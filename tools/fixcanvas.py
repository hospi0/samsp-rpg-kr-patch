# -*- coding: utf-8 -*-
"""FIX.SDP 조각 0(VDP2 공용 UI 셀, 4bpp, VRAM 0x80~) ↔ 256폭 화판(색 번호). 칸 t = 화판 (t%32*8, t//32*8)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, sdp
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load():
    d = open(os.path.join(ROOT, 'work', 'files', 'DATA', 'FIX.SDP'), 'rb').read(); e = {k: (o, s) for k, o, s in sdp.entries(d)}
    o, s = e[0]; return d[o:o + s]
def to_canvas(b):
    n = len(b) // 32; a = np.frombuffer(b, np.uint8); t = np.stack([a >> 4, a & 15], -1).reshape(n, 8, 8).astype(int)
    rows = n // 32; c = np.zeros((rows * 8, 256), int)
    for i in range(n): c[i // 32 * 8:i // 32 * 8 + 8, i % 32 * 8:i % 32 * 8 + 8] = t[i]
    return c
def from_canvas(c):
    out = bytearray()
    for i in range(c.shape[0] // 8 * 32):
        t = c[i // 32 * 8:i // 32 * 8 + 8, i % 32 * 8:i % 32 * 8 + 8]
        out += bytes(((int(t[j, 2 * k]) << 4) | int(t[j, 2 * k + 1])) for j in range(8) for k in range(4))
    return bytes(out)
