import re, sys

p = '/root/build/pokeemerald-expansion-master/src/debug.c'
s = open(p).read()
orig = s

# 1) includes
s = s.replace('#include "menu.h"\n', '#include "menu.h"\n#include "move.h"\n', 1)
if '#include "constants/moves.h"' not in s:
    s = s.replace('#include "constants/items.h"\n', '#include "constants/items.h"\n#include "constants/moves.h"\n', 1)

# 2) forward declarations
anchor = 'static const struct DebugSelection sPartnerSelection;\n'
if 'sSetItemQuantitySelection' not in s:
    s = s.replace(anchor, anchor +
        'static const struct DebugSelection sSetItemQuantitySelection;\n'
        'static const struct DebugSelection sEditMovesSelection;\n', 1)

# 3) menu entries
s = s.replace('''    { COMPOUND_STRING("Clear Bag"),           DebugAction_PCBag_ClearBag },''',
'''    { COMPOUND_STRING("Set Item Qty…"),       DebugAction_Selection_Init, &sSetItemQuantitySelection },
    { COMPOUND_STRING("Clear Bag"),           DebugAction_PCBag_ClearBag },''', 1)

s = s.replace('''    { COMPOUND_STRING("Edit Pokemon"),       DebugAction_OpenSubMenu, sDebugMenu_Actions_EditPokemon },''',
'''    { COMPOUND_STRING("Edit Pokemon"),       DebugAction_OpenSubMenu, sDebugMenu_Actions_EditPokemon },
    { COMPOUND_STRING("Edit moves/PP…"),     DebugAction_Selection_Init, &sEditMovesSelection },''', 1)

# 4) new selections right after sGiveItemSelection definition
give_block = '''static const struct DebugSelection sGiveItemSelection = {
    .onInit = Debug_CreateInputDisplayWindow,
    .onCancel = DebugSelectionStep_ReturnToGiveMenu,
    .onComplete = DebugSelection_GiveItem_Complete,
    .steps = {&sItemSelectionStep, &sQuantitySelectionStep},
    .maxSteps = 2,
};
'''
assert give_block in s, "give block not found"

addition = give_block + '''
// ===== StepClaw 修改器扩展：道具数量 / 队伍技能与 PP =====
UPDATE_GENERIC_INPUT(PartySlotX, Party Slot)
UPDATE_GENERIC_INPUT(MoveSlotX, Move Slot)
UPDATE_GENERIC_INPUT(MoveIdX, Move ID)
UPDATE_GENERIC_INPUT(MovePPX, PP)

static bool32 DebugSelection_SetItemQuantity_Complete(u8 taskId)
{
    u16 itemId = DebugSelection_GetData(taskId, 0);
    u16 qty = DebugSelection_GetData(taskId, 1);
    for (u32 p = 0; p < POCKETS_COUNT; p++)
    {
        struct BagPocket *pocket = &gBagPockets[p];
        for (u32 i = 0; i < pocket->capacity; i++)
        {
            if (pocket->itemSlots[i].itemId == itemId)
            {
                BagPocket_SetSlotItemIdAndCount(pocket, i, itemId, qty);
                DebugSelectionStep_ReturnToGiveMenu(taskId);
                PlaySE(SE_SUCCESS);
                return TRUE;
            }
        }
    }
    AddBagItem(itemId, qty);
    DebugSelectionStep_ReturnToGiveMenu(taskId);
    PlaySE(SE_SUCCESS);
    return TRUE;
}

static const struct DebugSelection sSetItemQuantitySelection = {
    .onInit = Debug_CreateInputDisplayWindow,
    .onCancel = DebugSelectionStep_ReturnToGiveMenu,
    .onComplete = DebugSelection_SetItemQuantity_Complete,
    .steps = {&sItemSelectionStep, &sQuantitySelectionStep},
    .maxSteps = 2,
};

static const struct DebugSelectionStep sPartySlotSelectionStep = {
    .stepUpdate = DebugSelectionStep_UpdatePartySlotX,
    .stepConfirm = DebugSelectionStep_GenericInputConfirm,
    .minValue = 1,
    .maxValue = PARTY_SIZE,
    .digits = 1
};

static const struct DebugSelectionStep sMoveSlotSelectionStep = {
    .stepUpdate = DebugSelectionStep_UpdateMoveSlotX,
    .stepConfirm = DebugSelectionStep_GenericInputConfirm,
    .minValue = 1,
    .maxValue = MAX_MON_MOVES,
    .digits = 1
};

static const struct DebugSelectionStep sMoveIdSelectionStep = {
    .stepUpdate = DebugSelectionStep_UpdateMoveIdX,
    .stepConfirm = DebugSelectionStep_GenericInputConfirm,
    .minValue = 1,
    .maxValue = MOVES_COUNT - 1,
    .digits = 4
};

static const struct DebugSelectionStep sMovePPSelectionStep = {
    .stepUpdate = DebugSelectionStep_UpdateMovePPX,
    .stepConfirm = DebugSelectionStep_GenericInputConfirm,
    .minValue = 0,
    .maxValue = 64,
    .digits = 2
};

static bool32 DebugSelection_EditMoves_Complete(u8 taskId)
{
    u32 partyIdx = DebugSelection_GetData(taskId, 0) - 1;
    u32 slot = DebugSelection_GetData(taskId, 1) - 1;
    u16 move = DebugSelection_GetData(taskId, 2);
    u16 pp = DebugSelection_GetData(taskId, 3);
    struct Pokemon *mon = &gPlayerParty[partyIdx];

    if (GetMonData(mon, MON_DATA_SPECIES, NULL) == SPECIES_NONE)
    {
        DebugSelectionStep_ReturnToGiveMenu(taskId);
        return TRUE;
    }
    if (move >= MOVES_COUNT)
    {
        DebugSelectionStep_ReturnToGiveMenu(taskId);
        return TRUE;
    }
    if (pp == 0 || pp > gMovesInfo[move].pp)
        pp = gMovesInfo[move].pp;

    u8 maxPP = gMovesInfo[move].pp;
    SetMonData(mon, MON_DATA_MOVE1 + slot, &move);
    SetMonData(mon, MON_DATA_PP1 + slot, &pp);
    {
        u8 ppUps = 0;
        SetMonData(mon, MON_DATA_PP_BONUSES, &ppUps);
    }
    CalculateMonStats(mon);
    DebugSelectionStep_ReturnToGiveMenu(taskId);
    PlaySE(SE_SUCCESS);
    return TRUE;
}

static const struct DebugSelection sEditMovesSelection = {
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
s = s.replace(give_block, addition, 1)

# 5) remove unused variable warning workaround
s = s.replace('''    u8 maxPP = gMovesInfo[move].pp;
    SetMonData''', '''    SetMonData''', 1)

open(p, 'w').write(s)
print("patched", len(s) - len(orig), "bytes added")
