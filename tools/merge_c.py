#!/usr/bin/env python3
# 按符号名合并汉化工程的 C 字符串定义
import os, re, glob

MINE = '/root/build/pokeemerald-expansion-master'
ZH = '/root/build/zh_src/pokeemerald-expansion-mingo-beacon'
DEF = re.compile(r'(?:static\s+)?const\s+u8\s+(\w+)\s*\[\s*\]\s*=')

def defs(path):
    try:
        txt = open(path, encoding='utf-8', errors='ignore').read()
    except Exception:
        return {}
    out = {}
    for m in DEF.finditer(txt):
        name = m.group(1)
        start = m.start()
        semi = txt.find(';', m.end())
        if semi < 0:
            continue
        body = txt[start:semi + 1]
        if '_(' not in body and 'COMPOUND_STRING' not in body:
            continue
        out[name] = body
    return out

def has_cjk(s):
    return bool(re.search(r'[\u4e00-\u9fff]', s))

def merge(mine_path, zh_path):
    mine = open(mine_path, encoding='utf-8').read()
    zmap = {k: v for k, v in defs(zh_path).items() if has_cjk(v)}
    if not zmap:
        return 0
    out = []
    pos = 0
    n = 0
    for m in DEF.finditer(mine):
        name = m.group(1)
        semi = mine.find(';', m.end())
        if semi < 0:
            continue
        if name in zmap:
            # 只替换初始化部分，保留我的声明（可能带显式长度）
            eq = mine.find('=', m.start())
            my_init = mine[eq + 1:semi]
            their = zmap[name]
            their_eq = their.find('=')
            their_init = their[their_eq + 1:their.rstrip().rfind(';')]
            # 若我的声明带 [N]，检查编码后长度是否放得下
            size_m = re.search(r'\[(\d+)\]', mine[m.start():eq])
            if size_m:
                limit = int(size_m.group(1)) - 1
                text = ''.join(re.findall(r'"(.*?)"', their_init, re.S))
                ln = 0
                for ch in text:
                    if ch == '\\':
                        continue
                    ln += 2 if ord(ch) > 127 else 1
                if ln > limit:
                    continue
            their_init = their_init.replace('COMPOUND_STRING(', '_(')
            out.append(mine[pos:eq + 1])
            out.append(their_init)
            pos = semi
            n += 1
    out.append(mine[pos:])
    if n:
        open(mine_path, 'w', encoding='utf-8').write(''.join(out))
    return n

def main():
    total = 0
    files = 0
    for zp in glob.glob(os.path.join(ZH, 'src', '*.c')):
        name = os.path.basename(zp)
        mp = os.path.join(MINE, 'src', name)
        if not os.path.exists(mp):
            continue
        n = merge(mp, zp)
        if n:
            total += n
            files += 1
    print('merged definitions:', total, 'files:', files)

if __name__ == '__main__':
    main()
