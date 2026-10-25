#!/usr/bin/env python3
# 按 [ENUM] 块合并汉化工程的 .description 文本
import re, os, sys, glob

MINE = '/root/build/pokeemerald-expansion-master'
ZH = '/root/build/zh_src/pokeemerald-expansion-mingo-beacon'
BLOCK = re.compile(r'\n\s*\[([A-Z][A-Z0-9_]*)\]\s*=')
DESC = '.description'

def find_desc(text, start):
    i = text.find(DESC, start)
    if i < 0:
        return None
    eq = text.find('=', i)
    if eq < 0:
        return None
    j = eq + 1
    depth = 0
    while j < len(text):
        c = text[j]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == ',' and depth <= 0:
            return (i, j)
        j += 1
    return None

def blocks(text):
    out = {}
    marks = list(BLOCK.finditer(text))
    for idx, m in enumerate(marks):
        end = marks[idx + 1].start() if idx + 1 < len(marks) else len(text)
        out[m.group(1)] = (m.end(), end)
    return out

def has_cjk(s):
    return bool(re.search(r'[\u4e00-\u9fff]', s))

def merge(mine_path, zh_path):
    mine = open(mine_path, encoding='utf-8', errors='ignore').read()
    zh = open(zh_path, encoding='utf-8', errors='ignore').read()
    zb = blocks(zh)
    mb = blocks(mine)
    repl = []
    for name, (ms, me) in mb.items():
        if name not in zb:
            continue
        zs, ze = zb[name]
        zm = find_desc(zh, zs)
        if not zm or zm[1] > ze:
            continue
        ztxt = zh[zm[0]:zm[1] + 1]
        if not has_cjk(ztxt):
            continue
        mm = find_desc(mine, ms)
        if not mm or mm[1] > me:
            continue
        if '#' in ztxt or '#' in mine[mm[0]:mm[1] + 1]:
            continue
        repl.append((mm[0], mm[1] + 1, ztxt))
    if not repl:
        return 0
    out = []
    pos = 0
    for s, e, t in sorted(repl):
        out.append(mine[pos:s])
        out.append(t)
        pos = e
    out.append(mine[pos:])
    open(mine_path, 'w', encoding='utf-8').write(''.join(out))
    return len(repl)

def run(pairs):
    total = 0
    for mine_rel, zh_rel in pairs:
        mp = os.path.join(MINE, mine_rel)
        zp = os.path.join(ZH, zh_rel)
        if not (os.path.exists(mp) and os.path.exists(zp)):
            print('skip', mine_rel)
            continue
        n = merge(mp, zp)
        print('%-55s %d' % (mine_rel, n))
        total += n
    print('total', total)

if __name__ == '__main__':
    pairs = []
    for zf in glob.glob(os.path.join(ZH, 'src/data/pokemon/species_info/gen_*.h')):
        pairs.append(('src/data/pokemon/species_info/' + os.path.basename(zf),
                      'src/data/pokemon/species_info/' + os.path.basename(zf)))
    pairs += [('src/data/moves_info.h', 'src/data/moves_info.h'),
              ('src/data/items.h', 'src/data/items.h'),
              ('src/data/abilities.h', 'src/data/abilities.h')]
    run(pairs)
