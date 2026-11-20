# -*- coding: utf-8 -*-
"""대사 후보 분량(하한·가설): BE16, 글자 = 상위/하위 둘 다 ≥0x80 & 번호<1859, 제어 = 0x02xx/0x05xx/0x01xx 일부, 끝 = 0000.
   글자 6개 이상 + 글자 비율 70% 이상인 «0000 종결 구간»만 센다. 2026-11-19 조사용(경계 미확정)."""
import sys, glob, struct, os
sys.path.insert(0, os.path.dirname(__file__)); import sdp
NG = 1859
def is_ch(w): return w >= 0x8080 and (w & 0x80) and ((w >> 8 & 0x7F) * 128 + (w & 0x7F)) < NG
def scan(b):
    out = []; n = len(b) // 2; v = struct.unpack('>%dH' % n, b[:n * 2])
    i = 0
    while i < n:
        if not is_ch(v[i]): i += 1; continue
        j = i; ch = 0; ct = 0
        while j < n and v[j] != 0:
            if is_ch(v[j]): ch += 1
            elif v[j] >> 8 in (1, 2, 3, 5): ct += 1
            else: break
            j += 1
        if j < n and v[j] == 0 and ch >= 6 and ch >= 0.7 * (ch + ct):
            out.append((i * 2, v[i:j]))
        i = j + 1
    return out
if __name__ == '__main__':
    tot = 0; tch = 0; uniq = set(); per = {}
    files = ['work/files/1ST.BIN'] + sorted(glob.glob('work/files/DATA/*.SDP'))
    for f in files:
        d = open(f, 'rb').read()
        for al in (0, 1):   # 홀수 정렬도
            for o, s in scan(d[al:]):
                tot += 1; c = sum(1 for w in s if is_ch(w)); tch += c; uniq.add(s)
                per[os.path.basename(f)] = per.get(os.path.basename(f), 0) + c
    print('구간', tot, '글자', tch, '고유 구간', len(uniq), '고유 글자', sum(sum(1 for w in s if is_ch(w)) for s in uniq))
    for k, v in sorted(per.items(), key=lambda x: -x[1]): print(' ', k, v)
