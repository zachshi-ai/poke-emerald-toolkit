package com.stepx.pokeemerald;

/**
 * 宝可梦仓库：直接读写模拟器内存里的队伍(gPlayerParty)与电脑箱子(PokemonStorage)，
 * 实现队伍与箱子之间的快速互转（引擎的 6 只上场上限不变，但可以随时轮换）。
 */
public class PokemonBox {

    // 由 assets/mem.cfg 注入
    public static int PARTY_ADDR = 0x02034A90;   // gPlayerParty
    public static int STORAGE_PTR_ADDR = 0x030051CC; // gPokemonStoragePtr（指针）
    public static final int POKEMON_SIZE = 100;
    public static final int BOXMON_SIZE = 80;
    public static final int PARTY_SIZE = 6;
    public static final int BOX_COUNT = 14;
    public static final int IN_BOX_COUNT = 30;
    public static final int BOXES_OFFSET = 1;    // struct PokemonStorage: u8 currentBox; boxes[...]

    private final GameView view;

    public PokemonBox(GameView view) {
        this.view = view;
    }

    public static void loadConfig(String cfg) {
        for (String line : cfg.split("\n")) {
            String[] kv = line.trim().split("=");
            if (kv.length != 2) continue;
            String k = kv[0].trim();
            int v;
            try {
                v = kv[1].trim().startsWith("0x")
                        ? (int) Long.parseLong(kv[1].trim().substring(2), 16)
                        : Integer.parseInt(kv[1].trim());
            } catch (Throwable t) {
                continue;
            }
            if (k.equals("party")) PARTY_ADDR = v;
            else if (k.equals("storage")) STORAGE_PTR_ADDR = v;
        }
    }

    public int storageBase() {
        byte[] b = view.readMem(STORAGE_PTR_ADDR, 4);
        if (b == null) return 0;
        return (b[0] & 0xFF) | ((b[1] & 0xFF) << 8) | ((b[2] & 0xFF) << 16) | ((b[3] & 0xFF) << 24);
    }

    public int partyAddr(int slot) {
        return PARTY_ADDR + slot * POKEMON_SIZE;
    }

    public int boxAddr(int box, int pos) {
        int base = storageBase();
        if (base == 0) return 0;
        return base + BOXES_OFFSET + (box * IN_BOX_COUNT + pos) * BOXMON_SIZE;
    }

    public byte[] readParty(int slot) {
        return view.readMem(partyAddr(slot), POKEMON_SIZE);
    }

    public byte[] readBox(int box, int pos) {
        int a = boxAddr(box, pos);
        return a == 0 ? null : view.readMem(a, BOXMON_SIZE);
    }

    /** 队伍槽位是否为空：空槽整块为 0（personality/otId 都为 0 且无物种） */
    public boolean isEmptySlot(byte[] mon) {
        if (mon == null) return true;
        for (int i = 0; i < 8; i++) if (mon[i] != 0) return false;
        return true;
    }

    /** 读等级（Pokemon 结构里 level 在 0x54） */
    public int levelOf(byte[] mon) {
        if (mon == null || mon.length < 0x56) return 0;
        return mon[0x54] & 0xFF;
    }

    /** 读当前 HP（0x56，u16） */
    public int hpOf(byte[] mon) {
        if (mon == null || mon.length < 0x59) return 0;
        return (mon[0x56] & 0xFF) | ((mon[0x57] & 0xFF) << 8);
    }

    /** 队伍 → 箱子：把队伍第 slot 只存进箱子指定位置（整块复制） */
    public boolean partyToBox(int slot, int box, int pos) {
        byte[] mon = readParty(slot);
        if (mon == null || isEmptySlot(mon)) return false;
        byte[] boxMon = new byte[BOXMON_SIZE];
        System.arraycopy(mon, 0, boxMon, 0, BOXMON_SIZE);
        int a = boxAddr(box, pos);
        if (a == 0) return false;
        if (!view.writeMem(a, boxMon)) return false;
        // 清空队伍槽
        return view.writeMem(partyAddr(slot), new byte[POKEMON_SIZE]);
    }

    /** 箱子 → 队伍：整块复制（Pokemon = BoxPokemon(80) + 状态/等级/HP 等 20 字节，等级与 HP 需要重算，这里简单置 0 交由游戏读档/战斗重算） */
    public boolean boxToParty(int box, int pos, int slot) {
        byte[] boxMon = readBox(box, pos);
        if (boxMon == null || isEmptySlot(boxMon)) return false;
        byte[] mon = new byte[POKEMON_SIZE];
        System.arraycopy(boxMon, 0, mon, 0, BOXMON_SIZE);
        int a = partyAddr(slot);
        return view.writeMem(a, mon);
    }

    /** 队伍内部交换两只 */
    public boolean swapParty(int a, int b) {
        byte[] ma = readParty(a);
        byte[] mb = readParty(b);
        if (ma == null || mb == null) return false;
        return view.writeMem(partyAddr(a), mb) && view.writeMem(partyAddr(b), ma);
    }

    /** 队伍与箱子互换 */
    public boolean swapPartyBox(int slot, int box, int pos) {
        byte[] mon = readParty(slot);
        byte[] boxMon = readBox(box, pos);
        if (mon == null || boxMon == null) return false;
        byte[] newBox = new byte[BOXMON_SIZE];
        System.arraycopy(mon, 0, newBox, 0, BOXMON_SIZE);
        byte[] newMon = new byte[POKEMON_SIZE];
        System.arraycopy(boxMon, 0, newMon, 0, BOXMON_SIZE);
        int a = boxAddr(box, pos);
        boolean ok = view.writeMem(a, newBox) && view.writeMem(partyAddr(slot), newMon);
        if (ok) {
            // 箱子里的宝可梦不带等级/HP 字段，换进队伍后会变成 0 级，回滚以免损坏存档
            byte[] check = readParty(slot);
            if (check != null && (check[0x54] & 0xFF) == 0) {
                view.writeMem(partyAddr(slot), mon);
                view.writeMem(a, boxMon);
                return false;
            }
        }
        return ok;
    }

    /** 把箱子某只复制到队伍空位（队伍满则失败） */
    public int copyBoxToFirstFreeParty(int box, int pos) {
        byte[] boxMon = readBox(box, pos);
        if (boxMon == null || isEmptySlot(boxMon)) return -1;
        for (int i = 0; i < PARTY_SIZE; i++) {
            if (isEmptySlot(readParty(i))) {
                byte[] mon = new byte[POKEMON_SIZE];
                System.arraycopy(boxMon, 0, mon, 0, BOXMON_SIZE);
                if (view.writeMem(partyAddr(i), mon)) return i;
                return -1;
            }
        }
        return -1;
    }

    /** 把整箱导出到文件（2400 字节 = 30 只 × 80 字节） */
    public boolean exportBox(int box, java.io.File out) {
        byte[] buf = new byte[IN_BOX_COUNT * BOXMON_SIZE];
        for (int i = 0; i < IN_BOX_COUNT; i++) {
            byte[] mon = readBox(box, i);
            if (mon == null) return false;
            System.arraycopy(mon, 0, buf, i * BOXMON_SIZE, BOXMON_SIZE);
        }
        try {
            java.io.FileOutputStream fos = new java.io.FileOutputStream(out);
            fos.write(buf);
            fos.close();
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    /** 从文件导入到整箱 */
    public boolean importBox(int box, java.io.File in) {
        try {
            byte[] buf = new byte[IN_BOX_COUNT * BOXMON_SIZE];
            java.io.FileInputStream fis = new java.io.FileInputStream(in);
            int off = 0, r;
            while (off < buf.length && (r = fis.read(buf, off, buf.length - off)) > 0) off += r;
            fis.close();
            if (off < buf.length) return false;
            for (int i = 0; i < IN_BOX_COUNT; i++) {
                byte[] mon = new byte[BOXMON_SIZE];
                System.arraycopy(buf, i * BOXMON_SIZE, mon, 0, BOXMON_SIZE);
                int a = boxAddr(box, i);
                if (a == 0) return false;
                if (!view.writeMem(a, mon)) return false;
            }
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    /** 队伍概况文本 */
    public String partySummary() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < PARTY_SIZE; i++) {
            byte[] mon = readParty(i);
            boolean empty = isEmptySlot(mon);
            sb.append("槽位 ").append(i + 1).append("：");
            if (empty) {
                sb.append("空");
            } else {
                sb.append("等级 ").append(levelOf(mon)).append("，HP ").append(hpOf(mon));
            }
            sb.append('\n');
        }
        return sb.toString();
    }

    /** 箱子概况 */
    public String boxSummary(int box) {
        int n = 0;
        for (int i = 0; i < IN_BOX_COUNT; i++) {
            if (!isEmptySlot(readBox(box, i))) n++;
        }
        return "第 " + (box + 1) + " 号箱子：" + n + " / " + IN_BOX_COUNT + " 只";
    }
}
