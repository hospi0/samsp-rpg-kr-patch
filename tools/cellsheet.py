# -*- coding: utf-8 -*-
"""SDP 조각의 VDP2 세트(종류 4 팔레트·5 맵·6 셀) → 타일 시트(4bpp·8bpp 둘 다, 팔레트 적용).  python tools/cellsheet.py 파일 조각 → work/cells/"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import sdp, piece
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def pal(b):
    e = np.frombuffer(b[4:4 + (len(b) - 4) // 2 * 2], '>u2').astype(int) if len(b) % 2 == 0 else np.zeros(256, int)
    return np.stack([(e & 31) << 3, (e >> 5 & 31) << 3, (e >> 10 & 31) << 3], -1).astype(np.uint8)
def tiles(b, bpp, P, cols=32):
    tb = 32 if bpp == 4 else 64; n = len(b) // tb
    a = np.frombuffer(b[:n * tb], np.uint8)
    idx = np.stack([a >> 4, a & 15], -1).reshape(n, 8, 8) if bpp == 4 else a.reshape(n, 8, 8)
    rows = (n + cols - 1) // cols; out = np.zeros((rows * 9, cols * 9, 3), np.uint8)
    for t in range(n):
        r, c = divmod(t, cols); im = P[np.clip(idx[t], 0, len(P) - 1)] if len(P) else np.repeat(idx[t][..., None] * (255 // (15 if bpp == 4 else 255)), 3, -1)
        out[r * 9:r * 9 + 8, c * 9:c * 9 + 8] = im
    return out
if __name__ == '__main__':
    fn, k = sys.argv[1], int(sys.argv[2])
    d = open(os.path.join(ROOT, 'work', 'files', 'DATA', fn + '.SDP'), 'rb').read(); e = {kk: (o, s) for kk, o, s in sdp.entries(d)}
    o, s = e[k]; p = d[o:o + s]; h = piece.header(p)
    os.makedirs(os.path.join(ROOT, 'work', 'cells'), exist_ok=True)
    lastpal = np.zeros((0, 3), np.uint8); n = 0
    for t, sub, bo, bs in h:
        b = p[bo:bo + bs]
        if t == 4: lastpal = pal(b)
        if t == 6:
            for bpp in (4, 8):
                im = tiles(b, bpp, lastpal[:16] if bpp == 4 else lastpal)
                Image.fromarray(im).resize((im.shape[1] * 3, im.shape[0] * 3), Image.NEAREST).save(os.path.join(ROOT, 'work', 'cells', '%s_%d_%x_%dbpp.png' % (fn, k, bo, bpp)))
            n += 1
    print(n)
