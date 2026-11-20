# -*- coding: utf-8 -*-
"""전투 명령 아이콘 8개(NBG2, 전투화면 스테이트) 斬技逃散/物防滅陣 → 한자음 한 글자.
  빈 판 = 8개 판의 같은 위치 «검정(1) 아닌 색» 최빈값(같은 크기·색 판 공유 규칙), 글자 = 검정(1).
  산출: work/gfx/btl_icons.json(패치) · work/preview/gfx_btl_icons.png(원본|새것)"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import v2edit as E, vdp2render as V

ROOT = E.ROOT
ST, N = '전투화면', 2
RX, RY, RW, RH = 16, 176, 96, 64                     # 편집 영역(8 단위)
PLATES = [(26 + 20 * c, 188 + 23 * r) for r in range(2) for c in range(4)]   # 판 왼쪽 위(절대), 16×18
KO = ['참', '기', '도', '산', '물', '방', '멸', '진']    # 斬技逃散 / 物防滅陣
FONT = r'C:\claude\utils\font\blackhansans\BlackHanSans-Regular.ttf'
PW, PH = 16, 18


def glyph_old(ch, w=14, h=15):
    for size in range(22, 8, -1):
        f = ImageFont.truetype(FONT, size); im = Image.new('L', (40, 40), 0); ImageDraw.Draw(im).text((4, 2), ch, fill=255, font=f)
        bb = im.getbbox()
        if bb and bb[2] - bb[0] <= w and bb[3] - bb[1] <= h:
            g = np.asarray(im.crop(bb)) > 110
            out = np.zeros((h, w), bool); oy = (h - g.shape[0]) // 2; ox = (w - g.shape[1]) // 2
            out[oy:oy + g.shape[0], ox:ox + g.shape[1]] = g; return out


def glyph(ch, w=15, h=15):
    import kglyph
    return kglyph.brush_glyph(ch, w, h)                               # 붓글씨(연성체)


def main():
    idx, pal, cram, I = E.read(ST, N, RX, RY, RW, RH)
    plates = [idx[y - RY:y - RY + PH, x - RX:x - RX + PW] for x, y in PLATES]
    blank = np.zeros((PH, PW), int)
    for j in range(PH):
        for i in range(PW):
            c = collections.Counter(int(p[j, i]) for p in plates if p[j, i] != 1)
            blank[j, i] = c.most_common(1)[0][0] if c else 0xC
    assert (blank == 0).sum() == 0
    new = idx.copy()
    for (x, y), ch in zip(PLATES, KO):
        pl = blank.copy(); g = glyph(ch)
        pl[2:2 + g.shape[0], 1:1 + g.shape[1]][g] = 1
        new[y - RY:y - RY + PH, x - RX:x - RX + PW] = pl
    ch = E.plan(ST, N, RX, RY, RW, RH, new)
    patches = E.to_patches2(ST, 'VDP2', ch)
    os.makedirs(os.path.join(ROOT, 'work', 'gfx'), exist_ok=True)
    json.dump({'what': '전투 명령 아이콘 8개', 'ko': KO, 'patches': patches}, open(os.path.join(ROOT, 'work', 'gfx', 'btl_icons.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    # 미리보기(실제 색): 원본 | 새것
    crm = cram
    def rgbimg(a):
        e = crm[((I['craof'] << 8) + pal * 16 + a) & 0x7FF]; return V.rgb(e)
    a = np.hstack([rgbimg(idx), np.zeros((RH, 4, 3), np.uint8) + 255, rgbimg(new)])
    Image.fromarray(a).resize((a.shape[1] * 5, a.shape[0] * 5), Image.NEAREST).save(os.path.join(ROOT, 'work', 'preview', 'gfx_btl_icons_원본_새것.png'))
    print('셀 %d · 패치 %d(사본 포함)' % (len(ch), len(patches)), sorted({p['file'] + '#%d' % p['piece'] for p in patches}))


if __name__ == '__main__':
    main()
