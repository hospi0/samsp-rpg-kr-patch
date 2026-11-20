# -*- coding: utf-8 -*-
"""VDP1 스프라이트(4bpp, 모드 0/1) 편집 — 스테이트에서 텍스처·LUT 읽기, 새 텍스처 → 같은 바이트 사본 전부 패치.
  get(state, sa)            → (idx[h,w], lut_rgb[16,3], (w,h,pm,col))
  patches(old_bytes, new_bytes) → work/gfx 패치 항목(파일·조각·머리표 순번·하위 블록 안 오프셋, old/new) — 사본 전부
"""
import os, sys, glob, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import sprites as S, sdp, piece

ROOT = S.ROOT


def get(state, sa):
    v, cram = S.load(state)
    for i, cmd, pm, col, a, w, h, x, y in S.cmds(v):
        if a == sa:
            mode = (pm >> 3) & 7; assert mode in (0, 1), '4bpp 만'
            n = w * h // 2; b = v[sa:sa + n]; a8 = np.frombuffer(b, np.uint8)
            idx = np.stack([a8 >> 4, a8 & 15], 1).ravel().reshape(h, w).astype(int)
            if mode == 1:                                   # LUT 항목: 최상위 비트 1 = RGB, 0 = CRAM 팔레트 번호
                e = np.frombuffer(v[col * 8:col * 8 + 32], '>u2').astype(int); cr = np.frombuffer(cram, '>u2').astype(int)
                e = np.where(e & 0x8000, e, cr[e & 0x7FF]); lut = S.rgb(e)
            else: lut = S.rgb(np.frombuffer(cram, '>u2').astype(int)[((col & 0x7F0) + np.arange(16)) & 0x7FF])
            return idx, lut, (w, h, pm, col, x, y), b
    raise SystemExit('스프라이트 %X 없음' % sa)


def encode(idx):
    h, w = idx.shape; f = idx.ravel()
    return bytes(((int(f[2 * i]) << 4) | int(f[2 * i + 1])) for i in range(len(f) // 2))


def patches(old, new):
    assert len(old) == len(new)
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'files', 'DATA', '*.SDP'))):
        fn = os.path.basename(f)[:-4]; d = open(f, 'rb').read(); i = d.find(old)
        while i >= 0:
            for k, o, s in sdp.entries(d):
                if not (o <= i < o + s): continue
                h = piece.header(d[o:o + s])
                if h:
                    for hi, (t, sub, bo, bs) in enumerate(h):
                        if bo <= i - o and i - o + len(old) <= bo + bs:
                            out.append({'file': fn, 'piece': k, 'type': t, 'sub': sub, 'hidx': hi, 'off': i - o - bo, 'old': old.hex(), 'new': new.hex()})
                else:
                    out.append({'file': fn, 'piece': k, 'type': -1, 'sub': -1, 'hidx': -1, 'off': i - o, 'old': old.hex(), 'new': new.hex()})
            i = d.find(old, i + 1)
    if not out: raise SystemExit('⛔ 디스크 사본 없음')
    return out


def preview(pairs, path, z=3):
    """pairs = [(이름, idx_old, idx_new, lut)] → 원본|새것 세로로"""
    rows = []
    for nm, a, b, lut in pairs:
        A = lut[a].copy(); A[a == 0] = (40, 40, 40); B = lut[b].copy(); B[b == 0] = (40, 40, 40)
        rows.append(np.hstack([A, np.full((a.shape[0], 3, 3), 255, np.uint8), B]))
    W = max(r.shape[1] for r in rows)
    img = np.vstack([np.pad(r, ((0, 3), (0, W - r.shape[1]), (0, 0)), constant_values=90) for r in rows])
    Image.fromarray(img).resize((img.shape[1] * z, img.shape[0] * z), Image.NEAREST).save(path)


def erase(idx, ink, box, period=None):
    """box 안 ink 색 화소 → 바탕: period 가 있으면 같은 줄 ±k·period 의 비잉크 화소, 없으면 0(투명)"""
    x0, y0, x1, y1 = box; out = idx.copy()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if idx[y, x] not in ink: continue
            v = 0
            if period:
                for k in range(1, 40):
                    for xx in (x - k * period, x + k * period):
                        if 0 <= xx < idx.shape[1] and idx[y, xx] not in ink and not (x0 <= xx < x1 and False): v = idx[y, xx]; break
                    else: continue
                    break
            out[y, x] = v
    return out


def text_mask(text, font, w, h, dil=0):
    """글꼴로 상자(w,h)에 맞게 → 농담 0~1 배열(h,w)"""
    big = 6
    for size in range(h * big * 2, 6, -2):
        f = ImageFont.truetype(font, size); im = Image.new('L', (w * big * 3, h * big * 3), 0)
        ImageDraw.Draw(im).text((8, 8), text, fill=255, font=f); bb = im.getbbox()
        if bb and bb[2] - bb[0] <= w * big and bb[3] - bb[1] <= h * big: break
    if dil:
        from PIL import ImageFilter
        im = im.filter(ImageFilter.MaxFilter(dil * big + 1)); bb = im.getbbox()
    g = im.crop(bb); sc = min(w / g.width, h / g.height)
    g = g.resize((max(1, round(g.width * sc)), max(1, round(g.height * sc))), Image.LANCZOS)
    a = np.zeros((h, w)); oy, ox = (h - g.height) // 2, (w - g.width) // 2
    a[oy:oy + g.height, ox:ox + g.width] = np.asarray(g) / 255.0
    return a


def draw(idx, box, a, ramp, outline=None, thr=0.4, grad='level'):
    """농담 a 를 box 에: grad='level' → 농담 높을수록 ramp 뒤쪽, 'row' → 줄(위→아래)마다 ramp 순서. outline = 8방향 1px 테두리 색"""
    x0, y0, x1, y1 = box; m = a >= thr; h, w = m.shape
    if outline is not None:
        p = np.pad(m, 1); ring = np.zeros_like(m)
        for dy in range(3):
            for dx in range(3): ring |= p[dy:dy + h, dx:dx + w]
        ring &= ~m; sub = idx[y0:y0 + h, x0:x0 + w]; sub[ring] = outline
    n = len(ramp)
    for j in range(h):
        for i in range(w):
            if not m[j, i]: continue
            k = min(n - 1, int((a[j, i] - thr) / (1 - thr) * n)) if grad == 'level' else min(n - 1, j * n // h)
            idx[y0 + j, x0 + i] = ramp[k]
    return idx
