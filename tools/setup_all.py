#!/usr/bin/env python3
# 从原始源码重建，并重新应用全部功能补丁（不包含批量机翻）
import os, re, shutil, subprocess

BASE = '/root/build/pokeemerald-expansion-master'
PRI = '/root/build/pristine2'

def restore():
    for d in ('src', 'include'):
        dst = os.path.join(BASE, d)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(os.path.join(PRI, d), dst)
    shutil.copy2(os.path.join(PRI, 'charmap.txt'), os.path.join(BASE, 'charmap.txt'))
    print('restored src/include/charmap')

def patch_global_h():
    p = os.path.join(BASE, 'include/global.h')
    s = open(p, encoding='utf-8').read()
    if 'BaseStatSaveEntries' in s:
        return
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
    print('global.h patched')

def patch_pokemon():
    p = os.path.join(BASE, 'src/pokemon.c')
    s = open(p, encoding='utf-8').read()
    if 'BaseStatOverrides_LoadFromSave' not in s:
        anchor = 'u32 GetSpeciesBaseHP(enum Species species)'
        add = '''EWRAM_DATA u8 gBaseStatOverrideFlags[NUM_SPECIES];
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

u32 GetSpeciesBaseHP(enum Species species)'''
        s = s.replace(anchor, add, 1)
        s = s.replace('''    return gSpeciesInfo[SanitizeSpeciesId(species)].baseHP;
}''', '''    {
        u32 id = SanitizeSpeciesId(species);
        if (gBaseStatOverrideFlags[id])
            return gBaseStatOverride[id][STAT_HP];
    }
    return gSpeciesInfo[SanitizeSpeciesId(species)].baseHP;
}''', 1)
        s = s.replace('''u32 GetSpeciesBaseStat(enum Species species, u32 statIndex)
{
    switch (statIndex)''', '''u32 GetSpeciesBaseStat(enum Species species, u32 statIndex)
{
    u32 id = SanitizeSpeciesId(species);
    if (gBaseStatOverrideFlags[id] && statIndex < NUM_STATS)
        return gBaseStatOverride[id][statIndex];
    switch (statIndex)''', 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('pokemon.c patched')

    # 性格中文
    natures = {'Hardy': '勤奋', 'Lonely': '怕寂寞', 'Brave': '勇敢', 'Adamant': '固执', 'Naughty': '顽皮',
               'Bold': '大胆', 'Docile': '坦率', 'Relaxed': '悠闲', 'Impish': '淘气', 'Lax': '乐天',
               'Timid': '胆小', 'Hasty': '急躁', 'Serious': '认真', 'Jolly': '爽朗', 'Naive': '天真',
               'Modest': '内敛', 'Mild': '慢吞吞', 'Quiet': '冷静', 'Bashful': '害羞', 'Rash': '马虎',
               'Calm': '温和', 'Gentle': '温柔', 'Sassy': '自大', 'Careful': '慎重', 'Quirky': '浮躁'}
    s = open(p, encoding='utf-8').read()
    for en, zh in natures.items():
        s = s.replace('.name = COMPOUND_STRING("%s")' % en, '.name = COMPOUND_STRING("%s")' % zh)
    open(p, 'w', encoding='utf-8').write(s)

    p = os.path.join(BASE, 'include/pokemon.h')
    s = open(p, encoding='utf-8').read()
    if 'BaseStatOverrides_Set' not in s:
        s = s.replace('u32 GetSpeciesBaseHP(enum Species species);',
                      'u32 GetSpeciesBaseHP(enum Species species);\nvoid BaseStatOverrides_LoadFromSave(void);\nvoid BaseStatOverrides_Set(u16 species, u8 stat, u8 value);', 1)
        open(p, 'w', encoding='utf-8').write(s)
    print('pokemon.h patched')

def patch_save_c():
    p = os.path.join(BASE, 'src/save.c')
    s = open(p, encoding='utf-8').read()
    if 'BaseStatOverrides_LoadFromSave' in s:
        return
    s = s.replace('''        status = TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);
        CopyPartyAndObjectsFromSave();
        gSaveFileStatus = status;''', '''        status = TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);
        CopyPartyAndObjectsFromSave();
        gSaveFileStatus = status;
        if (status == SAVE_STATUS_OK)
            BaseStatOverrides_LoadFromSave();''', 1)
    if '#include "pokemon.h"' not in s:
        s = s.replace('#include "save.h"', '#include "save.h"\n#include "pokemon.h"', 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('save.c patched')

def patch_text_c():
    p = os.path.join(BASE, 'src/text.c')
    s = open(p, encoding='utf-8').read()
    if 'gCjkGlyphs' not in s:
        block = '''
extern const u16 gCjkGlyphs[];
#define CJK_LEAD_MIN 0x01
#define CJK_LEAD_MAX 0x10

static void CjkLoadHalf(u16 idx, u32 half)
{
    const u16 *src = &gCjkGlyphs[((u32) idx << 5) + (half << 4)];
    DecompressGlyphTile(src, gCurGlyph.gfxBufferTop);
    DecompressGlyphTile(src + 8, gCurGlyph.gfxBufferBottom);
    gCurGlyph.width = 8;
    gCurGlyph.height = 16;
}
'''
        s = s.replace('IWRAM_DATA struct TextGlyph gCurGlyph = {0};',
                      'IWRAM_DATA struct TextGlyph gCurGlyph = {0};\n' + block, 1)
        s = s.replace('''        switch (currChar)
        {
        case CHAR_NEWLINE:''', '''        if (currChar >= CJK_LEAD_MIN && currChar <= CJK_LEAD_MAX)
        {
            u16 cjkIdx = ((u16) (currChar - CJK_LEAD_MIN) << 8) | *textPrinter->printerTemplate.currentChar++;
            CjkLoadHalf(cjkIdx, 0);
            PrintGlyph(textPrinter);
            CjkLoadHalf(cjkIdx, 1);
            PrintGlyph(textPrinter);
            return RENDER_PRINT;
        }

        switch (currChar)
        {
        case CHAR_NEWLINE:''', 1)
        s = s.replace('''        default:
            glyphWidth = func(*str, isJapanese);''', '''        default:
            if (*str >= CJK_LEAD_MIN && *str <= CJK_LEAD_MAX)
            {
                lineWidth += 16;
                ++str;
                break;
            }
            glyphWidth = func(*str, isJapanese);''', 1)
        open(p, 'w', encoding='utf-8').write(s)
        print('text.c patched')

def patch_debug_config():
    p = os.path.join(BASE, 'include/config/debug.h')
    s = open(p, encoding='utf-8').read()
    s = s.replace('#define DEBUG_OVERWORLD_MENU            DISABLED_ON_RELEASE', '#define DEBUG_OVERWORLD_MENU            TRUE')
    s = s.replace('#define DEBUG_OVERWORLD_IN_MENU         FALSE', '#define DEBUG_OVERWORLD_IN_MENU         TRUE')
    s = s.replace('#define DEBUG_BATTLE_MENU               DISABLED_ON_RELEASE', '#define DEBUG_BATTLE_MENU               TRUE')
    open(p, 'w', encoding='utf-8').write(s)
    print('debug config patched')

if __name__ == '__main__':
    restore()
    patch_global_h()
    patch_pokemon()
    patch_save_c()
    patch_text_c()
    patch_debug_config()
    for script in ('patch_debug.py', 'patch_debug2.py'):
        r = subprocess.run(['python3', '/root/build/' + script], capture_output=True, text=True)
        print(script, r.stdout.strip(), r.stderr.strip()[:200])
