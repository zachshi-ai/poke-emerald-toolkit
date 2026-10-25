import re
base = '/root/build/pokeemerald-expansion-master/'

# ---------- pokemon.c : add override tables ----------
p = base + 'src/pokemon.c'
s = open(p).read()
if 'gBaseStatOverrideFlags' not in s:
    anchor = 'u32 GetSpeciesBaseHP(enum Species species)\n'
    add = '''EWRAM_DATA u8 gBaseStatOverrideFlags[NUM_SPECIES];
EWRAM_DATA u8 gBaseStatOverride[NUM_SPECIES][NUM_STATS];

u32 GetSpeciesBaseHP(enum Species species)
{
    u32 id = SanitizeSpeciesId(species);
    if (gBaseStatOverrideFlags[id])
        return gBaseStatOverride[id][STAT_HP];
    return gSpeciesInfo[id].baseHP;
}

u32 GetSpeciesBaseHPOrig(enum Species species)
'''
    assert anchor in s
    s = s.replace(anchor, add, 1)

    # override inside GetSpeciesBaseStat
    old = '''u32 GetSpeciesBaseStat(enum Species species, u32 statIndex)
{
    switch (statIndex)'''
    new = '''u32 GetSpeciesBaseStat(enum Species species, u32 statIndex)
{
    u32 id = SanitizeSpeciesId(species);
    if (gBaseStatOverrideFlags[id] && statIndex < NUM_STATS)
        return gBaseStatOverride[id][statIndex];
    switch (statIndex)'''
    assert old in s
    s = s.replace(old, new, 1)
    open(p, 'w').write(s)
    print('pokemon.c patched')

# ---------- debug.c : base stat editor ----------
p = base + 'src/debug.c'
s = open(p).read()
if 'sSetBaseStatSelection' not in s:
    s = s.replace('static const struct DebugSelection sEditMovesSelection;\n',
                  'static const struct DebugSelection sEditMovesSelection;\n'
                  'static const struct DebugSelection sSetBaseStatSelection;\n', 1)

    s = s.replace('''    { COMPOUND_STRING("Time Functions…"),           DebugAction_OpenSubMenu, sDebugMenu_Actions_TimeMenu, },''',
'''    { COMPOUND_STRING("Base Stats…"),               DebugAction_Selection_Init, &sSetBaseStatSelection },
    { COMPOUND_STRING("Time Functions…"),           DebugAction_OpenSubMenu, sDebugMenu_Actions_TimeMenu, },''', 1)

    s = s.replace('extern const u8 Debug_EventScript_FontTest[];\n',
                  'extern const u8 Debug_EventScript_FontTest[];\n'
                  'extern u8 gBaseStatOverrideFlags[];\n'
                  'extern u8 gBaseStatOverride[][NUM_STATS];\n', 1)

    tail = '''static const struct DebugSelection sEditMovesSelection = {
    .onInit = Debug_CreateInputDisplayWindow,
    .onCancel = DebugSelectionStep_ReturnToGiveMenu,
    .onComplete = DebugSelection_EditMoves_Complete,
    .steps = {
        &sPartySlotSelectionStep,
        &sMoveSlotSelectionStep,
        &sMoveIdSelectionStep,
        &sMovePPSelectionStep,
    },
    .maxSteps = 4,
};
'''
    assert tail in s

    add = tail + '''
// ===== 种族值编辑（运行时覆盖，重启后恢复） =====
UPDATE_GENERIC_INPUT(BaseStatSpeciesX, Species)
UPDATE_GENERIC_INPUT(BaseStatIndexX, Stat 1-6)
UPDATE_GENERIC_INPUT(BaseStatValueX, Value)

static bool32 DebugSelection_SetBaseStat_Complete(u8 taskId)
{
    u32 species = DebugSelection_GetData(taskId, 0);
    u32 stat = DebugSelection_GetData(taskId, 1) - 1;
    u32 value = DebugSelection_GetData(taskId, 2);

    if (species >= NUM_SPECIES || stat >= NUM_STATS)
    {
        DebugSelectionStep_ReturnToGiveMenu(taskId);
        return TRUE;
    }
    if (!gBaseStatOverrideFlags[species])
    {
        gBaseStatOverride[species][STAT_HP]      = gSpeciesInfo[species].baseHP;
        gBaseStatOverride[species][STAT_ATK]     = gSpeciesInfo[species].baseAttack;
        gBaseStatOverride[species][STAT_DEF]     = gSpeciesInfo[species].baseDefense;
        gBaseStatOverride[species][STAT_SPEED]   = gSpeciesInfo[species].baseSpeed;
        gBaseStatOverride[species][STAT_SPATK]   = gSpeciesInfo[species].baseSpAttack;
        gBaseStatOverride[species][STAT_SPDEF]   = gSpeciesInfo[species].baseSpDefense;
    }
    gBaseStatOverride[species][stat] = value;
    gBaseStatOverrideFlags[species] = TRUE;

    for (u32 i = 0; i < PARTY_SIZE; i++)
    {
        if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES, NULL) != SPECIES_NONE)
            CalculateMonStats(&gPlayerParty[i]);
    }
    DebugSelectionStep_ReturnToGiveMenu(taskId);
    PlaySE(SE_SUCCESS);
    return TRUE;
}

static const struct DebugSelectionStep sBaseStatSpeciesStep = {
    .stepUpdate = DebugSelectionStep_UpdateBaseStatSpeciesX,
    .stepConfirm = DebugSelectionStep_GenericInputConfirm,
    .minValue = 1,
    .maxValue = NUM_SPECIES - 1,
    .digits = 4
};

static const struct DebugSelectionStep sBaseStatIndexStep = {
    .stepUpdate = DebugSelectionStep_UpdateBaseStatIndexX,
    .stepConfirm = DebugSelectionStep_GenericInputConfirm,
    .minValue = 1,
    .maxValue = NUM_STATS,
    .digits = 1
};

static const struct DebugSelectionStep sBaseStatValueStep = {
    .stepUpdate = DebugSelectionStep_UpdateBaseStatValueX,
    .stepConfirm = DebugSelectionStep_GenericInputConfirm,
    .minValue = 1,
    .maxValue = 255,
    .digits = 3
};

static const struct DebugSelection sSetBaseStatSelection = {
    .onInit = Debug_CreateInputDisplayWindow,
    .onCancel = DebugSelectionStep_ReturnToGiveMenu,
    .onComplete = DebugSelection_SetBaseStat_Complete,
    .steps = {
        &sBaseStatSpeciesStep,
        &sBaseStatIndexStep,
        &sBaseStatValueStep,
    },
    .maxSteps = 3,
};
'''
    s = s.replace(tail, add, 1)
    open(p, 'w').write(s)
    print('debug.c patched')
