import json, re, glob, hashlib, os

base = '/root/build/pokeemerald-expansion-master/'

# ---- species enum ids ----
spec_txt = open(base + 'include/constants/species.h').read()
ids = {}
for m in re.finditer(r'^\s*(SPECIES_[A-Z0-9_]+)\s*=\s*(\d+)\s*,', spec_txt, re.M):
    ids[m.group(1)] = int(m.group(2))
for m in re.finditer(r'^\s*(SPECIES_[A-Z0-9_]+)\s*,\s*$', spec_txt, re.M):
    ids.setdefault(m.group(1), None)
print('species parsed:', len(ids))

# ---- types / flags ----
info = {}
for f in glob.glob(base + 'src/data/pokemon/species_info/gen_*_families.h'):
    txt = open(f, encoding='utf-8').read()
    parts = re.split(r'\n\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=', txt)
    for i in range(1, len(parts) - 1, 2):
        name = parts[i]
        body = parts[i + 1][:4000]
        tm = re.search(r'\.types\s*=\s*MON_TYPES\(([^)]*)\)', body)
        types = [t.strip() for t in tm.group(1).split(',')] if tm else []
        if any(not t.startswith('TYPE_') for t in types):
            types = []
        flags = set()
        for fl in ('isRestrictedLegendary', 'isSubLegendary', 'isMythical', 'isUltraBeast', 'isParadox'):
            if re.search(r'\.%s\s*=\s*TRUE' % fl, body):
                flags.add(fl)
        bst = 0
        for st in ('baseHP', 'baseAttack', 'baseDefense', 'baseSpeed', 'baseSpAttack', 'baseSpDefense'):
            mm = re.search(r'\.%s\s*=\s*(\d+)' % st, body)
            if mm:
                bst += int(mm.group(1))
        info[name] = {'types': types, 'flags': flags, 'bst': bst}

print('species info parsed:', len(info))

FORM_BAD = ('MEGA', 'GMAX', 'TOTEM', 'ETERNAMAX', 'ALOLAN', 'GALARIAN', 'HISUIAN', 'PALDEAN', 'TERA', 'PRIMAL', 'ORIGIN', '_ALOLA', '_GALAR', '_HISUI', '_PALDEA', '_SEVII', '_ATTACK', '_DEFENSE', '_SPEED', '_SANDY', '_TRASH', '_SUNSHINE', '_HEAT', '_WASH', '_FROST', '_FAN', '_MOW')

def is_plain_newgen(name):
    n = ids.get(name)
    if n is None or not (387 <= n <= 1025):
        return False
    if any(b in name for b in FORM_BAD):
        return False
    i = info.get(name)
    if not i or not i['types']:
        return False
    if i['flags']:
        return False
    return True

pool_by_type = {}
for name in info:
    if is_plain_newgen(name):
        for t in info[name]['types']:
            pool_by_type.setdefault(t, []).append(name)
for t in pool_by_type:
    pool_by_type[t].sort()
print('newgen pool', {t: len(v) for t, v in sorted(pool_by_type.items())})

path = base + 'src/data/wild_encounters.json'
d = json.load(open(path))
wg = d['wild_encounter_groups'][0]

PLAN = {
    'land_mons': [6, 7, 8, 9, 10, 11],
    'water_mons': [2, 3, 4],
    'fishing_mons': [7, 8, 9],
    'rock_smash_mons': [2, 3, 4],
}

backend = json.load(open('/root/build/wild_encounters_original.json')) if os.path.exists('/root/build/wild_encounters_original.json') else None
if backend is None:
    import shutil
    shutil.copy(path, '/root/build/wild_encounters_original.json')

changed = 0
for e in wg['encounters']:
    mapname = e.get('map', '')
    for table, slots in PLAN.items():
        tbl = e.get(table)
        if not tbl or 'mons' not in tbl:
            continue
        used = set(m['species'] for m in tbl['mons'])
        for slot in slots:
            if slot >= len(tbl['mons']):
                continue
            mon = tbl['mons'][slot]
            orig = mon['species']
            otypes = info.get(orig, {}).get('types', [])
            if not otypes:
                continue
            cands = []
            for t in otypes:
                cands.extend(pool_by_type.get(t, []))
            cands = [c for c in dict.fromkeys(cands) if c not in used]
            if not cands:
                continue
            ob = info.get(orig, {}).get('bst', 400)
            cands.sort(key=lambda c: abs(info.get(c, {}).get('bst', 400) - ob))
            top = cands[:6]
            h = int(hashlib.md5((mapname + table + str(slot)).encode()).hexdigest(), 16)
            pick = top[h % len(top)]
            mon['species'] = pick
            used.add(pick)
            changed += 1

json.dump(d, open(path, 'w'), indent=2, ensure_ascii=False)
print('slots replaced:', changed)
