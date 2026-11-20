# -*- coding: utf-8 -*-
"""캐릭터 선택 인물 이름 로고 6개(VDP1 64×32/64×31, C_ALL#5 7.7) → 한글 이름(붓 글꼴 굵게, 줄 그라데이션 1~9, 테두리 f)
  산출 work/gfx/logos.json · work/preview/gfx_logos_원본_새것.png"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spredit as P
FD = 'C:/claude/utils/font/'
FONT = FD + 'blackhansans/BlackHanSans-Regular.ttf'
LOGOS = [('하오마루', 0x72A20, '하오마루'), ('갈포드', 0x72220, '갈포드'), ('나코루루', 0x72620, '나코루루'),
         ('겐쥬로', 0x71A60, '키바가미\n겐쥬로'), ('우쿄', 0x71E40, '타치바나\n우쿄'), ('참참', 0x71680, '챰챰')]
RAMP = (1, 2, 3, 4, 5, 6, 7, 8, 9)


def main():
    allp = []; prev = []
    for st, sa, name in LOGOS:
        idx, lut, info, old = P.get(st, sa); h, w = idx.shape
        new = np.zeros_like(idx)
        lines = name.split('\n'); lh = (h - 4) // len(lines)
        for k, ln in enumerate(lines):
            a = P.text_mask(ln, FONT, w - 4, lh - 1)
            m = a >= 0.4; ys, xs = np.nonzero(m)
            P.draw(new, (2, 2 + k * lh, w - 2, 2 + k * lh + lh - 1), a, RAMP, 15, grad='row')
        pt = P.patches(old, P.encode(new)); allp += pt; prev.append((st, idx, new, lut))
        print(st, '사본 %d' % len(pt))
    json.dump({'what': '인물 이름 로고', 'patches': allp}, open(os.path.join(P.ROOT, 'work', 'gfx', 'logos.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    P.preview(prev, os.path.join(P.ROOT, 'work', 'preview', 'gfx_logos_원본_새것.png'), 4)


if __name__ == '__main__':
    main()
