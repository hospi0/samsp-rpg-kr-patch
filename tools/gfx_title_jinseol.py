# -*- coding: utf-8 -*-
"""타이틀 두루마리 真説 → «진설» 세로 붓글씨 시안(미리보기만, 빌드 안 함)
  바탕 = 합격안 v4(진설원본_사무라이스피리츠_새로그림_v4_붙여씀_인덱스.png)
  지우기: 두루마리 안 먹색(11·13·14·15)만, 칼자루 자리(x<8, y19~33)는 손대지 않음 → 같은 줄 가까운 종이색으로 메움
  쓰기: 글꼴별로 진(위)·설(아래), 먹 15 + 가장자리 13
  산출: work/preview/타이틀_진설한글_시안_<글꼴>_인덱스.png · 타이틀_진설한글_시안_비교.png(원본|시안들, 4배)"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PV = os.path.join(ROOT, 'work', 'preview')
SRC = os.path.join(PV, '진설원본_사무라이스피리츠_새로그림_v4_붙여씀_인덱스.png')
FD = 'C:/claude/utils/font/'
FONTS = {'연성': FD + 'yeonsung/YeonSung-Regular.ttf',
         '나눔붓': FD + 'nanumbrushscript/NanumBrushScript-Regular.ttf',
         '송명': FD + 'songmyung/SongMyung-Regular.ttf',
         '동해독도': FD + 'eastseadokdo/EastSeaDokdo-Regular.ttf'}
INK = (11, 13, 14, 15); PAPER = (1, 2, 10)
STROKE = 0.018
BOX = {'진': (7, 5, 19, 17), '설': (5, 23, 22, 24)}      # x, y, w, h


def hilt(y, x): return x < 8 and 19 <= y <= 33


def glyph(ch, font, w, h):
    big = 16; f = ImageFont.truetype(font, h * big)
    im = Image.new('L', (w * big * 3, h * big * 3), 0); ImageDraw.Draw(im).text((w * big, h * big), ch, fill=255, font=f, stroke_width=round(h * big * STROKE), stroke_fill=255)
    g = im.crop(im.getbbox()); sc = min(w / g.width, h / g.height)
    g = g.resize((max(1, round(g.width * sc)), max(1, round(g.height * sc))), Image.LANCZOS)
    return np.asarray(g) / 255.0


def main():
    im = Image.open(SRC); pal = im.getpalette()[:48]; a = np.asarray(im).astype(int); H, W = a.shape
    base = a.copy()
    for y in range(4, 48):
        for x in range(2, 30):
            if hilt(y, x) or base[y, x] not in INK: continue
            for d in range(1, 30):                     # 같은 줄 가까운 종이색
                c = [base[y, xx] for xx in (x - d, x + d) if 0 <= xx < 30 and a[y, xx] in PAPER and not hilt(y, xx)]
                if c: base[y, x] = c[0]; break
            else: base[y, x] = 2
    outs = {}
    for nm, font in FONTS.items():
        n = base.copy()
        for ch, (bx, by, bw, bh) in BOX.items():
            g = glyph(ch, font, bw, bh); oy = by + (bh - g.shape[0]) // 2; ox = bx + (bw - g.shape[1]) // 2
            for j in range(g.shape[0]):
                for i in range(g.shape[1]):
                    y, x = oy + j, ox + i
                    if hilt(y, x) or n[y, x] == 0: continue
                    if g[j, i] >= 0.55: n[y, x] = 15
                    elif g[j, i] >= 0.3: n[y, x] = 13
        q = Image.new('P', (W, H)); q.putpalette(pal + [0] * (768 - 48)); q.putdata(n.ravel().tolist())
        q.save(os.path.join(PV, '타이틀_진설한글_시안_%s_인덱스.png' % nm), transparency=0)
        outs[nm] = n
    P = np.array(pal).reshape(16, 3)
    def rgb(x):
        r = P[x].astype(np.uint8); r[x == 0] = (104, 160, 104); return r     # 바탕 = 타이틀 풀빛 비슷
    cols = [rgb(a[:, :40])] + [rgb(outs[k][:, :40]) for k in FONTS]
    img = np.hstack([np.pad(c, ((0, 0), (0, 3), (0, 0)), constant_values=255) for c in cols])
    Image.fromarray(img).resize((img.shape[1] * 5, img.shape[0] * 5), Image.NEAREST).save(os.path.join(PV, '타이틀_진설한글_시안_비교.png'))
    full = np.vstack([np.pad(rgb(x), ((0, 3), (0, 0), (0, 0)), constant_values=255) for x in [a] + [outs[k] for k in FONTS]])
    Image.fromarray(full).resize((full.shape[1] * 3, full.shape[0] * 3), Image.NEAREST).save(os.path.join(PV, '타이틀_진설한글_시안_전체.png'))
    print('왼쪽부터 원본 |', ' | '.join(FONTS))


if __name__ == '__main__':
    main()
