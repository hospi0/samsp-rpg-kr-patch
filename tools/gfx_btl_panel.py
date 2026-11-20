# -*- coding: utf-8 -*-
"""전투 패널(NBG2): 칸 번호 판 6개 壱弐参四伍六 → 일이삼사오육, 탭 奥義/道具 → 오의/도구.  산출 work/gfx/btl_panel.json · preview"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import v2edit as E, vdp2render as V, kglyph

RX, RY, RW, RH = 16, 176, 80, 64
PLATES = [(24, 200), (48, 200), (72, 200), (24, 217), (48, 217), (72, 217)]
NUM = '일이삼사오육'
TABS = [('전투커맨드2', '오의'), ('전투도구커맨드', '도구')]
TAB = (34, 185, 44, 14)             # 탭 글자 상자(절대)


def glyph(ch, w, h, font='Galmuri14'):
    return kglyph.brush_glyph(ch, w, h)
    g = kglyph.glyph(ch, font, bold=True).astype(bool); ys, xs = np.nonzero(g); g = g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out = np.zeros((h, w), bool); oy = (h - g.shape[0]) // 2; ox = (w - g.shape[1]) // 2; out[oy:oy + g.shape[0], ox:ox + g.shape[1]] = g; return out


def edit(state, tabtext):
    idx, pal, cram, I = E.read(state, 2, RX, RY, RW, RH); new = idx.copy()
    pl = [idx[y - RY:y - RY + 16, x - RX:x - RX + 16] for x, y in PLATES]
    blank = np.array([[collections.Counter(int(p[j, i]) for p in pl if p[j, i] != 1).most_common(1)[0][0] if any(p[j, i] != 1 for p in pl) else 13 for i in range(16)] for j in range(16)])
    for (x, y), ch in zip(PLATES, NUM):
        b = blank.copy(); g = glyph(ch, 15, 14); b[1:15, 1:16][g] = 1
        new[y - RY:y - RY + 16, x - RX:x - RX + 16] = b
    tx, ty, tw, th = TAB; reg = new[ty - RY:ty - RY + th, tx - RX:tx - RX + tw]
    plate = [int(v) for v in reg.ravel() if v not in (0, 1)]; fill = collections.Counter(plate).most_common(1)[0][0]
    L = []; R = []
    for j in range(th):                                   # 줄마다 판 안쪽 구간만(바깥 검은 장식 보존)
        nz = [i for i in range(tw) if reg[j, i] not in (0, 1)]
        if len(nz) < 4: continue
        l, r = nz[0], nz[-1]; L.append(l); R.append(r)
        seg = reg[j, l:r + 1]; seg[seg == 1] = fill
    cx = (min(L) + max(R)) // 2
    for k, ch in enumerate(tabtext):
        g = glyph(ch, 13, 12, 'Galmuri11'); x0 = cx - 14 + k * 15
        sub = reg[1:13, x0:x0 + 13]; sub[g] = 1
    ch = E.plan(state, 2, RX, RY, RW, RH, new)
    return E.to_patches2(state, 'VDP2', ch), idx, new, pal, cram, I


def main():
    allp = []; prev = []
    for st, t in TABS:
        p, idx, new, pal, cram, I = edit(st, t); allp += p
        rgb = lambda a: V.rgb(cram[((I['craof'] << 8) + pal * 16 + a) & 0x7FF])
        prev.append(np.hstack([rgb(idx), np.full((RH, 3, 3), 255, np.uint8), rgb(new)]))
        print(st, '패치 %d' % len(p))
    json.dump({'what': '전투 패널 칸 번호·탭', 'patches': allp}, open(os.path.join(E.ROOT, 'work', 'gfx', 'btl_panel.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    img = np.vstack(prev); Image.fromarray(img).resize((img.shape[1] * 5, img.shape[0] * 5), Image.NEAREST).save(os.path.join(E.ROOT, 'work', 'preview', 'gfx_btl_panel_원본_새것.png'))


if __name__ == '__main__':
    main()
