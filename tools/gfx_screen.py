# -*- coding: utf-8 -*-
"""화면 기준 그림 글자 한글화(v2edit: 스테이트 층 영역 → 셀 → 디스크 패치).
  python tools/gfx_screen.py [작업 이름…]   → work/gfx/scr_<이름>.json · work/preview/gfx_<이름>_원본_새것.png
작업: 영역 안 잉크(지정 색) 지움 → 한글을 글꼴로 그려 색 단계에 나눠 담음."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import v2edit as E, vdp2render as V

ROOT = E.ROOT
FD = r'C:\claude\utils\font'
PEN = FD + r'\nanum-pen\NanumPenScript-Regular.ttf'
BRUSH = FD + r'\nanumbrushscript\NanumBrushScript-Regular.ttf'
DOKDO = FD + r'\eastseadokdo\EastSeaDokdo-Regular.ttf'

JOBS = {
    # 이름: (스테이트, 층, (x,y,w,h 8단위), 지울 색들, 한글, 글꼴, 글자 상자(x,y,w,h), 색 단계(옅음→짙음))
    'loading': ('로딩스크린', 3, (176, 192, 120, 24), (15,), '잠시 기다려 주세요…', 'pen', (178, 195, 116, 16), (15,)),
    'kire': ('전투로딩', 3, (88, 48, 152, 128), (8, 9, 10, 11), '베어라', ('dilate', DOKDO, 2), (94, 62, 136, 96), (8, 9, 10, 11)),
}


def bdf_line(text, name, w, h, color):
    """작은 글씨 = 비트맵 글꼴 그대로(축소 없음)"""
    import kglyph
    kglyph.FONTS.setdefault(name, 'C:/claude/utils/font/Galmuri-v2.40.3/%s.bdf' % name)
    gl, top, bot = kglyph.load(name); H = top - bot + 1; cols = []
    for ch in text:
        if ch == ' ': cols.append(np.zeros((H, 3), bool)); continue
        g = gl[ord(ch)]; gw, gh, xo, yo = g['bbx']; a = np.zeros((H, max(gw + max(xo, 0), 1) + 1), bool)
        for r, hx in enumerate(g['rows']):
            vv = int(hx, 16); nb = len(hx) * 4
            for xx in range(gw):
                if vv >> (nb - 1 - xx) & 1:
                    Y = top - (yo + gh) + r
                    if 0 <= Y < H: a[Y, max(xo, 0) + xx] = True
        cols.append(a)
    g = np.hstack(cols)
    if g.shape[1] > w: raise SystemExit('⛔ 글씨 폭 %d > %d' % (g.shape[1], w))
    out = np.zeros((h, w), int); oy = max(0, (h - g.shape[0]) // 2)
    out[oy:oy + g.shape[0], 0:g.shape[1]][g[:h - oy]] = color
    return out


def render_text(text, font, w, h, levels):
    """글자를 상자에 맞춰 크게 → 줄여 농담(0~1) → 단계 색 번호 배열(0 = 투명)"""
    if isinstance(font, str) and font.startswith('bdf:'): return bdf_line(text, font[4:], w, h, levels[-1])
    if font == 'pen':                                   # 손글씨(나눔손글씨 펜), «…» 는 점 셋 직접
        import kglyph
        body = text.rstrip('…'); m = kglyph.brush_line(body, w - 12, h - 1, thr=100, bold=False)
        out = np.zeros((h, w), int); out[0:h - 1, 0:m.shape[1]][m] = levels[-1]
        xe = int(np.nonzero(m.any(0))[0].max()) + 3
        if text.endswith('…'):
            for k in range(3): out[h - 3:h - 1, xe + k * 3:xe + k * 3 + 2] = levels[-1]
        return out
    dil = 0
    if isinstance(font, tuple): _, font, dil = font
    big = 8
    for size in range(h * big * 2, 8, -4):
        f = ImageFont.truetype(font, size); im = Image.new('L', (w * big * 2, h * big * 2), 0)
        ImageDraw.Draw(im).text((10, 10), text, fill=255, font=f); bb = im.getbbox()
        if bb and bb[2] - bb[0] <= w * big and bb[3] - bb[1] <= h * big: break
    if dil:
        from PIL import ImageFilter
        im = im.filter(ImageFilter.MaxFilter(dil * big + 1)); bb = im.getbbox()
    g = im.crop(bb); sc = min(w / g.width, h / g.height)
    g = g.resize((max(1, round(g.width * sc)), max(1, round(g.height * sc))), Image.LANCZOS)
    a = np.asarray(g) / 255.0; out = np.zeros((h, w), int)
    oy, ox = (h - a.shape[0]) // 2, (w - a.shape[1]) // 2
    n = len(levels)
    for j in range(a.shape[0]):
        for i in range(a.shape[1]):
            v = a[j, i]
            if v < 0.35: continue
            k = min(n - 1, int((v - 0.35) / 0.65 * n))
            out[oy + j, ox + i] = levels[k]
    return out


def run(name):
    st, n, (x, y, w, h), erase, text, font, (bx, by, bw, bh), levels = JOBS[name]
    idx, pal, cram, I = E.read(st, n, x, y, w, h)
    new = idx.copy()
    for c in erase: new[new == c] = 0
    C, v, cram2, I2 = E.cells(st, n)
    users = {}
    for k_, (a_, p_, h_, v_) in C.items(): users.setdefault(a_, set()).add(k_)
    inside = {(tx, ty) for ty in range(y // 8, (y + h) // 8) for tx in range(x // 8, (x + w) // 8)}
    allow = np.zeros((h, w), bool)                       # 쓸 수 있는 칸 = 영역 밖에서 안 쓰는 고유 셀
    for (tx, ty) in inside:
        a_ = C[(tx, ty)][0]
        if not (users[a_] - inside) and len(users[a_]) == 1: allow[ty * 8 - y:ty * 8 - y + 8, tx * 8 - x:tx * 8 - x + 8] = True
    best = None
    for sc in [1.0 - 0.04 * i for i in range(15)]:
        tw, th = int(bw * sc), int(bh * sc)
        t = render_text(text, font, tw, th, levels)
        for dy in range(0, bh - th + 1, 2):
            for dx in range(0, bw - tw + 1, 2):
                m = np.zeros((h, w), bool); m[by - y + dy:by - y + dy + th, bx - x + dx:bx - x + dx + tw] = t > 0
                if (m & ~allow).any(): continue
                best = (sc, dx, dy, t, tw, th); break
            if best: break
        if best: break
    if not best: raise SystemExit('⛔ %s: 고유 셀 안에 들어가는 배치 없음' % name)
    sc, dx, dy, t, tw, th = best; print('  크기 %.2f 위치 (%d,%d)' % (sc, dx, dy))
    sub = new[by - y + dy:by - y + dy + th, bx - x + dx:bx - x + dx + tw]; sub[t > 0] = t[t > 0]
    ch = E.plan(st, n, x, y, w, h, new)
    patches = E.to_patches2(st, 'VDP2', ch)
    os.makedirs(os.path.join(ROOT, 'work', 'gfx'), exist_ok=True)
    json.dump({'what': name, 'text': text, 'patches': patches}, open(os.path.join(ROOT, 'work', 'gfx', 'scr_%s.json' % name), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    pl = int(np.bincount(pal[idx > 0].ravel()).argmax()) if (idx > 0).any() else 0
    def rgb(a):
        im = V.rgb(cram[(pl * 16 + a) & 0x7FF]); im[a == 0] = (0, 0, 0); return im
    a = np.hstack([rgb(idx), np.full((h, 4, 3), 255, np.uint8), rgb(new)])
    z = 4 if w < 200 else 3
    Image.fromarray(a).resize((a.shape[1] * z, a.shape[0] * z), Image.NEAREST).save(os.path.join(ROOT, 'work', 'preview', 'gfx_%s_원본_새것.png' % name))
    print(name, '셀 %d · 패치 %d' % (len(ch), len(patches)), sorted({'%s#%d' % (p['file'], p['piece']) for p in patches}))


if __name__ == '__main__':
    for nm in (sys.argv[1:] or JOBS): run(nm)
