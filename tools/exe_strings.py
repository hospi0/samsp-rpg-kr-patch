# -*- coding: utf-8 -*-
"""1ST.BIN(0x06010000 적재) 문자열 전수: BE32 포인터(4정렬) → 대상이 «글자 코드 ≥1 + (제어 01~10xx) + 0000 끝»인 것.
   반환 {문자열 오프셋: [포인터 오프셋…]}."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(__file__)); import cmap
BASE = 0x06010000
def is_ch(w): return w >= 0x8080 and (w & 0x80) and cmap.idx(w) < 1859
def parse(b, o):
    v = []; j = o
    while j + 1 < len(b):
        w = struct.unpack_from('>H', b, j)[0]
        if w == 0: return v, j
        if is_ch(w) or (w >> 8) in range(1, 0x11) and not (w & 0x8000): v.append(w); j += 2
        else: return None, j
        if len(v) > 400: return None, j
    return None, j
def scan(b):
    out = {}
    for p in range(0, len(b) - 3, 4):
        a = struct.unpack_from('>I', b, p)[0]
        if not (BASE <= a < BASE + len(b)) or a & 1: continue
        o = a - BASE
        v, e = parse(b, o)
        if v and sum(1 for w in v if is_ch(w)) >= 1 and (o < 2 or b[o - 2:o] == b'\0\0' or True):
            out.setdefault(o, []).append(p)
    return out
if __name__ == '__main__':
    b = open(sys.argv[1], 'rb').read(); T = cmap.load()
    S = scan(b)
    print(len(S), '문자열 ·', sum(len(v) for v in S.values()), '포인터')
