import re

with open('/root/pesarguard_bot/pesarguard.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'BOT_TOKEN = ".*?"', 'BOT_TOKEN = "8500420442:AAHQZ4CtgjuvBuEi-X3Mb9mRG19n8u8R6pk"', code)
code = re.sub(r'ADMIN_ID = \d+', 'ADMIN_ID = 7254045901', code)

with open('/root/pesarguard_bot/pesarguard.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated BOT_TOKEN and ADMIN_ID in pesarguard.py")
