#!/usr/bin/env python3
# 提取所有 _("...") 字符串，批量机翻为中文，带缓存与多引擎回退
import os, re, json, sys, time, urllib.parse, urllib.request, threading, queue

BASE = '/root/build/pokeemerald-expansion-master'
CACHE = '/root/build/trans_cache.json'
OUT = '/root/build/trans_result.json'

STR_RE = re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
PLACE_RE = re.compile(r'\{[^}]*\}')

def collect():
    strings = {}
    for root, dirs, files in os.walk(os.path.join(BASE, 'src')):
        for f in files:
            if not (f.endswith('.c') or f.endswith('.h')):
                continue
            p = os.path.join(root, f)
            try:
                txt = open(p, encoding='utf-8').read()
            except UnicodeDecodeError:
                continue
            for m in STR_RE.finditer(txt):
                s = m.group(1)
                if not re.search(r'[A-Za-z]', s):
                    continue
                if re.search(r'[\u4e00-\u9fff]', s):
                    continue
                strings.setdefault(s, 0)
                strings[s] += 1
    return strings

def protect(s):
    ph = []
    def rep(m):
        ph.append(m.group(0))
        return '{%d}' % (len(ph) - 1)
    t = PLACE_RE.sub(rep, s)
    t = t.replace('\\n', '{%d}' % len(ph)); ph.append('\\n')
    t = t.replace('\\p', '{%d}' % len(ph)); ph.append('\\p')
    t = t.replace('\\l', '{%d}' % len(ph)); ph.append('\\l')
    return t, ph

def restore(t, ph):
    for i, v in enumerate(ph):
        t = t.replace('{%d}' % i, v)
    return t

def tr_mymemory(q):
    url = 'https://api.mymemory.translated.net/get?' + urllib.parse.urlencode({'q': q, 'langpair': 'en|zh-CN'})
    with urllib.request.urlopen(url, timeout=25) as r:
        d = json.loads(r.read().decode())
    if d.get('quotaFinished'):
        raise RuntimeError('quota')
    t = d.get('responseData', {}).get('translatedText')
    if not t:
        raise RuntimeError('empty')
    return t

def tr_libretranslate(q):
    data = json.dumps({'q': q, 'source': 'en', 'target': 'zh'}).encode()
    req = urllib.request.Request('https://translate.terraprint.co/translate', data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    return d['translatedText']

def translate_one(s):
    q, ph = protect(s)
    if len(q) > 480:
        return None
    last = None
    for fn in (tr_mymemory, tr_libretranslate, tr_mymemory):
        try:
            return restore(fn(q), ph)
        except Exception as e:
            last = e
            time.sleep(0.2)
    return None

def main():
    strings = collect()
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [s for s in strings if s not in cache]
    print('total %d, cached %d, todo %d' % (len(strings), len(cache), len(todo)), flush=True)

    lock = threading.Lock()
    done = [0]

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                s = todo.pop()
            t = translate_one(s)
            with lock:
                if t is not None:
                    cache[s] = t
                done[0] += 1
                if done[0] % 50 == 0:
                    json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)
                    print('progress %d' % done[0], flush=True)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)
    print('finished, cache size %d' % len(cache), flush=True)

if __name__ == '__main__':
    main()
