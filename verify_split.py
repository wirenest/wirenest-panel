import ast, sys, os, re, collections, subprocess, importlib, shutil, tempfile
orig, root = sys.argv[1], sys.argv[2]
pkg = os.path.join(root, 'pesarguard')
files = [os.path.join(d, f) for d, _, fs in os.walk(pkg) for f in fs if f.endswith('.py')]
ok = True
def sec(t): print('\n=== ' + t + ' ===')

sec('1. star imports')
star = [f for f in files if re.search(r'^from .* import \*', open(f).read(), re.M)]
print('files with import *:', len(star)); ok &= not star

sec('2. pyflakes (undefined names)')
r = subprocess.run([sys.executable, '-m', 'pyflakes', pkg, os.path.join(root, 'run.py')], capture_output=True, text=True)
und = [l for l in r.stdout.splitlines() if 'undefined name' in l or 'may be undefined' in l]
print('undefined-name warnings:', len(und)); [print(' ', l) for l in und[:10]]; ok &= not und
print('other pyflakes lines:', len([l for l in r.stdout.splitlines() if l not in und]))

sec('3. AST equality of every non-import top-level node')
ot = ast.parse(open(orig, encoding='utf-8').read())
def key(n): return ast.dump(n, include_attributes=False)
BASE = 'BASE_DIR'
oc = collections.Counter()
for n in ot.body:
    if isinstance(n, (ast.Import, ast.ImportFrom)): continue
    if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == BASE: continue
    oc[key(n)] += 1
nc = collections.Counter(); order = {}
for f in files:
    for n in ast.parse(open(f, encoding='utf-8').read()).body:
        if isinstance(n, (ast.Import, ast.ImportFrom)): continue
        if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == BASE: continue
        nc[key(n)] += 1
print('original nodes (excl imports, BASE_DIR):', sum(oc.values()), '| split:', sum(nc.values()))
print('missing:', sum((oc - nc).values()), '| extra/duplicated:', sum((nc - oc).values()))
ok &= (oc == nc)

sec('4. dependency graph / SCC')
g = collections.defaultdict(set)
for f in files:
    m = os.path.relpath(f, root)[:-3].replace(os.sep, '.')
    if m.endswith('.__init__'): m = m[:-9]
    for n in ast.walk(ast.parse(open(f).read())):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith('pesarguard'):
            tgt = n.module
            if tgt == 'pesarguard':
                for a in n.names: g[m].add('pesarguard.' + a.name)
            else: g[m].add(tgt)
idx, low, st, on, res, c = {}, {}, [], set(), [], [0]
def sc(v):
    idx[v] = low[v] = c[0]; c[0] += 1; st.append(v); on.add(v)
    for w in g[v]:
        if w not in idx: sc(w); low[v] = min(low[v], low[w])
        elif w in on: low[v] = min(low[v], idx[w])
    if low[v] == idx[v]:
        comp = []
        while True:
            w = st.pop(); on.discard(w); comp.append(w)
            if w == v: break
        if len(comp) > 1: res.append(comp)
for v in list(g):
    if v not in idx: sc(v)
print('cycles:', res); ok &= not res

sec('5. mutable globals only used where defined')
for gname in ['_DB', '_BOT_OBJ']:
    users = [os.path.relpath(f, root) for f in files if re.search(r'\b' + gname + r'\b', open(f).read())]
    print(gname, '->', users); ok &= len(users) == 1

sec('6. runtime import of every module (temp copy)')
tmp = tempfile.mkdtemp(); shutil.copytree(root, tmp + '/p')
sys.path.insert(0, tmp + '/p'); os.chdir(tmp + '/p')
fails = 0; cnt = 0
for f in sorted(files):
    m = os.path.relpath(f, root)[:-3].replace(os.sep, '.')
    if m.endswith('.__init__'): m = m[:-9]
    try: importlib.import_module(m); cnt += 1
    except Exception as e: fails += 1; print('FAIL', m, type(e).__name__, e)
print(f'imported {cnt}/{len(files)}'); ok &= not fails
import pesarguard.config as cfg
print('BASE_DIR ->', os.path.relpath(cfg.BASE_DIR, tmp + '/p') or '.', '(must be "." = folder containing run.py)')
ok &= os.path.abspath(cfg.BASE_DIR) == os.path.abspath(tmp + '/p')
print('\nRESULT:', 'ALL CHECKS PASSED' if ok else 'FAILED')
