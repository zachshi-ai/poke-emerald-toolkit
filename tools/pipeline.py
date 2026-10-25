#!/usr/bin/env python3
# 逐文件机翻流水线：翻译 -> 写回 -> 编译校验 -> 失败回滚；支持断点续跑
import os, re, json, time, shutil, subprocess, urllib.parse, urllib.request

BASE = '/root/build/pokeemerald-expansion-master'
STATE = '/root/build/pipeline_state.json'
LOG = '/root/build/pipeline.log'
BAK = '/root/build/pipeline_bak'

STR_RE = re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
PLACE_RE = re.compile(r'\{[^}]*\}')
POLLUTED = re.compile(r'\((optional|translator|note)', re.I)

SKIP = {'easy_chat.c', 'debug.c', 'cjk_font.c', 'pokemon_sprite_visualizer.c',
        'trainer_tower_sets.c', 'credits.c', 'credits_frlg.c'}

# 按玩家可见度排序
ORDER = [
    'battle_message.c', 'item_use.c', 'strings.c', 'battle_script_commands.c',
    'party_menu.c', 'pokemon_summary_screen.c', 'pokedex.c', 'bag.c', 'item_menu.c',
    'start_menu.c', 'main_menu.c', 'option_menu.c', 'save.c', 'field_screen_effect.c',
    'field_player_avatar.c', 'field_control_avatar.c', 'overworld.c', 'script_pokemon_util.c',
    'battle_main.c', 'battle_util.c', 'battle_controller_player.c', 'battle_controller_opponent.c',
    'battle_anim_utility_funcs.c', 'battle_interface.c', 'contest.c', 'berry.c',
    'daycare.c', 'pokemon_storage_system.c', 'trainer_card.c', 'pokenav.c',
]

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

def tr(q, tries=3):
    url = 'https://api.mymemory.translated.net/get?' + urllib.parse.urlencode({'q': q, 'langpair': 'en|zh-CN'})
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                d = json.loads(r.read().decode())
            if d.get('quotaFinished'):
                return None
            t = d.get('responseData', {}).get('translatedText')
            if t:
                return t
        except Exception:
            time.sleep(2 + k * 3)
    return None

def compile_obj(name):
    obj = 'build/emerald/src/%s.o' % name[:-2]
    try:
        os.remove(os.path.join(BASE, obj))
    except OSError:
        pass
    r = subprocess.run(['make', obj], cwd=BASE, capture_output=True, text=True, timeout=600)
    return r.returncode == 0, (r.stdout + r.stderr)[-800:]

def process(name):
    p = os.path.join(BASE, 'src', name)
    if not os.path.exists(p):
        return 'missing'
    txt = open(p, encoding='utf-8').read()
    strings = []
    for m in STR_RE.finditer(txt):
        s = m.group(1)
        if not re.search(r'[A-Za-z]', s) or re.search(r'[\u4e00-\u9fff]', s):
            continue
        if s not in strings:
            strings.append(s)
    if not strings:
        return 'no-strings'
    log('%s: %d strings' % (name, len(strings)))

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
        if (i + 1) % 40 == 0:
            log('  %s progress %d/%d (kept %d)' % (name, i + 1, len(strings), len(mapping)))
    if not mapping:
        return 'nothing-translated'

    os.makedirs(BAK, exist_ok=True)
    shutil.copy2(p, os.path.join(BAK, name))
    def rep(m):
        s = m.group(1)
        return '_("' + mapping[s] + '")' if s in mapping else m.group(0)
    out = STR_RE.sub(rep, txt)
    open(p, 'w', encoding='utf-8').write(out)

    # charmap 可能缺字：先重生成字库
    subprocess.run(['python3', '/root/build/gen_cjk.py'], cwd='/root/build', capture_output=True, text=True)
    ok, err = compile_obj(name)
    if ok:
        log('%s: OK (%d strings translated)' % (name, len(mapping)))
        return 'ok'
    log('%s: COMPILE FAIL, rolling back' % name)
    log(err[-300:])
    shutil.copy2(os.path.join(BAK, name), p)
    subprocess.run(['python3', '/root/build/gen_cjk.py'], cwd='/root/build', capture_output=True, text=True)
    return 'compile-fail'

def main():
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    todo = [f for f in ORDER if state.get(f) not in ('ok', 'no-strings', 'missing')]
    # 追加 ORDER 之外的 src 顶层 .c 文件
    extra = sorted(f for f in os.listdir(os.path.join(BASE, 'src'))
                   if f.endswith('.c') and f not in ORDER and f not in SKIP
                   and not f.startswith('test_'))
    for f in extra:
        if state.get(f) not in ('ok', 'no-strings', 'missing'):
            todo.append(f)
    log('pipeline start, %d files to do' % len(todo))
    for name in todo:
        try:
            res = process(name)
        except Exception as e:
            log('%s: EXCEPTION %s' % (name, e))
            res = 'error'
        state[name] = res
        json.dump(state, open(STATE, 'w'), ensure_ascii=False, indent=1)
        time.sleep(1)
    log('pipeline finished')

if __name__ == '__main__':
    main()
