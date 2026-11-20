# -*- coding: utf-8 -*-
"""글꼴(work/font_glyphs.npy, 1bpp 16×16) → 일본어 글자 후보. 공통 em 박스로 JIS 후보를 렌더해 정규상관(numpy).
   aww-kr-patch/tools/kanji_ocr.py 방식(«글자별로 늘리지 말 것») 재구현."""
import numpy as np, sys
from PIL import Image, ImageDraw, ImageFont
N = 16; BOX = 64; GB = 16
def vecs(imgs):
    a = imgs.reshape(len(imgs), -1).astype(np.float32); a -= a.mean(1, keepdims=True)
    n = np.linalg.norm(a, axis=1, keepdims=True); n[n < 1e-6] = 1; return a / n
def cands():
    cs = []
    for c in range(0x8140, 0xEAA5):
        try: ch = bytes([c >> 8, c & 0xFF]).decode('cp932')
        except Exception: continue
        if len(ch) == 1: cs.append(ch)
    return sorted(set(cs))
def render(fontpath, chars, size=BOX, idx=0):
    f = ImageFont.truetype(fontpath, size, index=idx)
    def draw(ch):
        im = Image.new('L', (size * 2, size * 2), 0); ImageDraw.Draw(im).text((size // 2, size // 2), ch, fill=255, font=f); return im
    bb = [draw(c).getbbox() for c in '国鬱曇議闘囲']
    l = min(b[0] for b in bb); t = min(b[1] for b in bb); r = max(b[2] for b in bb); btm = max(b[3] for b in bb)
    sz = max(r - l, btm - t); cx, cy = (l + r) // 2, (t + btm) // 2
    crop = (cx - sz // 2, cy - sz // 2, cx - sz // 2 + sz, cy - sz // 2 + sz)
    out = np.zeros((len(chars), N, N), np.float32)
    for k, ch in enumerate(chars):
        out[k] = np.asarray(draw(ch).crop(crop).resize((GB, GB), Image.BOX), np.float32)
    return out
if __name__ == '__main__':
    G0 = np.load('work/font_glyphs.npy').astype(np.float32)
    # 게임 글꼴 공통 상자(한자 칸 합집합) → 정사각 크롭 → GB
    ys, xs = np.nonzero(G0[300:].sum(0)); t, b, l, r = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sz = max(b - t, r - l); print('게임 em', t, b, l, r)
    G = np.zeros((len(G0), sz, sz), np.float32); G[:, :b - t, :r - l] = G0[:, t:b, l:r]
    G = np.stack([np.asarray(Image.fromarray(x * 255).resize((GB, GB), Image.BOX)) for x in G]) if sz != GB else G
    # 게임 글꼴 em 박스 = 16×16 그대로(셀 전체), 후보도 em 전체를 16 으로 줄임
    chars = cands()
    V = []
    for fp, ix in (('C:/Windows/Fonts/msgothic.ttc', 0), ('C:/Windows/Fonts/msmincho.ttc', 0)):
        V.append(vecs(render(fp, chars, idx=ix)))
    g = vecs(G)
    S = np.maximum(g @ V[0].T, g @ V[1].T)
    top = np.argsort(-S, 1)[:, :5]
    np.save('work/ocr_top.npy', top); open('work/ocr_chars.txt', 'w', encoding='utf8').write(''.join(chars))
    np.save('work/ocr_score.npy', np.take_along_axis(S, top, 1))
    print('ok', len(chars))
