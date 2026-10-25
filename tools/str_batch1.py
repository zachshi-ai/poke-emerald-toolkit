import re, shutil
p='pokeemerald-expansion-master/src/strings.c'
shutil.copy2(p,'/root/build/bak_strings.c')
m={
'SAPPHIRE':'蓝宝石','RUBY':'红宝石','EMERALD':'绿宝石','AQUA':'水舰队','MAGMA':'火岩队',
'ARCHIE':'阿潮','MAXIE':'马克西','KYOGRE':'盖欧卡','GROUDON':'固拉多','BRENDAN':'布兰登',
'MAY':'小遥','RED':'小智','GREEN':'小茂','EGG':'蛋','POKéMON':'宝可梦','PLAYER':'玩家',
'POKéDEX':'图鉴','TIME':'时间','BADGES':'徽章','A Button':'A键','B Button':'B键','R Button':'R键',
'L Button':'L键','+ Control Pad':'+ 方向键','L Button  R Button':'L键  R键','CONTROLS':'操作',
'{DPAD_UPDOWN}PICK {A_BUTTON}OK':'{DPAD_UPDOWN}选择 {A_BUTTON}确定',
'{A_BUTTON}NEXT':'{A_BUTTON}下一个',
'{A_BUTTON}NEXT {B_BUTTON}BACK':'{A_BUTTON}下一个 {B_BUTTON}返回',
'{DPAD_UPDOWN}PICK {A_BUTTON}NEXT {B_BUTTON}CANCEL':'{DPAD_UPDOWN}选择 {A_BUTTON}下一个 {B_BUTTON}取消',
'{DPAD_UPDOWN}PICK {A_BUTTON}{B_BUTTON}CANCEL':'{DPAD_UPDOWN}选择 {A_BUTTON}{B_BUTTON}取消',
'{A_BUTTON}EXIT':'{A_BUTTON}退出','BOY':'男孩','GIRL':'女孩',
'This is what we call a “POKéMON.”{PAUSE 96}\\p':'这就是我们所说的“宝可梦”。{PAUSE 96}\\p',
'????? POKéMON':'?????宝可梦','CRY OF':'叫声：','SIZE COMPARED TO ':'体型对比：',
'Welcome to the HALL OF FAME!':'欢迎来到名人堂！',
"Spotted POKéMON: {STR_VAR_1}!\\nOwned POKéMON: {STR_VAR_2}!\\pPROF. BIRCH's POKéDEX rating!\\pPROF. BIRCH: Let's see…\\p":
"已发现宝可梦：{STR_VAR_1}！\\n已拥有宝可梦：{STR_VAR_2}！\\p橡木博士的图鉴评价！\\p橡木博士：让我看看……\\p",
"SAVING…\\nDON'T TURN OFF THE POWER.":"存档中……\\n请不要关闭电源。",
'The HALL OF FAME data is corrupted.':'名人堂数据已损坏。',
'HALL OF FAME No. {STR_VAR_1}':'名人堂 第{STR_VAR_1}号',
'LEAGUE CHAMPION!\\nCONGRATULATIONS!':'联盟冠军！\\n恭喜你！',
'No. ':'No. ','Lv. ':'Lv. ','IDNo. /':'IDNo. /','NAME':'名字','IDNo.':'IDNo.',
'PROF. BIRCH is in trouble!\\nRelease a POKéMON and rescue him!':'橡木博士有危险！\\n放出宝可梦去救他！',
'Do you choose this POKéMON?':'要选择这只宝可梦吗？','FLY to where?':'要飞往哪里？',
'USE':'使用','TOSS':'丢弃','REGISTER':'登记','GIVE':'交给','CONFIRM':'确定','CANCEL':'取消','NONE':'无',
'Go back to the\\nprevious menu.':'返回\\n上一个菜单。','What would you like to do?':'你想做什么？',
'×{STR_VAR_1}':'×{STR_VAR_1}',' BERRY':'果','{STR_VAR_1} COINS':'{STR_VAR_1}枚代币','CLOSE BAG':'关闭背包',
'{STR_VAR_1}\\nis selected.':'已选择\\n{STR_VAR_1}。',
"You can't write\\nMAIL here.":'这里不能\\n写邮件。',
'There is no\\nPOKéMON.':'没有\\n宝可梦。',
'Move the\\n{STR_VAR_1}\\nwhere?':'要把{STR_VAR_1}\\n移到\\n哪里？',
"The {STR_VAR_1} can't be held.":'{STR_VAR_1}不能携带。',
'Toss out how many\\n{STR_VAR_1}?':'要丢弃多少个\\n{STR_VAR_1}？',
'Threw away {STR_VAR_2}\\n{STR_VAR_1}.':'已丢弃{STR_VAR_2}个\\n{STR_VAR_1}。',
'Is it okay to\\nthrow away {STR_VAR_2}\\n{STR_VAR_1}?':'确定要丢弃{STR_VAR_2}个\\n{STR_VAR_1}吗？',
"DAD's advice…\\n{PLAYER}, there's a time and place for\\leverything!{PAUSE_UNTIL_PRESS}":'爸爸的建议……\\n{PLAYER}，凡事都有\\l它的时机！{PAUSE_UNTIL_PRESS}',
'{PLAYER} used the\\n{STR_VAR_2}.{PAUSE_UNTIL_PRESS}':'{PLAYER}使用了\\n{STR_VAR_2}。{PAUSE_UNTIL_PRESS}',
'But the effects of a REPEL\\nlingered from earlier.{PAUSE_UNTIL_PRESS}':'但驱虫喷雾的效果\\n还在持续。{PAUSE_UNTIL_PRESS}',
'But the effects of a Lure\\nlingered from earlier.{PAUSE_UNTIL_PRESS}':'但引虫香的效果\\n还在持续。{PAUSE_UNTIL_PRESS}',
'The BOX is full.{PAUSE_UNTIL_PRESS}':'盒子已满。{PAUSE_UNTIL_PRESS}',
'the field':'野外','the battle':'战斗','the POKéMON LIST':'宝可梦列表','the shop':'商店','the PC':'电脑',
'Return to\\n{STR_VAR_1}.':'返回\\n{STR_VAR_1}。',
'BUY':'购买','SELL':'出售','QUIT':'退出',
"I'm sorry, but that item is sold out.{PAUSE_UNTIL_PRESS}":'抱歉，那个商品卖完了。{PAUSE_UNTIL_PRESS}',
'SOLD OUT':'售罄','IN BAG: {STR_VAR_1}':'背包中：{STR_VAR_1}','Quit shopping.':'结束购物。',
'{STR_VAR_1}? Certainly.\\nHow many would you like?':'{STR_VAR_1}？好的。\\n你要几个？',
'{STR_VAR_1}? And you wanted {STR_VAR_2}?\\nThat will be ¥{STR_VAR_3}.':'{STR_VAR_1}？你要{STR_VAR_2}个吗？\\n一共¥{STR_VAR_3}。',
"{STR_VAR_1}, is it?\\nThat'll be ¥{STR_VAR_2}. Do you want it?":'{STR_VAR_1}是吧？\\n一共¥{STR_VAR_2}。要买吗？',
"You wanted {STR_VAR_1}?\\nThat'll be ¥{STR_VAR_2}. Will that be okay?":'你要{STR_VAR_1}？\\n一共¥{STR_VAR_2}。可以吗？',
'Here you go!\\nThank you very much.':'给你！\\n非常感谢。',
"Thank you!\\nI'll send it to your home PC.":'谢谢！\\n我会送到你家的电脑里。',
"Thanks!\\nI'll send it to your PC at home.":'谢谢！\\n我会送到你家的电脑。',
"You don't have enough money.{PAUSE_UNTIL_PRESS}":'你的钱不够。{PAUSE_UNTIL_PRESS}',
'You have no more room for this\\nitem.{PAUSE_UNTIL_PRESS}':'你已没有空间\\n放这个道具了。{PAUSE_UNTIL_PRESS}',
'The space for {STR_VAR_1} is full.{PAUSE_UNTIL_PRESS}':'{STR_VAR_1}的存放空间已满。{PAUSE_UNTIL_PRESS}',
'Is there anything else I can help\\nyou with?':'还有什么可以\\n帮你的吗？',
}
STR=re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
s=open(p,encoding='utf-8').read()
hit=[0]
def rep(mm):
    t=mm.group(1)
    if t in m:
        hit[0]+=1; return '_("'+m[t]+'")'
    return mm.group(0)
open(p,'w',encoding='utf-8').write(STR.sub(rep,s))
print('replaced', hit[0], 'dict', len(m))
