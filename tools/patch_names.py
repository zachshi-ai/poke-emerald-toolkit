#!/usr/bin/env python3
# 用 PokeAPI 官方中文名替换源码里的英文名词（宝可梦/招式/道具/特性/属性/性格）
import csv, os, re, glob, json

BASE = '/root/build/pokeemerald-expansion-master'
API = '/root/build/pokeapi'
ZH_HANS = '12'

def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

def load(entity, names):
    id2ident = {}
    with open(os.path.join(API, entity + '.csv'), encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if 'identifier' in row:
                id2ident[row['id']] = row['identifier']
    keycol = entity[:-1] if entity.endswith('s') else entity
    # 表头第一列名各表不同，直接按位置取
    zh = {}
    with open(os.path.join(API, names + '.csv'), encoding='utf-8') as f:
        r = csv.reader(f)
        header = next(r)
        for row in r:
            if len(row) < 3:
                continue
            eid, lang, name = row[0], row[1], row[2]
            if lang == ZH_HANS:
                zh[eid] = name
    out = {}
    for eid, ident in id2ident.items():
        if eid in zh and zh[eid]:
            out[norm(ident)] = zh[eid]
    return out

species = load('pokemon_species', 'pokemon_species_names')
moves = load('moves', 'move_names')
items = load('items', 'item_names')
abilities = load('abilities', 'ability_names')
types = load('types', 'type_names')
natures = load('natures', 'nature_names')
print('dict sizes', len(species), len(moves), len(items), len(abilities), len(types), len(natures))

EXTRA = {
    'type': {'???': '???', 'Fairy': '妖精', 'Stellar': '星晶'},
    'nature': {},
}

stats = {}

def patch(pattern, path_glob, dicts, tag, stats):
    files = glob.glob(os.path.join(BASE, path_glob))
    changed = 0
    missed = []
    for p in files:
        s = open(p, encoding='utf-8').read()
        def rep(m):
            nonlocal changed
            name = m.group('name')
            key = norm(name)
            for d in dicts:
                if key in d:
                    changed += 1
                    return m.group('pre') + d[key] + m.group('post')
            missed.append(name)
            return m.group(0)
        s2 = pattern.sub(rep, s)
        if s2 != s:
            open(p, 'w', encoding='utf-8').write(s2)
    stats[tag] = (changed, len(set(missed)), sorted(set(missed))[:15])
    print(tag, 'changed', changed, 'missed', len(set(missed)), sorted(set(missed))[:10])

# 1. 宝可梦名
p = re.compile(r'(?P<pre>\.speciesName\s*=\s*_\(")(?P<name>[^"]+)(?P<post>"\))')
patch(p, 'src/data/pokemon/species_info/*.h', [species], 'species', stats)

# 2. 招式名
p = re.compile(r'(?P<pre>\.name\s*=\s*COMPOUND_STRING\(")(?P<name>[^"]+)(?P<post>"\))')
patch(p, 'src/data/moves_info.h', [moves], 'moves', stats)

# 3. 道具名
p = re.compile(r'(?P<pre>\.name\s*=\s*_\(")(?P<name>[^"]+)(?P<post>"\))')
patch(p, 'src/data/items.h', [items], 'items', stats)

# 4. 特性名
patch(p, 'src/data/abilities.h', [abilities], 'abilities', stats)

# 5. 属性名
patch(p, 'src/data/types_info.h', [types], 'types', stats)

json.dump(stats, open('/root/build/name_patch_stats.json', 'w'), ensure_ascii=False, indent=1)
