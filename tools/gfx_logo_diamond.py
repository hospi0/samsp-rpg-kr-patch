# -*- coding: utf-8 -*-
"""하스피 이름 그림(work/preview/<이름>.png) → 원본 로고의 «빈 검은 마름모» 위에 얹기 → 미리보기·인덱스 PNG(빌드는 지시 후)
  마름모 = 원본 검정(15) 를 3×3 깎기(가는 획 테두리 제거) → 가장 큰 덩어리 → 3×3 키우기 → 구멍 메우기"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, 'work', 'export_gfx'); PV = os.path.join(ROOT, 'work', 'preview')
NAMES = ('하오마루', '갈포드', '나코루루', '겐쥬로', '우쿄', '참참')


def erode(m):
    p = np.pad(m, 1, constant_values=False); o = np.ones_like(m)
    for dy in range(3):
        for dx in range(3): o &= p[dy:dy + m.shape[0], dx:dx + m.shape[1]]
    return o
def dilate(m):
    p = np.pad(m, 1); o = np.zeros_like(m)
    for dy in range(3):
        for dx in range(3): o |= p[dy:dy + m.shape[0], dx:dx + m.shape[1]]
    return o
def largest(m):
    lab = np.zeros(m.shape, int); best = None; n = 0
    for y, x in zip(*np.nonzero(m)):
        if lab[y, x]: continue
        n += 1; st = [(y, x)]; lab[y, x] = n; cnt = 0
        while st:
            cy, cx = st.pop(); cnt += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = cy + dy, cx + dx
                    if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and not lab[yy, xx]: lab[yy, xx] = n; st.append((yy, xx))
        if best is None or cnt > best[1]: best = (n, cnt)
    return lab == best[0]
def fill_holes(m):
    out = np.zeros_like(m); st = [(y, x) for y in range(m.shape[0]) for x in (0, m.shape[1] - 1)] + [(y, x) for x in range(m.shape[1]) for y in (0, m.shape[0] - 1)]
    seen = np.zeros_like(m)
    while st:
        y, x = st.pop()
        if not (0 <= y < m.shape[0] and 0 <= x < m.shape[1]) or seen[y, x] or m[y, x]: continue
        seen[y, x] = True; st += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return ~seen


def hull(m):
    """점들의 볼록 다각형(앤드루) → 채운 마스크, 1px 키움"""
    from PIL import ImageDraw
    pts = sorted(set((int(x), int(y)) for y, x in zip(*np.nonzero(m))))
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo = []; up = []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    poly = lo[:-1] + up[:-1]
    im = Image.new('L', (m.shape[1], m.shape[0]), 0); ImageDraw.Draw(im).polygon(poly, fill=1, outline=1)
    return dilate(np.asarray(im).astype(bool))


def main():
    rows = []
    for nm in NAMES:
        o = Image.open(os.path.join(EX, '이름로고_%s_원본.png' % nm)); pal = np.array(o.getpalette()[:48]).reshape(16, 3); oi = np.asarray(o).astype(int)
        H, W = oi.shape
        dia = hull(erode(oi == 15))
        u = np.asarray(Image.open(os.path.join(PV, nm + '.png')).convert('RGBA')).astype(int)
        if u.shape[0] > H:                                   # 64×32 → 64×31: 아래 줄이 비면 자르고, 아니면 위 줄을 자름
            u = u[:H] if (u[H:, :, 3] < 128).all() else u[u.shape[0] - H:]
        d = ((u[..., None, :3] - pal[None, None, 1:, :]) ** 2).sum(-1); ui = d.argmin(-1) + 1; ui[u[..., 3] < 128] = 0
        new = np.where(dia, 15, 0); new[ui > 0] = ui[ui > 0]
        q = Image.new('P', (W, H)); q.putpalette([int(c) for c in pal.ravel()] + [0] * (768 - 48)); q.putdata(new.ravel().tolist())
        q.save(os.path.join(PV, '이름로고_%s_마름모합성_인덱스.png' % nm), transparency=0)
        def rgb(a):
            r = pal[a].astype(np.uint8); r[a == 0] = (90, 90, 90); return r
        e = np.zeros((H, W), int); e[dia] = 15
        rows.append(np.hstack([rgb(oi), np.full((H, 2, 3), 255, np.uint8), rgb(e), np.full((H, 2, 3), 255, np.uint8), rgb(new)]))
    img = np.vstack([np.pad(r, ((0, 2), (0, 0), (0, 0)), constant_values=255) for r in rows])
    Image.fromarray(img).resize((img.shape[1] * 4, img.shape[0] * 4), Image.NEAREST).save(os.path.join(PV, '이름로고_원본_빈마름모_합성.png'))
    print('ok')


if __name__ == '__main__':
    main()
