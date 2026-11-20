# -*- coding: utf-8 -*-
"""오프닝 문구(C_ALL#2 7.2, VDP1): 머리 u32 텍스처 시작·u16 텍스처 수·u16 프레임 수·u32 ?, u32 프레임 오프셋[프레임 수]
   프레임 = u16 개수, u16 예비, 항목 8단어(텍스처 위치/32, 텍스처 번호, x, y, 폭, 높이, 모드, 색)"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, sdp, piece
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def block():
    d = open(os.path.join(ROOT, 'work', 'files', 'DATA', 'C_ALL.SDP'), 'rb').read(); e = {k: (o, s) for k, o, s in sdp.entries(d)}
    o, s = e[2]; p = d[o:o + s]; h = piece.header(p)
    hi = [i for i, x in enumerate(h) if (x[0], x[1]) == (7, 2)][0]; t = h[hi]
    return p[t[2]:t[2] + t[3]], hi
def frames(b):
    tex0, ntex, nfr = struct.unpack_from('>IHH', b, 0)
    offs = struct.unpack_from('>%dI' % nfr, b, 12)
    out = []
    for fo in offs:
        n = struct.unpack_from('>H', b, fo)[0]; es = []
        for k in range(n):
            es.append(struct.unpack_from('>HHhhHHHH', b, fo + 4 + 16 * k))
        out.append(es)
    return tex0, ntex, out
def texture(b, tex0, e):
    to, tn, x, y, w, h, pm, col = e; a = np.frombuffer(b[tex0 + to * 32:tex0 + to * 32 + w * h // 2], np.uint8)
    return np.stack([a >> 4, a & 15], 1).ravel().reshape(h, w).astype(int)
