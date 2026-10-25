import re, shutil

P = '/root/build/pe_zh/src/debug.c'
shutil.copy2(P, '/root/build/bak_pe_zh_debug.c')
s = open(P, encoding='utf-8').read()

DECL = '''
static void DebugAction_SetItemQty(u8 taskId);
static void DebugAction_SetItemQty_SelectId(u8 taskId);
static void DebugAction_SetItemQty_SelectQty(u8 taskId);
static void DebugAction_EditMovePP(u8 taskId);
static void DebugAction_EditMovePP_Party(u8 taskId);
static void DebugAction_EditMovePP_Slot(u8 taskId);
static void DebugAction_EditMovePP_Move(u8 taskId);
static void DebugAction_EditMovePP_PP(u8 taskId);
static void DebugAction_SetBaseStat(u8 taskId);
static void DebugAction_SetBaseStat_Species(u8 taskId);
static void DebugAction_SetBaseStat_Index(u8 taskId);
static void DebugAction_SetBaseStat_Value(u8 taskId);
'''

if 'DebugAction_SetItemQty' not in s:
    s = s.replace('static void DebugAction_Give_Item(u8 taskId);',
                  'static void DebugAction_Give_Item(u8 taskId);\n' + DECL, 1)

# 菜单项
if '设定道具数量…' not in s:
    s = s.replace('    { COMPOUND_STRING("清空背包"),           DebugAction_PCBag_ClearBag },',
                  '    { COMPOUND_STRING("设定道具数量…"),      DebugAction_SetItemQty },\n'
                  '    { COMPOUND_STRING("清空背包"),           DebugAction_PCBag_ClearBag },', 1)

if '修改技能与PP…' not in s:
    s = s.replace('    { COMPOUND_STRING("清空同行宝可梦"),        DebugAction_Party_ClearParty },',
                  '    { COMPOUND_STRING("修改技能与PP…"),      DebugAction_EditMovePP },\n'
                  '    { COMPOUND_STRING("种族值编辑…"),        DebugAction_SetBaseStat },\n'
                  '    { COMPOUND_STRING("清空同行宝可梦"),        DebugAction_Party_ClearParty },', 1)

IMPL = r'''
// ===== StepClaw 修改器扩展 =====
static void Debug_ShowNumber(u32 value, u32 digits, u8 windowId)
{
    ConvertIntToDecimalStringN(gStringVar1, value, STR_CONV_MODE_LEADING_ZEROS, digits);
    StringCopyPadded(gStringVar1, gStringVar1, CHAR_SPACE, 20);
    AddTextPrinterParameterized(windowId, DEBUG_MENU_FONT, gStringVar1, 0, 0, 0, NULL);
}

static void Debug_OpenExtraWindow(u8 taskId)
{
    u8 windowId;

    ClearStdWindowAndFrame(gTasks[taskId].tWindowId, TRUE);
    RemoveWindow(gTasks[taskId].tWindowId);
    HideMapNamePopUpWindow();
    LoadMessageBoxAndBorderGfx();
    windowId = AddWindow(&sDebugMenuWindowTemplateExtra);
    DrawStdWindowFrame(windowId, FALSE);
    CopyWindowToVram(windowId, COPYWIN_FULL);
    gTasks[taskId].tSubWindowId = windowId;
}

static void Debug_FinishExtra(u8 taskId)
{
    PlaySE(SE_SELECT);
    DebugAction_DestroyExtraWindow(taskId);
}

// --- 设定道具数量 ---
static void DebugAction_SetItemQty(u8 taskId)
{
    Debug_OpenExtraWindow(taskId);
    gTasks[taskId].tInput = 1;
    gTasks[taskId].tDigit = 0;
    Debug_ShowNumber(1, DEBUG_NUMBER_DIGITS_ITEMS, gTasks[taskId].tSubWindowId);
    gTasks[taskId].func = DebugAction_SetItemQty_SelectId;
}

static void DebugAction_SetItemQty_SelectId(u8 taskId)
{
    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 1, ITEMS_COUNT - 1, DEBUG_NUMBER_DIGITS_ITEMS);
        Debug_ShowNumber(gTasks[taskId].tInput, DEBUG_NUMBER_DIGITS_ITEMS, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        gTasks[taskId].tItemId = gTasks[taskId].tInput;
        gTasks[taskId].tInput = 1;
        gTasks[taskId].tDigit = 0;
        Debug_ShowNumber(1, MAX_ITEM_DIGITS, gTasks[taskId].tSubWindowId);
        gTasks[taskId].func = DebugAction_SetItemQty_SelectQty;
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

static void DebugAction_SetItemQty_SelectQty(u8 taskId)
{
    enum Item itemId = gTasks[taskId].tItemId;

    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 1, MAX_BAG_ITEM_CAPACITY, MAX_ITEM_DIGITS);
        Debug_ShowNumber(gTasks[taskId].tInput, MAX_ITEM_DIGITS, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        u16 qty = gTasks[taskId].tInput;
        u32 guard = 0;

        while (CheckBagHasItem(itemId, 1) && guard++ < 200)
        {
            if (!RemoveBagItem(itemId, 999))
                break;
        }
        AddBagItem(itemId, qty);
        PlaySE(MUS_LEVEL_UP);
        Debug_FinishExtra(taskId);
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

// --- 修改技能与 PP ---
static void DebugAction_EditMovePP(u8 taskId)
{
    Debug_OpenExtraWindow(taskId);
    gTasks[taskId].tInput = 1;
    gTasks[taskId].tDigit = 0;
    Debug_ShowNumber(1, 1, gTasks[taskId].tSubWindowId);
    gTasks[taskId].func = DebugAction_EditMovePP_Party;
}

static void DebugAction_EditMovePP_Party(u8 taskId)
{
    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 1, PARTY_SIZE, 1);
        Debug_ShowNumber(gTasks[taskId].tInput, 1, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        gTasks[taskId].tPartyId = gTasks[taskId].tInput - 1;
        gTasks[taskId].tInput = 1;
        gTasks[taskId].tDigit = 0;
        Debug_ShowNumber(1, 1, gTasks[taskId].tSubWindowId);
        gTasks[taskId].func = DebugAction_EditMovePP_Slot;
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

static void DebugAction_EditMovePP_Slot(u8 taskId)
{
    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 1, MAX_MON_MOVES, 1);
        Debug_ShowNumber(gTasks[taskId].tInput, 1, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        gTasks[taskId].tMoveSlot = gTasks[taskId].tInput - 1;
        gTasks[taskId].tInput = 1;
        gTasks[taskId].tDigit = 0;
        Debug_ShowNumber(1, 4, gTasks[taskId].tSubWindowId);
        gTasks[taskId].func = DebugAction_EditMovePP_Move;
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

static void DebugAction_EditMovePP_Move(u8 taskId)
{
    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 1, MOVES_COUNT - 1, 4);
        Debug_ShowNumber(gTasks[taskId].tInput, 4, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        gTasks[taskId].tMoveId = gTasks[taskId].tInput;
        gTasks[taskId].tInput = 1;
        gTasks[taskId].tDigit = 0;
        Debug_ShowNumber(1, 2, gTasks[taskId].tSubWindowId);
        gTasks[taskId].func = DebugAction_EditMovePP_PP;
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

static void DebugAction_EditMovePP_PP(u8 taskId)
{
    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 0, 64, 2);
        Debug_ShowNumber(gTasks[taskId].tInput, 2, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        struct Pokemon *mon = &gPlayerParty[gTasks[taskId].tPartyId];
        u16 move = gTasks[taskId].tMoveId;
        u8 pp = gTasks[taskId].tInput;

        if (GetMonData(mon, MON_DATA_SPECIES, NULL) != SPECIES_NONE && move < MOVES_COUNT)
        {
            if (pp == 0 || pp > gMovesInfo[move].pp)
                pp = gMovesInfo[move].pp;
            SetMonData(mon, MON_DATA_MOVE1 + gTasks[taskId].tMoveSlot, &move);
            SetMonData(mon, MON_DATA_PP1 + gTasks[taskId].tMoveSlot, &pp);
            CalculateMonStats(mon);
        }
        PlaySE(MUS_LEVEL_UP);
        Debug_FinishExtra(taskId);
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

// --- 种族值编辑 ---
static void DebugAction_SetBaseStat(u8 taskId)
{
    Debug_OpenExtraWindow(taskId);
    gTasks[taskId].tInput = 1;
    gTasks[taskId].tDigit = 0;
    Debug_ShowNumber(1, 4, gTasks[taskId].tSubWindowId);
    gTasks[taskId].func = DebugAction_SetBaseStat_Species;
}

static void DebugAction_SetBaseStat_Species(u8 taskId)
{
    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 1, NUM_SPECIES - 1, 4);
        Debug_ShowNumber(gTasks[taskId].tInput, 4, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        gTasks[taskId].tSpeciesId = gTasks[taskId].tInput;
        gTasks[taskId].tInput = 1;
        gTasks[taskId].tDigit = 0;
        Debug_ShowNumber(1, 1, gTasks[taskId].tSubWindowId);
        gTasks[taskId].func = DebugAction_SetBaseStat_Index;
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

static void DebugAction_SetBaseStat_Index(u8 taskId)
{
    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 1, NUM_STATS, 1);
        Debug_ShowNumber(gTasks[taskId].tInput, 1, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        gTasks[taskId].tStatIndex = gTasks[taskId].tInput - 1;
        gTasks[taskId].tInput = 1;
        gTasks[taskId].tDigit = 0;
        Debug_ShowNumber(1, 3, gTasks[taskId].tSubWindowId);
        gTasks[taskId].func = DebugAction_SetBaseStat_Value;
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

static void DebugAction_SetBaseStat_Value(u8 taskId)
{
    if (JOY_NEW(DPAD_ANY))
    {
        PlaySE(SE_SELECT);
        Debug_HandleInput_Numeric(taskId, 1, 255, 3);
        Debug_ShowNumber(gTasks[taskId].tInput, 3, gTasks[taskId].tSubWindowId);
    }
    if (JOY_NEW(A_BUTTON))
    {
        u32 i;

        BaseStatOverrides_Set((u16) gTasks[taskId].tSpeciesId, (u8) gTasks[taskId].tStatIndex, (u8) gTasks[taskId].tInput);
        for (i = 0; i < PARTY_SIZE; i++)
        {
            if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES, NULL) != SPECIES_NONE)
                CalculateMonStats(&gPlayerParty[i]);
        }
        PlaySE(MUS_LEVEL_UP);
        Debug_FinishExtra(taskId);
    }
    else if (JOY_NEW(B_BUTTON))
    {
        Debug_FinishExtra(taskId);
    }
}

'''

anchor = 'static void DebugAction_Sound_SE(u8 taskId)\n{'
if 'StepClaw 修改器扩展' not in s:
    s = s.replace(anchor, IMPL + anchor, 1)

open(P, 'w', encoding='utf-8').write(s)
print('debug.c patched, size', len(s))
