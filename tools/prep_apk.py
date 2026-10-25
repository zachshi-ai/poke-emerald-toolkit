import re, sys

mp = '/root/build/pe_zh/pokeemerald.map'
txt = open(mp, errors='ignore').read()
a = re.search(r'(0x[0-9a-fA-F]+)\s+gBaseStatOverride\s*$', txt, re.M)
b = re.search(r'(0x[0-9a-fA-F]+)\s+gBaseStatOverrideFlags\s*$', txt, re.M)
if not (a and b):
    sys.exit('symbols not found')
addr_over = int(a.group(1), 16)
addr_flags = int(b.group(1), 16)
n = (addr_flags - addr_over) // 6
size_over = 6 * n
size_flags = n
cfg = f"over=0x{addr_over:08x}\nsize={size_over}\nflags=0x{addr_flags:08x}\nfsize={size_flags}\n"
open('/root/build/app/assets/override.cfg', 'w').write(cfg)
print(cfg)
