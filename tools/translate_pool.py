#!/usr/bin/env python3
# 并行翻译池：多线程 + 双端点，先全量翻译再逐文件注入编译校验
import os, re, json, time, shutil, subprocess, threading, queue
import urllib.parse, urllib.request

BASE = '/root/build/pokeemerald-expansion-master'
CACHE = '/root/build/pool_cache.json'
LOG = '/root/build/pool.log'
BAK = '/root/build/pool_bak'

STR_RE = re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
PLACE_RE = re.compile(r'\{[^}]*\}')
POLLUTED = re.compile(r'\((optional|translator|note)', re.I)

SKIP_FILES = {'easy_chat.c', 'debug.c', 'cjk_font.c', 'pokemon_sprite_visualizer.c',
              'trainer_tower_sets.c', 'credits.c', 'credits_frlg.c', 'test_runner.c'}

lock = threading.Lock()
done = [0]
total = [0]

def log(msg):
    line = '[%s] %s' % (time.strftime('%H:%M:%S'), msg)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)

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

def tr_disroot(q):
    data = json.dumps({'q': q, 'source': 'en', 'target': 'zh'}).encode()
    req = urllib.request.Request('https://translate.disroot.org/translate', data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode())
    return d['translatedText']

def translate(s):
    q, ph = protect(s)
    if len(q) > 450:
        return None
    engines = (tr_mymemory, tr_disroot) if (hash(s) % 2 == 0) else (tr_disroot, tr_mymemory)
    for fn in engines:
        try:
            t = restore(fn(q), ph)
            if POLLUTED.search(t):
                continue
            if len(t) > len(s) * 1.6 + 8:
                continue
            if len(re.findall(r'\{[^}]*\}', s)) != len(re.findall(r'\{[^}]*\}', t)):
                continue
            return t
        except Exception:
            time.sleep(0.3)
    return None

def worker(todo, cache):
    while True:
        with lock:
            if not todo:
                return
            s = todo.pop()
        t = translate(s)
        with lock:
            if t:
                cache[s] = t
            done[0] += 1
            if done[0] % 100 == 0:
                json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)
                log('translated %d/%d (cache %d)' % (done[0], total[0], len(cache)))

def collect():
    pairs = {}
    for f in sorted(os.listdir(os.path.join(BASE, 'src'))):
        if not f.endswith('.c') or f in SKIP_FILES:
            continue
        p = os.path.join(BASE, 'src', f)
        try:
            txt = open(p, encoding='utf-8').read()
        except UnicodeDecodeError:
            continue
        for m in STR_RE.finditer(txt):
            s = m.group(1)
            if not re.search(r'[A-Za-z]', s) or re.search(r'[\u4e00-\u9fff]', s):
                continue
            pairs.setdefault(s, set()).add(f)
    return pairs

def compile_obj(name):
    obj = 'build/emerald/src/%s.o' % name[:-2]
    try:
        os.remove(os.path.join(BASE, obj))
    except OSError:
        pass
    r = subprocess.run(['make', obj], cwd=BASE, capture_output=True, text=True, timeout=600)
    return r.returncode == 0, (r.stdout + r.stderr)[-600:]

def main():
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    pairs = collect()
    todo = [s for s in pairs if s not in cache]
    total[0] = len(pairs)
    log('unique strings %d, to translate %d' % (len(pairs), len(todo)))

    threads = [threading.Thread(target=worker, args=(todo, cache), daemon=True) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)
    log('translation done, cache %d' % len(cache))

    # 逐文件注入 + 编译校验
    os.makedirs(BAK, exist_ok=True)
    files = sorted({f for fs in pairs.values() for f in fs})
    ok, fail = 0, 0
    for f in files:
        p = os.path.join(BASE, 'src', f)
        txt = open(p, encoding='utf-8').read()
        used = [0]
        def rep(m):
            s = m.group(1)
            zh = cache.get(s)
            if not zh or s not in pairs or f not in pairs[s]:
                return m.group(0)
            used[0] += 1
            return '_("' + zh + '")'
        out = STR_RE.sub(rep, txt)
        if out == txt:
            continue
        shutil.copy2(p, os.path.join(BAK, f))
        open(p, 'w', encoding='utf-8').write(out)
        subprocess.run(['python3', '/root/build/gen_cjk.py'], cwd='/root/build', capture_output=True)
        good, err = compile_obj(f)
        if good:
            ok += 1
            log('%s OK (%d)' % (f, used[0]))
        else:
            shutil.copy2(os.path.join(BAK, f), p)
            subprocess.run(['python3', '/root/build/gen_cjk.py'], cwd='/root/build', capture_output=True)
            fail += 1
            log('%s FAIL rollback: %s' % (f, err[-160:].replace('\n', ' ')))
    log('inject done: ok %d, rollback %d' % (ok, fail))

if __name__ == '__main__':
    main()
