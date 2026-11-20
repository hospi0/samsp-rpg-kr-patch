# -*- coding: utf-8 -*-
"""VDP1 스프라이트 그림 글자 한글화 → work/gfx/spr.json · work/preview/gfx_spr_원본_새것.png
  작업 = (스테이트, 스프라이트 주소, 잉크 색, 바탕 반복 주기, 글자 상자(x,y,w,h), 한글, 글꼴, 굵게, 색 단계, 테두리 색)"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spredit as P

ROOT = P.ROOT
FD = 'C:/claude/utils/font/'
MYEONG = FD + 'nanum-myeongjo/NanumMyeongjoExtraBold.ttf'
DOKDO = FD + 'eastseadokdo/EastSeaDokdo-Regular.ttf'
BHS = FD + 'blackhansans/BlackHanSans-Regular.ttf'
GREY = (1, 2, 3, 4, 5, 6)

JOBS = [
    ('제목띠_주인공선택', '하오마루', 0x6FA80, GREY + (11,), 16, (44, 3, 232, 18), '주인공을 선택해 주십시오', MYEONG, 0, (3, 4, 5, 6), 11),
    ('시나리오_사천강림', '시나리오선택', 0x71300, GREY, 16, (2, 0, 108, 16), '사천강림의 장', MYEONG, 0, (3, 4, 5, 6), 11),
    ('시나리오_요화통곡', '시나리오선택', 0x70F80, GREY, 16, (2, 0, 108, 16), '요화통곡의 장', MYEONG, 0, (3, 4, 5, 6), 11),
    ('오의입력_격투커맨드', '오의선택', 0x70C80, GREY, 16, (2, 0, 92, 16), '격투 커맨드', MYEONG, 0, (3, 4, 5, 6), 11),
    ('오의입력_기술명선택', '오의선택', 0x70980, GREY, 16, (2, 0, 92, 16), '기술명 선택', MYEONG, 0, (3, 4, 5, 6), 11),
    ('전투팝업_참', '전투커맨드1', 0x7E640, (1, 2), None, (3, 2, 26, 28), '참', MYEONG, 1, (2,), 1),
    ('전투팝업_기', '전투커맨드2사용', 0x7E440, (1, 2), None, (3, 2, 26, 28), '기', MYEONG, 1, (2,), 1),
]


def main(only=None):
    allp = []; prev = []
    for name, st, sa, ink, per, (bx, by, bw, bh), text, font, dil, ramp, outline in JOBS:
        if only and name not in only: continue
        idx, lut, info, old = P.get(st, sa); h, w = idx.shape
        new = P.erase(idx, set(ink), (0, 0, w, h), per)
        a = P.text_mask(text, font, bw - 2, bh - 2, dil)
        P.draw(new, (bx + 1, by + 1, bx + 1 + bw - 2, by + 1 + bh - 2), a, ramp, outline)
        pt = P.patches(old, P.encode(new)); allp += pt; prev.append((name, idx, new, lut))
        print(name, '사본 %d' % len(pt), sorted({'%s#%d' % (p['file'], p['piece']) for p in pt}))
    json.dump({'what': 'VDP1 스프라이트 그림 글자', 'jobs': [j[0] for j in JOBS], 'patches': allp},
              open(os.path.join(ROOT, 'work', 'gfx', 'spr.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    P.preview(prev, os.path.join(ROOT, 'work', 'preview', 'gfx_spr_원본_새것.png'), 3)


if __name__ == '__main__':
    main(sys.argv[1:] or None)
