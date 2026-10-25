import re, shutil, json, sys

p = '/root/build/pokeemerald-expansion-master/data/maps/LittlerootTown/scripts.inc'
shutil.copy2(p, '/root/build/bak_littleroot.inc')

M = {
"MOM: {PLAYER}, we're here, honey!\\p": "妈妈：{PLAYER}，我们到了，宝贝！\\p",
"It must be tiring riding with our things\\nin the moving truck.\\p": "坐在搬家卡车里，\\n一定很累吧。\\p",
"Well, this is LITTLEROOT TOWN.\\p": "这里就是未白镇了。\\p",
"How do you like it?\\nThis is our new home!\\p": "你觉得怎么样？\\n这就是我们的新家！\\p",
"It has a quaint feel, but it seems to be\\nan easy place to live, don't you think?\\p": "有点古朴，不过\\n住起来很舒服吧？\\p",
"And, you get your own room, {PLAYER}!\\nLet's go inside.$MOM: Wait, {PLAYER}!$MOM: {PLAYER}! {PLAYER}! Did you\\nintroduce yourself to PROF. BIRCH?\\p": "而且你还有自己的房间，{PLAYER}！\\n我们进去吧。$妈妈：等等，{PLAYER}！$妈妈：{PLAYER}！{PLAYER}！你\\n跟橡木博士打过招呼了吗？\\p",
"Oh! What an adorable POKéMON!\\nYou got it from PROF. BIRCH. How nice!\\p": "哦！好可爱的宝可梦！\\n是从橡木博士那里得到的吧。\\p",
"You're your father's child, all right.\\nYou look good together with POKéMON!\\p": "果然是爸爸的孩子。\\n你和宝可梦很般配！\\p",
"Here, honey! If you're going out on an\\nadventure, wear these RUNNING SHOES.\\p": "来，宝贝！要去冒险的话，\\n就穿上这双跑步鞋。\\p",
"They'll put a zip in your step!${PLAYER} switched shoes with the\\nRUNNING SHOES.$MOM: {PLAYER}, those shoes came with\\ninstructions.\\p": "穿上它脚下生风！${PLAYER}换上了\\n跑步鞋。$妈妈：{PLAYER}，这双鞋\\n是附说明书的。\\p",
"“Press the B Button while wearing these\\nRUNNING SHOES to run extra-fast!\\p": "“穿上跑步鞋时按B键\\n就能跑得更快！\\p",
"“Slip on these RUNNING SHOES and race\\nin the great outdoors!”$… … … … … … … …\\n… … … … … … … …\\p": "“穿上跑步鞋，到大自然里\\n奔跑吧！”$…… …… …… ……\\n…… …… …… ……\\p",
"To think that you have your very own\\nPOKéMON now…\\lYour father will be overjoyed.\\p": "你现在有了自己的\\n宝可梦……\\l你爸爸会很高兴的。\\p",
"…But please be careful.\\nIf anything happens, you can come home.\\p": "……不过要小心。\\n有事就回家来。\\p",
"Go on, go get them, honey!$If you use a PC, you can store items\\nand POKéMON.\\p": "去吧，加油，宝贝！$用电脑可以存放道具\\n和宝可梦。\\p",
"The power of science is staggering!$PROF. BIRCH spends days in his LAB\\nstudying, then he'll suddenly go out in\\lthe wild to do more research…\\p": "科学的力量真厉害！$橡木博士整天在研究所\\n研究，然后突然跑到\\l野外去做调查……\\p",
"When does PROF. BIRCH spend time\\nat home?$Um, um, um!\\p": "橡木博士什么时候\\n在家呢？$呃，呃，呃！\\p",
"If you go outside and go in the grass,\\nwild POKéMON will jump out!$It's dangerous if you don't have\\nyour own POKéMON.$Um, hi!\\p": "到外面走进草丛，\\n野生宝可梦会跳出来！$没有自己的宝可梦\\n是很危险的。$呃，你好！\\p",
"There are scary POKéMON outside!\\nI can hear their cries!\\p": "外面有可怕的宝可梦！\\n我能听到它们的叫声！\\p",
"I want to go see what's going on,\\nbut I don't have any POKéMON…\\p": "我想去看看发生了什么，\\n可是我没有宝可梦……\\p",
"Can you go see what's happening\\nfor me?$You saved PROF. BIRCH!\\nI'm so glad!$Are you going to catch POKéMON?\\nGood luck!$LITTLEROOT TOWN\\n“A town that can't be shaded any hue.”$PROF. BIRCH'S POKéMON LAB${PLAYER}'s HOUSE$PROF. BIRCH'S HOUSE$PROF. BIRCH: Well, well, {PLAYER}{KUN}!\\nThat was good work out there!\\p": "你能替我去看看\\n发生了什么吗？$你救了橡木博士！\\n太好了！$你要去抓宝可梦吗？\\n祝你好运！$未白镇\\n“不会被任何颜色染上的小镇。”$橡木博士的研究所${PLAYER}的家$橡木博士的家$橡木博士：哎呀呀，{PLAYER}{KUN}！\\n刚才干得不错！\\p",
"I knew there was something special\\nabout you when I first saw you,\\lbut I never expected this.\\p": "第一次见到你我就觉得\\n你与众不同，\\l但没想到这么厉害。\\p",
"Oh, yes. Do you still have the POKéDEX\\nI gave you?\\p": "对了，我给你的图鉴\\n还带着吗？\\p",
"I have something to show you.\\nLet's go to my LAB.$": "我有东西给你看。\\n去我的研究所吧。$",
}

lines = open(p, encoding='utf-8').read().splitlines(keepends=True)
out = []
cur = []
start = None
applied = 0
buf = ''

def flush():
    global cur, start, applied
    if cur:
        key = buf
        if key in M:
            out.append('\t.string "%s"\n' % M[key])
            applied += 1
        else:
            out.extend(cur)
    cur = []
    start = None

buf = ''
for line in lines:
    m = re.match(r'\s*\.string "(.*)"\s*$', line.rstrip('\n'))
    if m:
        if not cur:
            start = len(out)
        cur.append(line)
        buf += m.group(1)
        if '\\p' in m.group(1):
            flush(); buf = ''
    else:
        flush(); buf = ''
        out.append(line)
flush()

open(p, 'w', encoding='utf-8').write(''.join(out))
print('messages translated:', applied, 'of', len(M))
