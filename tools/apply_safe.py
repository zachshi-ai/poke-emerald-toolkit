#!/usr/bin/env python3
# 安全应用机翻：只处理 src 顶层 .c/.h，跳过定长结构文件，长度受限
import os, re, json, shutil

BASE = '/root/build/pokeemerald-expansion-master'
CACHE = '/root/build/trans_cache.json'
BACKUP = '/root/build/backup_src'

SKIP_FILES = {
    'easy_chat.c', 'debug.c', 'cjk_font.c',
}
SKIP_DIRS = {'data', 'test'}

STR_RE = re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
POLLUTED = re.compile(r'\((optional|translator|note)', re.I)

def main():
    cache = json.load(open(CACHE, encoding='utf-8'))
    os.makedirs(BACKUP, exist_ok=True)
    applied = 0
    files = 0
    for root, dirs, fs in os.walk(os.path.join(BASE, 'src')):
        rel = os.path.relpath(root, os.path.join(BASE, 'src'))
        if rel != '.' and rel.split(os.sep)[0] in SKIP_DIRS:
            continue
        for f in fs:
            if not (f.endswith('.c') or f.endswith('.h')):
                continue
            if f in SKIP_FILES:
                continue
            p = os.path.join(root, f)
            try:
                txt = open(p, encoding='utf-8').read()
            except UnicodeDecodeError:
                continue
            orig = txt
            local = [0]
            def rep(m):
                src = m.group(1)
                zh = cache.get(src)
                if not zh:
                    return m.group(0)
                if re.search(r'[\u4e00-\u9fff]', src):
                    return m.group(0)
                if POLLUTED.search(zh):
                    return m.group(0)
                # 长度保护：译文不应远长于原文
                if len(zh) > len(src) * 1.6 + 8:
                    return m.group(0)
                # 控制码数量必须一致
                if len(re.findall(r'\{[^}]*\}', src)) != len(re.findall(r'\{[^}]*\}', zh)):
                    return m.group(0)
                local[0] += 1
                return '_("' + zh + '")'
            txt = STR_RE.sub(rep, txt)
            if txt != orig:
                dst = os.path.join(BACKUP, rel.replace('.', '_'), f) if rel != '.' else os.path.join(BACKUP, f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(p, dst)
                open(p, 'w', encoding='utf-8').write(txt)
                files += 1
                applied += local[0]
    print('applied %d strings in %d files (backup at %s)' % (applied, files, BACKUP))

if __name__ == '__main__':
    main()
