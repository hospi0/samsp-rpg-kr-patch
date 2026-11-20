# -*- coding: utf-8 -*-
"""알려진 문장의 «같은 글자 = 같은 코드» 모양으로 미지 인코딩 검색. python tools/patsearch.py <파일…> -- <문장(⏎=줄바꿈 자리, 0~3 토큰 허용)>"""
import sys, struct
def search(b, text, w):
    parts = text.split('⏎')
    n = len(b) // w
    vals = struct.unpack('>%d%s' % (n, 'H' if w == 2 else 'B'), b[:n * w])
    hits = []
    L0 = len(parts[0])
    for i in range(n - len(text) - 6):
        # 첫 줄
        m = {}; ok = True
        def chk(ch, v):
            if ch in m: return m[ch] == v
            if v in m.values(): return False
            m[ch] = v; return True
        for k, ch in enumerate(parts[0]):
            if not chk(ch, vals[i + k]): ok = False; break
        if not ok: continue
        if len(parts) == 1: hits.append((i * w, dict(m))); continue
        for gap in range(0, 4):
            m2 = dict(m); m = m2; good = True
            j = i + L0 + gap
            for k, ch in enumerate(parts[1]):
                if j + k >= n or not chk(ch, vals[j + k]): good = False; break
            if good: hits.append((i * w, gap, dict(m)))
            m = {kk: vv for kk, vv in m2.items() if kk in parts[0]}
    return hits
if __name__ == '__main__':
    a = sys.argv[1:]; k = a.index('--'); files, text = a[:k], a[k + 1]
    for f in files:
        b = open(f, 'rb').read()
        for w in (2, 1):
            h = search(b, text, w)
            print(f, 'w=%d' % w, len(h))
            for x in h[:5]: print('  ', hex(x[0]), x[1:])
