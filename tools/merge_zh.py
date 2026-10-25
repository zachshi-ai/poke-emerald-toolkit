#!/usr/bin/env python3
# 把汉化工程的 .string 文本按 label 合并进本工程
import os, re, sys, shutil

MINE = '/root/build/pokeemerald-expansion-master'
ZH = '/root/build/zh_src/pokeemerald-expansion-mingo-beacon'
LABEL = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)::?\s*$')
STR = re.compile(r'^\s*\.string "')

def parse(path):
    blocks = {}
    label = None
    cur = []
    with open(path, encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = LABEL.match(line.rstrip('\n'))
            if m:
                if label and cur:
                    blocks[label] = cur
                label = m.group(1)
                cur = []
            elif STR.match(line):
                if label is not None:
                    cur.append(line)
            else:
                if label and cur:
                    blocks[label] = cur
                cur = []
                if line.strip():
                    label = None
    if label and cur:
        blocks[label] = cur
    return blocks

def has_cjk(lines):
    return any(re.search(r'[\u4e00-\u9fff]', l) for l in lines)

def merge_file(mine_path, zh_path):
    mine = open(mine_path, encoding='utf-8').read().splitlines(keepends=True)
    zh = parse(zh_path)
    out = []
    i = 0
    replaced = 0
    while i < len(mine):
        line = mine[i]
        m = LABEL.match(line.rstrip('\n'))
        out.append(line)
        i += 1
        if m:
            label = m.group(1)
            # 收集我的 .string 行
            j = i
            while j < len(mine) and STR.match(mine[j]):
                j += 1
            mine_block = mine[i:j]
            zh_block = zh.get(label)
            if zh_block and has_cjk(zh_block) and len(zh_block) <= max(len(mine_block), 6):
                out.extend(zh_block)
                replaced += 1
            else:
                out.extend(mine_block)
            i = j
    open(mine_path, 'w', encoding='utf-8').write(''.join(out))
    return replaced

def main():
    total = 0
    files = 0
    for name in sorted(os.listdir(os.path.join(ZH, 'data/maps'))):
        zp = os.path.join(ZH, 'data/maps', name, 'scripts.inc')
        mp = os.path.join(MINE, 'data/maps', name, 'scripts.inc')
        if not (os.path.exists(zp) and os.path.exists(mp)):
            continue
        shutil.copy2(mp, '/root/build/mergebak_' + name + '.inc') if False else None
        n = merge_file(mp, zp)
        if n:
            total += n
            files += 1
    print('merged labels:', total, 'files:', files)

if __name__ == '__main__':
    main()
