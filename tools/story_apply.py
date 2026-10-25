import re, shutil, json, sys, os

BASE = '/root/build/pokeemerald-expansion-master'
BS = chr(92)
END_P = BS + 'p'

def split_seg(s):
    # 按 $ 切段，保留每段末尾的 $
    parts = []
    cur = ''
    for ch in s:
        cur += ch
        if ch == '$':
            parts.append(cur)
            cur = ''
    if cur:
        parts.append(cur)
    return parts

def build_segment_map(path):
    raw = json.load(open(path, encoding='utf-8'))
    out = {}
    for rel, mapping in raw.items():
        seg = {}
        for en, zh in mapping.items():
            es, zs = split_seg(en), split_seg(zh)
            if len(es) == len(zs):
                for a, b in zip(es, zs):
                    seg[a] = b
            else:
                seg[en] = zh
        out[rel] = seg
    return out

def apply(data):
    total = 0
    for rel, mapping in data.items():
        p = os.path.join(BASE, rel)
        if not os.path.exists(p):
            print('missing', rel); continue
        shutil.copy2(p, '/root/build/storybak_' + rel.replace('/', '_'))
        lines = open(p, encoding='utf-8').read().splitlines(keepends=True)
        out, cur, buf = [], [], ''
        applied, unmatched = 0, []

        def flush():
            nonlocal cur, buf, applied
            if cur:
                if buf in mapping:
                    out.append('\t.string "' + mapping[buf] + '"\n')
                    applied += 1
                else:
                    out.extend(cur)
                    if re.search(r'[A-Za-z]', buf) and not re.search(r'[\u4e00-\u9fff]', buf):
                        unmatched.append(buf[:40])
            cur, buf = [], ''

        for line in lines:
            m = re.match(r'\s*\.string "(.*)"\s*$', line.rstrip('\n'))
            if m:
                cur.append(line)
                buf += m.group(1)
                b = buf.rstrip()
                if b.endswith(END_P) or b.endswith('$'):
                    flush()
            else:
                flush()
                out.append(line)
        flush()
        open(p, 'w', encoding='utf-8').write(''.join(out))
        print('%-45s applied %d/%d' % (rel, applied, len(mapping)))
        if unmatched:
            print('   unmatched:', unmatched[:4])
        total += applied
    print('total applied:', total)

if __name__ == '__main__':
    apply(build_segment_map(sys.argv[1]))
