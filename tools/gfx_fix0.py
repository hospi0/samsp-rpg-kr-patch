# -*- coding: utf-8 -*-
"""FIX.SDP 조각 0(공용 UI 셀) 그림 글자 한글화 — 화판(16칸 폭: 칸 768~ / 32칸 폭: 칸 0~767)에서 직접 고침.
  산출 work/gfx/fix0.json(칸 단위 패치) · work/preview/gfx_fix0_*_원본_새것.png
  각 작업 = (이름, 화판, 사각형, 지울 색, 바탕 색, 글자, 글꼴, 글자 색, 그림자 색)
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import fixcanvas as F, kglyph, v2edit as E, vdp2render as V

ROOT = F.ROOT
B0 = F.load(); N = len(B0) // 32
TILES = np.stack([np.frombuffer(B0, np.uint8) >> 4, np.frombuffer(B0, np.uint8) & 15], -1).reshape(N, 8, 8).astype(int)


def canvas(W, start):
    cnt = (N - start) if W == 16 else 768; rows = (cnt + W - 1) // W
    c = np.zeros((rows * 8, W * 8), int)
    for i in range(cnt): c[i // W * 8:i // W * 8 + 8, i % W * 8:i % W * 8 + 8] = TILES[start + i]
    return c


def put_back(c, W, start, tiles):
    for i in range(tiles.shape[0] - start if W == 16 else 768):
        r, q = divmod(i, W)
        if (r + 1) * 8 <= c.shape[0]: tiles[start + i] = c[r * 8:r * 8 + 8, q * 8:q * 8 + 8]


def glyph(ch, font, w, h):
    if font == 'brush':
        return kglyph.brush_glyph(ch, w, h)
    if font == 'galmuri':
        g = kglyph.glyph(ch, 'Galmuri14', bold=True).astype(bool)
    else:
        f = ImageFont.truetype(font[0], font[1]); im = Image.new('L', (font[1] * 3, font[1] * 2), 0)
        ImageDraw.Draw(im).text((4, 4), ch, fill=255, font=f); g = np.asarray(im) > 120
    ys, xs = np.nonzero(g); g = g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if g.shape[0] > h or g.shape[1] > w:
        g = np.asarray(Image.fromarray(g.astype(np.uint8) * 255).resize((min(w, g.shape[1]), min(h, g.shape[0])), Image.LANCZOS)) > 110
    out = np.zeros((h, w), bool); oy = (h - g.shape[0]) // 2; ox = (w - g.shape[1]) // 2
    out[oy:oy + g.shape[0], ox:ox + g.shape[1]] = g
    return out


def stamp(c, x, y, w, h, text, font, fg, shadow, erase, bg):
    """사각형 안: 지울 색(erase) → 바탕(bg), 글자들을 가로로 나눠 그림(그림자 = 오른쪽·아래 1px)"""
    reg = c[y:y + h, x:x + w]
    for col in erase: reg[reg == col] = bg
    n = len(text); cw = w // n
    for k, ch in enumerate(text):
        if ch == ' ': continue
        g = glyph(ch, font, cw - (1 if shadow is not None else 0), h - (1 if shadow is not None else 0))
        X = x + k * cw
        if shadow is not None:
            m = np.zeros((h, cw), bool); m[1:1 + g.shape[0], 1:1 + g.shape[1]] = g
            sub = c[y:y + h, X:X + cw]; sub[m & (sub == bg)] = shadow
        sub = c[y:y + g.shape[0], X:X + g.shape[1]]; sub[g] = fg


JOBS16 = []                                   # 16칸 폭 화판(칸 768~)
HL = [(x, 82 if k < 4 else 105, ch) for k, (x, ch) in enumerate(zip((1, 29, 49, 77) * 2, '참기도산물방멸진'))]   # 강조 아이콘 斬技逃散/物防滅陣


def highlight(c):
    """강조 아이콘 = 보통 아이콘(gfx_btl_icons)과 «같은 글자 마스크·같은 자리»(2026-11-21 하스피 «흰 하이라이트 어긋남»).
       원본 실측: 강조 화판 (x+1, y+2) = NBG2 판 (0,0), 강조 글자(1) = 판 글자(1) 화소 그대로. 판 안 글자 자리 = (1, 2)."""
    import gfx_btl_icons as B
    for x, y, ch in HL:
        reg = c[y + 2:y + 20, x + 2:x + 17]; reg[np.isin(reg, (1, 2))] = 0
        g = B.glyph(ch); X, Y = x + 1 + 1, y + 2 + 2
        sub = c[Y:Y + g.shape[0], X:X + g.shape[1]]; sub[g] = 1
# 강조 칸 번호 壱弐参四伍六: (화판 x, y, 글자, 원본 실측 «판 (0,0) = 화판 (x+dx, y+dy)»)
NUMHL = [(97, 81, '일', -1, -1), (113, 81, '이', -1, -1), (97, 97, '삼', -1, -1), (113, 97, '사', -1, 0), (97, 112, '오', -1, 1), (113, 112, '육', -1, 1)]


def numhl(c):
    """강조 칸 번호 = 전투 패널 판(gfx_btl_panel: glyph(ch,15,14) 를 판 (1,1))과 같은 마스크·같은 자리"""
    import gfx_btl_panel as P
    for x, y, ch, dx, dy in NUMHL:
        X, Y = x + dx + 1, y + dy + 1
        for (rx, ry) in ((x, y), (X, Y)):                   # 옛 글자 자리 + 새 글자 자리의 글자·그림자 색 지움
            reg = c[ry:ry + 15, rx:rx + 15]; reg[np.isin(reg, (1, 2))] = 0
        g = P.glyph(ch, 15, 14); sub = c[Y:Y + 14, X:X + 15]; sub[g] = 1


def bdf_text(text, name):
    import kglyph
    kglyph.FONTS.setdefault(name, 'C:/claude/utils/font/Galmuri-v2.40.3/%s.bdf' % name)
    gl, top, bot = kglyph.load(name); H = top - bot + 1; cols = []
    for ch in text:
        g = gl[ord(ch)]; gw, gh, xo, yo = g['bbx']; a = np.zeros((H, gw + max(xo, 0) + 1), bool)
        for r, hx in enumerate(g['rows']):
            vv = int(hx, 16); nb = len(hx) * 4
            for xx in range(gw):
                if vv >> (nb - 1 - xx) & 1:
                    Y = top - (yo + gh) + r
                    if 0 <= Y < H: a[Y, max(xo, 0) + xx] = True
        cols.append(a)
    g = np.hstack(cols); ys, xs = np.nonzero(g)
    return g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def stamp_grad(c, x, y, w, h, text, font, erase, bg, rowcol):
    """그라데이션 글자(줄마다 색): 사각형 안 지울 색 → 바탕, 비트맵 글꼴 글자를 가운데, 줄 y 의 색 = rowcol[y-y0]"""
    reg = c[y:y + h, x:x + w]
    for col in erase: reg[reg == col] = bg
    g = bdf_text(text, font)
    if g.shape[0] > h or g.shape[1] > w: raise SystemExit('⛔ %s 글자 %s > 칸 %dx%d' % (text, g.shape, w, h))
    oy = (h - g.shape[0]) // 2; ox = (w - g.shape[1]) // 2
    for j in range(g.shape[0]):
        for i in range(g.shape[1]):
            if g[j, i]: c[y + oy + j, x + ox + i] = rowcol[oy + j]


def shohi(c):
    """消費(16칸 폭 x80~111, y192~207): 바탕 = 1(흰), 획 = c·d·e(얼룩) → 획 지우고 «소비»를 얼룩 획으로(원래 획 화소면 그 색, 아니면 d)"""
    x, y, w, h = 80, 192, 32, 16
    orig = c[y:y + h, x:x + w].copy()
    reg = c[y:y + h, x:x + w]; inner = reg[1:h - 1]; inner[np.isin(inner, (12, 13, 14))] = 1
    for k, ch in enumerate('소비'):
        g = glyph(ch, 'galmuri', 15, 14)
        for j in range(14):
            for i in range(15):
                if g[j, i]:
                    o = orig[1 + j, k * 16 + i]; reg[1 + j, k * 16 + i] = o if o in (12, 13, 14) else 13


def moe(c):
    """燃 프레임 5장(16칸 폭 y68~78, x 0·17·34·51·68, 폭 16): 프레임마다 테두리색·줄별 채움색 읽어 «분» 다시 그림(그림자 f)"""
    import collections
    def binary_dilation(m, k):
        p = np.pad(m, 1); return np.max([p[dy:dy + m.shape[0], dx:dx + m.shape[1]] for dy in range(3) for dx in range(3)], 0)
    for x0 in (0, 17, 34, 51, 68):
        reg = c[68:79, x0:x0 + 16].copy()
        ink = (reg != 0) & (reg != 15); p = np.pad(ink, 1)
        edge = ink & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])   # 투명과 맞닿은 잉크 = 테두리
        border = collections.Counter(int(v) for v in reg[edge]).most_common(1)[0][0]
        fills = []
        for j in range(11):
            cc = collections.Counter(int(v) for v, e in zip(reg[j], edge[j]) if v not in (0, 15, border) and not e)
            fills.append(cc.most_common(1)[0][0] if cc else (fills[-1] if fills else border))
        g = bdf_text('분', 'Galmuri9')
        gh, gw = g.shape; m = np.zeros((11, 16), bool); oy = (11 - gh) // 2; ox = 1
        m[oy:oy + gh, ox:ox + gw] = g
        m2 = binary_dilation(m, np.ones((3, 3), bool))           # 테두리
        sh = np.zeros_like(m2); sh[1:, 1:] = m2[:-1, :-1]
        out = np.zeros((11, 16), int); out[sh & ~m2] = 15; out[m2] = border
        for j in range(11): out[j][m[j]] = fills[j]
        c[68:79, x0:x0 + 16] = out


GRAD = [1, 1, 2, 3, 4, 5, 5]
JOBS32 = [('체력라벨', 13, 72, 23, 7, '체력', 'Galmuri7', (1, 2, 3, 4, 5, 6), 7, GRAD),
          ('기력라벨', 53, 72, 23, 7, '기력', 'Galmuri7', (1, 2, 3, 4, 5, 6), 7, GRAD),
          ('체력라벨넓은', 166, 96, 36, 7, '체력', 'Galmuri7', (1, 2, 3, 4, 5, 6), 7, GRAD)]


def main():
    tiles = TILES.copy()
    c16 = canvas(16, 768); o16 = c16.copy()
    for job in JOBS16:
        name, x, y, w, h, text, font, fg, sh, er, bg = job
        stamp(c16, x, y, w, h, text, font, fg, sh, er, bg)
    highlight(c16); numhl(c16); shohi(c16); moe(c16)
    put_back(c16, 16, 768, tiles)
    c32 = canvas(32, 0)
    for i in range(768): c32[i // 32 * 8:i // 32 * 8 + 8, i % 32 * 8:i % 32 * 8 + 8] = tiles[i]
    o32 = c32.copy()
    for name, x, y, w, h, text, font, er, bg, rc in JOBS32: stamp_grad(c32, x, y, w, h, text, font, er, bg, rc)
    put_back(c32, 32, 0, tiles)
    patches = []
    for i in range(N):
        if (tiles[i] != TILES[i]).any():
            b = bytes(((int(tiles[i][j, 2 * q]) << 4) | int(tiles[i][j, 2 * q + 1])) for j in range(8) for q in range(4))
            patches.append({'file': 'FIX', 'piece': 0, 'type': -1, 'sub': -1, 'hidx': -1, 'off': i * 32, 'new': b.hex(), 'old': B0[i * 32:i * 32 + 32].hex()})
    os.makedirs(os.path.join(ROOT, 'work', 'gfx'), exist_ok=True)
    json.dump({'what': 'FIX#0 공용 UI 그림 글자', 'jobs': ['강조아이콘_' + h[2] for h in HL] + ['칸번호_' + n[2] for n in NUMHL] + [j[0] for j in JOBS16], 'patches': patches},
              open(os.path.join(ROOT, 'work', 'gfx', 'fix0.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    C, v, cram, I = E.cells('전투화면', 3)
    def rgb(a):
        im = V.rgb(cram[(101 * 16 + a) & 0x7FF]); im[a == 0] = (70, 0, 70); return im
    y0, y1 = 60, 210
    a = np.hstack([rgb(o16[y0:y1]), np.full((y1 - y0, 4, 3), 255, np.uint8), rgb(c16[y0:y1])])
    Image.fromarray(a).resize((a.shape[1] * 5, a.shape[0] * 5), Image.NEAREST).save(os.path.join(ROOT, 'work', 'preview', 'gfx_fix0_전투강조_칸번호_원본_새것.png'))
    y0, y1 = 64, 104
    a = np.hstack([rgb(o32[y0:y1]), np.full((y1 - y0, 4, 3), 255, np.uint8), rgb(c32[y0:y1])])
    Image.fromarray(a).resize((a.shape[1] * 4, a.shape[0] * 4), Image.NEAREST).save(os.path.join(ROOT, 'work', 'preview', 'gfx_fix0_체력기력_원본_새것.png'))
    print('패치 칸 %d' % len(patches))


if __name__ == '__main__':
    main()
