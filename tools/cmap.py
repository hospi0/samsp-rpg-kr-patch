# -*- coding: utf-8 -*-
"""글꼴 번호 ↔ 글자(work/charmap.tsv) · 코드 ↔ 번호. 코드 = 0x8080 | (번호>>7)<<8 | (번호&0x7F)."""
import os, struct
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load():
    T = {}
    for l in open(os.path.join(ROOT, 'work', 'charmap.tsv'), encoding='utf8').read().splitlines()[1:]:
        i, c, _ = l.split('\t'); T[int(i)] = c
    return T
def idx(w): return ((w >> 8) & 0x7F) * 128 + (w & 0x7F)
def code(i): return 0x8080 | ((i >> 7) << 8) | (i & 0x7F)
def decode(ws, T):
    out = []
    for w in ws:
        if w >= 0x8080 and w & 0x80: out.append(T.get(idx(w), '{?%04X}' % w))
        elif w == 0x0200: out.append('⏎')
        else: out.append('{%04X}' % w)
    return ''.join(out)
