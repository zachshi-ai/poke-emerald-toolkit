#!/usr/bin/env python3
# 单文件批量机翻：提取 -> 翻译 -> 安全回写（带备份）
import os, re, json, sys, time, shutil, urllib.parse, urllib.request

BASE = '/root/build/pokeemerald-expansion-master'
STR_RE = re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
PLACE_RE = re.compile(r'\{[^}]*\}')
POLLUTED = re.compile(r'\((optional|translator|note)', re.I)

def protect(s):
    ph = []
    def rep(m):
        ph.append(m.group(0))
        return '{%d}' % (len(ph) - 1)
    t = PLACE_RE.sub(rep, s)
    for esc in ('\\n', '\\p', '\\l'):
        if esc in t:
            t = t.replace(esc, '{%d}' % len(ph))
            ph.append(esc)
    return t, ph

def restore(t, ph):
    for i, v in enumerate(ph):
        t = t.replace('{%d}' % i, v)
    return t

def tr(q):
    url = 'https://api.mymemory.translated.net/get?' + urllib.parse.urlencode({'q': q, 'langpair': 'en|zh-CN'})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                d = json.loads(r.read().decode())
            if d.get('quotaFinished'):
                return None
            t = d.get('responseData', {}).get('translatedText')
            if t:
                return t
        except Exception:
            time.sleep(0.5)
    return None

def main(path):
    p = os.path.join(BASE, path)
    txt = open(p, encoding='utf-8').read()
    strings = []
    for m in STR_RE.finditer(txt):
        s = m.group(1)
        if not re.search(r'[A-Za-z]', s) or re.search(r'[\u4e00-\u9fff]', s):
            continue
        if s not in strings:
            strings.append(s)
    print('unique strings:', len(strings))
    mapping = {}
    for i, s in enumerate(strings):
        q, ph = protect(s)
        if len(q) > 450:
            continue
        zh = tr(q)
        if not zh:
            continue
        zh = restore(zh, ph)
        if POLLUTED.search(zh):
            continue
        if len(zh) > len(s) * 1.6 + 8:
            continue
        if len(re.findall(r'\{[^}]*\}', s)) != len(re.findall(r'\{[^}]*\}', zh)):
            continue
        mapping[s] = zh
        if (i + 1) % 25 == 0:
            print('  translated %d/%d' % (i + 1, len(strings)), flush=True)
    print('kept translations:', len(mapping))
    bak = '/root/build/backup_src/' + path.replace('/', '_')
    os.makedirs(os.path.dirname(bak), exist_ok=True)
    shutil.copy2(p, bak)
    def rep(m):
        s = m.group(1)
        return '_("' + mapping[s] + '")' if s in mapping else m.group(0)
    out = STR_RE.sub(rep, txt)
    open(p, 'w', encoding='utf-8').write(out)
    print('written', p)

if __name__ == '__main__':
    main(sys.argv[1])
