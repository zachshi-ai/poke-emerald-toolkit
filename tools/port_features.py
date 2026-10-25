#!/usr/bin/env python3
# 在中文底座上移植我们的功能：DEBUG菜单、遇敌表扩世代、种族值持久化
import os, re, json, shutil

B = '/root/build/pe_zh'

def patch_debug_cfg():
    p = os.path.join(B, 'include/config/debug.h')
    s = open(p, encoding='utf-8').read()
    s = s.replace('#define DEBUG_OVERWORLD_MENU            DISABLED_ON_RELEASE',
                  '#define DEBUG_OVERWORLD_MENU            TRUE')
    if 'DEBUG_OVERWORLD_IN_MENU' in s:
        s = re.sub(r'#define DEBUG_OVERWORLD_IN_MENU\s+\w+',
                   '#define DEBUG_OVERWORLD_IN_MENU         TRUE', s)
    s = s.replace('#define DEBUG_BATTLE_MENU               DISABLED_ON_RELEASE',
                  '#define DEBUG_BATTLE_MENU               TRUE')
    open(p, 'w', encoding='utf-8').write(s)
    print('debug config ok')

def patch_save_struct():
    p = os.path.join(B, 'include/global.h')
    s = open(p, encoding='utf-8').read()
    if 'BaseStatSaveEntries' in s:
        print('save struct already'); return
    s = s.replace('struct SaveBlock1\n{', '''#define MAX_BASE_STAT_OVERRIDES 36

struct BaseStatSaveEntry
{
    u16 species;
    u8 stats[NUM_STATS];
};

struct BaseStatSaveEntries
{
    u16 count;
    struct BaseStatSaveEntry entries[MAX_BASE_STAT_OVERRIDES];
};

struct SaveBlock1
{''', 1)
    s = s.replace('''    // sizeof: 0x3???
};''', '''    /*StepClaw*/ struct BaseStatSaveEntries baseStatEntries;
    // sizeof: 0x3???
};''', 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('global.h ok')

def patch_pokemon():
    p = os.path.join(B, 'src/pokemon.c')
    s = open(p, encoding='utf-8').read()
    if 'BaseStatOverrides_LoadFromSave' in s:
        print('pokemon.c already'); return
    m = re.search(r'u32 GetSpeciesBaseHP\(([^)]*)\)\s*\{\s*return gSpeciesInfo\[SanitizeSpeciesId\([^)]*\)\]\.baseHP;\s*\}', s)
    if not m:
        print('!! GetSpeciesBaseHP 形式不同，跳过')
    else:
        argtype = m.group(1).strip()
        replacement = '''EWRAM_DATA u8 gBaseStatOverrideFlags[NUM_SPECIES];
EWRAM_DATA u8 gBaseStatOverride[NUM_SPECIES][NUM_STATS];

static void BaseStatOverrides_EnsureInit(u16 species)
{
    if (!gBaseStatOverrideFlags[species])
    {
        gBaseStatOverride[species][STAT_HP]    = gSpeciesInfo[species].baseHP;
        gBaseStatOverride[species][STAT_ATK]   = gSpeciesInfo[species].baseAttack;
        gBaseStatOverride[species][STAT_DEF]   = gSpeciesInfo[species].baseDefense;
        gBaseStatOverride[species][STAT_SPEED] = gSpeciesInfo[species].baseSpeed;
        gBaseStatOverride[species][STAT_SPATK] = gSpeciesInfo[species].baseSpAttack;
        gBaseStatOverride[species][STAT_SPDEF] = gSpeciesInfo[species].baseSpDefense;
        gBaseStatOverrideFlags[species] = TRUE;
    }
}

void BaseStatOverrides_LoadFromSave(void)
{
    memset(gBaseStatOverrideFlags, 0, sizeof(gBaseStatOverrideFlags));
    memset(gBaseStatOverride, 0, sizeof(gBaseStatOverride));
    if (gSaveBlock1Ptr == NULL)
        return;
    struct BaseStatSaveEntries *saved = &gSaveBlock1Ptr->baseStatEntries;
    if (saved->count > MAX_BASE_STAT_OVERRIDES)
    {
        saved->count = 0;
        return;
    }
    for (u32 i = 0; i < saved->count; i++)
    {
        u16 species = saved->entries[i].species;
        if (species >= NUM_SPECIES)
            continue;
        BaseStatOverrides_EnsureInit(species);
        for (u32 st = 0; st < NUM_STATS; st++)
            gBaseStatOverride[species][st] = saved->entries[i].stats[st];
    }
}

void BaseStatOverrides_Set(u16 species, u8 stat, u8 value)
{
    if (species >= NUM_SPECIES || stat >= NUM_STATS)
        return;
    BaseStatOverrides_EnsureInit(species);
    gBaseStatOverride[species][stat] = value;
    if (gSaveBlock1Ptr == NULL)
        return;
    struct BaseStatSaveEntries *saved = &gSaveBlock1Ptr->baseStatEntries;
    if (saved->count > MAX_BASE_STAT_OVERRIDES)
        saved->count = 0;
    for (u32 i = 0; i < saved->count; i++)
    {
        if (saved->entries[i].species == species)
        {
            for (u32 st = 0; st < NUM_STATS; st++)
                saved->entries[i].stats[st] = gBaseStatOverride[species][st];
            return;
        }
    }
    if (saved->count < MAX_BASE_STAT_OVERRIDES)
    {
        saved->entries[saved->count].species = species;
        for (u32 st = 0; st < NUM_STATS; st++)
            saved->entries[saved->count].stats[st] = gBaseStatOverride[species][st];
        saved->count++;
    }
}

u32 GetSpeciesBaseHP(''' + argtype + ''')
{
    u32 id = SanitizeSpeciesId(species);
    if (gBaseStatOverrideFlags[id])
        return gBaseStatOverride[id][STAT_HP];
    return gSpeciesInfo[id].baseHP;
}'''
        s = s[:m.start()] + replacement + s[m.end():]

        # 属性读取也走覆盖表
        m2 = re.search(r'u32 GetSpeciesBaseStat\(([^)]*)\)\s*\{', s)
        if m2:
            s = s[:m2.end()] + '''
    {
        u32 _id = SanitizeSpeciesId(species);
        if (gBaseStatOverrideFlags[_id] && statIndex < NUM_STATS)
            return gBaseStatOverride[_id][statIndex];
    }
''' + s[m2.end():]
        open(p, 'w', encoding='utf-8').write(s)
        print('pokemon.c ok')

    p = os.path.join(B, 'include/pokemon.h')
    s = open(p, encoding='utf-8').read()
    if 'BaseStatOverrides_Set' not in s:
        s = s.replace('u32 GetSpeciesBaseHP(', 'void BaseStatOverrides_LoadFromSave(void);\nvoid BaseStatOverrides_Set(u16 species, u8 stat, u8 value);\nu32 GetSpeciesBaseHP(', 1)
        open(p, 'w', encoding='utf-8').write(s)
        print('pokemon.h ok')

def patch_save_hook():
    p = os.path.join(B, 'src/save.c')
    s = open(p, encoding='utf-8').read()
    if 'BaseStatOverrides_LoadFromSave' in s:
        print('save.c already'); return
    s = s.replace('''        status = TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);''',
'''        status = TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);''', 1)
    # 在 gSaveFileStatus = status; 后插入
    s = re.sub(r'(status = TryLoadSaveSlot\(FULL_SAVE_SLOT, gRamSaveSectorLocations\);\n(\s*)CopyPartyAndObjectsFromSave\(\);\n\s*gSaveFileStatus = status;)',
               r'\1\n\2if (status == SAVE_STATUS_OK)\n\2    BaseStatOverrides_LoadFromSave();', s, count=1)
    if '#include "pokemon.h"' not in s:
        s = s.replace('#include "save.h"', '#include "save.h"\n#include "pokemon.h"', 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('save.c ok')

if __name__ == '__main__':
    patch_debug_cfg()
    patch_save_struct()
    patch_pokemon()
    patch_save_hook()
