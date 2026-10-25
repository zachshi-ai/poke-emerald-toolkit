#!/usr/bin/env python3
# 中文点阵字库 + charmap 生成器
import os, re, json, sys
from PIL import Image, ImageDraw, ImageFont

BASE = '/root/build/pokeemerald-expansion-master'
FONT_PATH = '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc'
if not os.path.exists(FONT_PATH):
    for root, dirs, files in os.walk('/usr/share/fonts'):
        for f in files:
            if 'CJK' in f and f.endswith(('.ttc', '.otf', '.ttf')):
                FONT_PATH = os.path.join(root, f); break
        if os.path.exists(FONT_PATH): break
print('font:', FONT_PATH)

# 第一批翻译：文件内精确替换
TRANS = {
    'src/main_menu.c': [
        ('_("NEW GAME")', '_("新游戏")'),
        ('_("CONTINUE")', '_("继续")'),
        ('_("OPTION")', '_("设置")'),
    ],
    'src/battle_message.c': [
        ('_("Battle{CLEAR_TO 56}Bag\\nPokémon{CLEAR_TO 56}Run")',
         '_("战斗{CLEAR_TO 56}背包\\n宝可梦{CLEAR_TO 56}逃跑")'),
    ],
    'src/start_menu.c': [
        ('_("DEBUG")', '_("调试")'),
    ],
    'src/strings.c': [
        ('const u8 gText_MenuPokedex[] = _("POKéDEX");', 'const u8 gText_MenuPokedex[] = _("图鉴");'),
        ('const u8 gText_MenuPokemon[] = _("POKéMON");', 'const u8 gText_MenuPokemon[] = _("宝可梦");'),
        ('const u8 gText_MenuBag[] = _("BAG");', 'const u8 gText_MenuBag[] = _("背包");'),
        ('const u8 gText_MenuPokenav[] = _("POKéNAV");', 'const u8 gText_MenuPokenav[] = _("导航");'),
        ('const u8 gText_MenuSave[] = _("SAVE");', 'const u8 gText_MenuSave[] = _("存档");'),
        ('const u8 gText_MenuOption[] = _("OPTION");', 'const u8 gText_MenuOption[] = _("设置");'),
        ('const u8 gText_MenuExit[] = _("EXIT");', 'const u8 gText_MenuExit[] = _("退出");'),
        ('const u8 gText_MenuRetire[] = _("RETIRE");', 'const u8 gText_MenuRetire[] = _("撤退");'),
        ('const u8 gText_MenuDexNav[] = _("DEXNAV");', 'const u8 gText_MenuDexNav[] = _("图鉴导航");'),
        ('const u8 gText_MenuPlayer[] = _("PLAYER");', 'const u8 gText_MenuPlayer[] = _("训练家");'),
        ('const u8 gText_Yes[] = _("YES");', 'const u8 gText_Yes[] = _("是");'),
        ('const u8 gText_No[] = _("NO");', 'const u8 gText_No[] = _("否");'),
    ],
}

changed = 0
for f, pairs in TRANS.items():
    p = os.path.join(BASE, f)
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        if new in s:
            continue
        if old in s:
            s = s.replace(old, new)
            changed += 1
    open(p, 'w', encoding='utf-8').write(s)
print('replaced strings:', changed)

# 收集源码里所有中文字符
import glob
chars = set()
for root, dirs, files in (list(os.walk(os.path.join(BASE, 'src'))) + list(os.walk(os.path.join(BASE, 'data')))):
    for fn in files:
        if not (fn.endswith('.c') or fn.endswith('.h') or fn.endswith('.inc')):
            continue
        try:
            txt = open(os.path.join(root, fn), encoding='utf-8').read()
        except UnicodeDecodeError:
            continue
        for ch in txt:
            if ord(ch) > 127:
                chars.add(ch)

# 排除原 charmap 已定义的字符（避免 redefining char）
_orig = open(os.path.join(BASE, 'charmap.txt'), encoding='utf-8').read()
_orig = _orig.split('@ CJK-CHARSET-BEGIN')[0]
_defined = set()
for _line in _orig.splitlines():
    _line = _line.split('@')[0].strip()
    _m = re.match(r"^'(.{1})'\s*=", _line)
    if _m:
        _defined.add(_m.group(1))
chars = [c for c in sorted(chars) if c not in _defined]
print('charset size:', len(chars), ''.join(chars))

LEAD_MIN = 0x01
MAX_CHARS = 16 * 256

assert len(chars) <= MAX_CHARS

# 渲染 16x16 1bpp（源格式 2bpp，值 1=前景，2=阴影）
font = ImageFont.truetype(FONT_PATH, 15, index=0)

def render(ch):
    img = Image.new('L', (16, 16), 0)
    d = ImageDraw.Draw(img)
    d.text((0, 0), ch, fill=255, font=font)
    px = img.load()
    grid = [[1 if px[x, y] > 110 else 0 for x in range(16)] for y in range(16)]
    # 阴影：空格子且右侧或下方有前景 → 2
    out = [row[:] for row in grid]
    for y in range(16):
        for x in range(16):
            if grid[y][x] == 0:
                if (x + 1 < 16 and grid[y][x + 1]) or (y + 1 < 16 and grid[y + 1][x]):
                    out[y][x] = 2
    return out

def pack_half(grid, half):
    rows = []
    for y in range(16):
        v = 0
        for i in range(8):
            x = i + half * 8
            v |= (grid[y][x] & 3) << (14 - 2 * i)
        rows.append(v)
    return rows

data = []
charmap_lines = []
for i, ch in enumerate(chars):
    grid = render(ch)
    data.extend(pack_half(grid, 0))
    data.extend(pack_half(grid, 1))
    hi = LEAD_MIN + (i >> 8)
    lo = i & 0xFF
    charmap_lines.append(f"'{ch}' = {hi:02X} {lo:02X}")

# 生成 C 数据文件
lines = ['#include "global.h"', '', 'ALIGNED(4) const u16 gCjkGlyphs[] = {']
for i in range(0, len(data), 12):
    lines.append('    ' + ', '.join(f'0x{v:04X}' for v in data[i:i+12]) + ',')
lines.append('};')
lines.append(f'const u16 gCjkGlyphCount = {len(chars)};')
open(os.path.join(BASE, 'src/cjk_font.c'), 'w').write('\n'.join(lines) + '\n')

# 追加 charmap（先清除旧块）
cm = os.path.join(BASE, 'charmap.txt')
s = open(cm, encoding='utf-8').read()
for mk in ('@ CJK-CHARSET-BEGIN', '# CJK-CHARSET-BEGIN'):
    if mk in s:
        s = s.split(mk)[0].rstrip() + '\n'
s += '@ CJK-CHARSET-BEGIN\n' + '\n'.join(charmap_lines) + '\n'
open(cm, 'w', encoding='utf-8').write(s)
print('charmap entries written:', len(charmap_lines))
