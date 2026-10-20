#!/usr/bin/env python3
"""Mechanical splitter: copies exact source slices of pesarguard.py into modules.
Only generated content: import lines, __init__.py files, run.py, and ONE documented
edit (BASE_DIR in config.py) so data/ and logs/ stay next to the package folder."""
import ast, re, os, io, sys, collections, shutil
from pyflakes import api, reporter

SRC, MAP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(SRC, encoding='utf-8').read()
lines = src.split('\n')
tree = ast.parse(src)

# ---- mapping from ANALYSIS.md ----
dest = []
for l in open(MAP, encoding='utf-8'):
    m = re.match(r'\|\s*\d+\s*\|\s*(.*?)\s*\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*`?([^`|]+?)`?\s*\|\s*$', l)
    if m: dest.append((m[1].strip('`'), m[2], m[5].strip()))
# map by node ORDER (line numbers may shift between file versions); verify type and name per row
assert len(dest) == len(tree.body), f"mapping rows {len(dest)} != nodes {len(tree.body)}"
for (nm, ty, _), n in zip(dest, tree.body):
    assert ty == type(n).__name__, f"type mismatch at line {n.lineno}: {ty} vs {type(n).__name__}"
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        assert nm == n.name, f"name mismatch at line {n.lineno}: {nm} vs {n.name}"
dest = [(n.lineno, n.end_lineno, d) for n, (_, _, d) in zip(tree.body, dest)]

W, S, AR = 'pesarguard/handlers/user/wallet.py', 'pesarguard/handlers/user/services.py', 'pesarguard/handlers/admin/receipts.py'
MERGED = 'pesarguard/handlers/user/wallet_services_receipts.py'
wallet_names = {'wallet_screen','start_topup','wallet_add_credit','wallet_card_sent','_keep_xp_and_clear',
                'receipt_review_kb','handle_wallet_receipt_text','handle_wallet_receipt_photo'}
admin_rcpt = {'admin_receipts_queue','handle_receipt_review','receipt_fix_start','receipt_fix_apply'}

def name_of(n):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): return n.name
    if isinstance(n, ast.Assign): return ','.join(t.id for t in n.targets if isinstance(t, ast.Name))
    if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name): return n.target.id
    return None

nodes = []  # (node, dest)
for n, (_, _, d) in zip(tree.body, dest):
    if d == 'imports.py' or isinstance(n, (ast.Import, ast.ImportFrom)): continue
    if d == MERGED:
        nm = name_of(n)
        d = W if nm in wallet_names else AR if nm in admin_rcpt else S
    nodes.append((n, d))

# ---- original imports: name -> import spec ----
imp = {}
for n in tree.body:
    if isinstance(n, ast.Import):
        for a in n.names: imp[(a.asname or a.name).split('.')[0]] = ('import', a.name, a.asname)
    elif isinstance(n, ast.ImportFrom):
        for a in n.names: imp[a.asname or a.name] = ('from', n.module, a.name, a.asname)

# ---- project-level names -> module ----
owner = {}
for n, d in nodes:
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name): owner[t.id] = d
    elif name_of(n): owner[name_of(n)] = d
def modname(path): return path[:-3].replace('/', '.')

# ---- module bodies: exact slices (with preceding comment lines) ----
prev_end = 0
seg = {}
for n, (a, b, d0) in zip(tree.body, dest):
    start = prev_end + 1
    prev_end = b
    if d0 == 'imports.py' or isinstance(n, (ast.Import, ast.ImportFrom)): continue
    txt = lines[start - 1:b]
    while txt and not txt[0].strip(): txt = txt[1:]
    seg[id(n)] = '\n'.join(txt)
bodies = collections.defaultdict(list)
for n, d in nodes: bodies[d].append(seg[id(n)])

BASE_OLD = 'BASE_DIR = os.path.dirname(os.path.abspath(__file__))'
BASE_NEW = ('# NOTE (split): config.py lives one level below the project root; BASE_DIR must still be the\n'
            '# folder that contains data/ and logs/ (the folder holding run.py).\n'
            'BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))')

class Rep:
    def __init__(s): s.undef = set(); s.other = []
    def unexpectedError(s, f, m): s.other.append(m)
    def syntaxError(s, f, m, l, c, t): s.other.append(m)
    def flake(s, m):
        if m.__class__.__name__ == 'UndefinedName': s.undef.add(m.message_args[0])

def fmt_import(spec_list):
    out, froms = [], collections.OrderedDict()
    for s in spec_list:
        if s[0] == 'import': out.append(f'import {s[1]}' + (f' as {s[2]}' if s[2] else ''))
        else: froms.setdefault(s[1], []).append(s[2] + (f' as {s[3]}' if s[3] else ''))
    for m, names in froms.items(): out.append(f'from {m} import ' + ', '.join(names))
    return out

if os.path.exists(OUT): shutil.rmtree(OUT)
for d, body in bodies.items():
    code = '\n\n'.join(body) + '\n'
    if d.endswith('config.py'): code = code.replace(BASE_OLD, BASE_NEW)
    r = Rep(); api.check(code, d, r)
    assert not r.other, (d, r.other)
    std, proj = [], collections.defaultdict(list)
    for nm in sorted(r.undef):
        if nm in imp: std.append(imp[nm])
        elif nm in owner and owner[nm] != d: proj[owner[nm]].append(nm)
        elif nm in dir(__builtins__) or nm == '__file__': pass
        else: raise SystemExit(f'unresolved name {nm} in {d}')
    # dedupe std specs
    seen, std2 = set(), []
    for s in std:
        if s not in seen: seen.add(s); std2.append(s)
    hdr = []
    if not d.endswith(('config.py', 'bootstrap.py')):
        hdr.append('from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)')
    hdr += fmt_import(sorted(std2, key=lambda s: (s[0] != 'import', s[1])))
    for m in sorted(proj): hdr.append(f'from {modname(m)} import ' + ', '.join(sorted(set(proj[m]))))
    full = '\n'.join(hdr) + '\n\n\n' + code
    p = os.path.join(OUT, d); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(full)

for pkg in ['pesarguard', 'pesarguard/handlers', 'pesarguard/handlers/user', 'pesarguard/handlers/admin']:
    open(os.path.join(OUT, pkg, '__init__.py'), 'w').write('')
open(os.path.join(OUT, 'run.py'), 'w').write('from pesarguard.main import main\n\nif __name__ == "__main__":\n    main()\n')
print('modules:', len(bodies))
