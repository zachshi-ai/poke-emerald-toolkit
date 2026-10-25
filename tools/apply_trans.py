#!/usr/bin/env python3
# 把机翻结果写回源码（_("EN") -> _("ZH")），并重生成中文字库/charmap
import os, re, json

BASE = '/root/build/pokeemerald-expansion-master'
CACHE = '/root/build/trans_cache.json'

STR_RE = re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')

TERMS = [
    ('POKéMON', '宝可梦'), ('Pokémon', '宝可梦'), ('POKEMON', '宝可梦'),
    ('POKéDEX', '图鉴'), ('Pokédex', '图鉴'),
    ('TRAINER', '训练家'), ('Trainer', '训练家'),
    ('GYM LEADER', '道馆馆主'), ('GYM', '道馆'), ('BADGE', '徽章'),
    ('POKé BALL', '精灵球'), ('POKé BALLS', '精灵球'),
    ('HP', 'HP'), ('PP', 'PP'),
]

def post(s):
    for a, b in TERMS:
        s = s.replace(a, b)
    # 去掉中文与占位符之间的多余空格
    s = re.sub(r'\s*([\u4e00-\u9fff])\s*', r'\1', s)
    s = re.sub(r'\s*\{(\d+)\}\s*', r'{\1}', s)
    s = re.sub(r' +', ' ', s)
    return s.strip()

def apply():
    cache = json.load(open(CACHE, encoding='utf-8'))
    changed = 0
    files = 0
    for root, dirs, fs in os.walk(os.path.join(BASE, 'src')):
        for f in fs:
            if not (f.endswith('.c') or f.endswith('.h')):
                continue
            p = os.path.join(root, f)
            try:
                txt = open(p, encoding='utf-8').read()
            except UnicodeDecodeError:
                continue
            orig = txt
            def rep(m):
                nonlocal changed
                src = m.group(1)
                zh = cache.get(src)
                if not zh or re.search(r'[\u4e00-\u9fff]', src):
                    return m.group(0)
                changed += 1
                return '_("' + post(zh) + '")'
            txt = STR_RE.sub(rep, txt)
            if txt != orig:
                open(p, 'w', encoding='utf-8').write(txt)
                files += 1
    print('applied', changed, 'strings in', files, 'files')

if __name__ == '__main__':
    apply()
