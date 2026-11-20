# -*- coding: utf-8 -*-
"""한글 16×16 1bpp 글자 — BDF(Galmuri) 읽기. 세로 = 한글 공통 상자(가~힣 합집합)를 칸 안 위아래 가운데. 가로 = BDF xo 그대로 + 칸 가운데 보정.
   bold=True → 가로 1px 굵게(게임 글꼴 세로획 2px 맞춤 후보)."""
import numpy as np
FONTS = {'Galmuri14': 'C:/claude/utils/font/Galmuri-v2.40.3/Galmuri14.bdf',
         'Galmuri11-Bold': 'C:/claude/utils/font/Galmuri-v2.40.3/Galmuri11-Bold.bdf',
         'Galmuri11': 'C:/claude/utils/font/Galmuri-v2.40.3/Galmuri11.bdf'}
_cache = {}
def load(name):
    if name in _cache: return _cache[name]
    gl = {}; cur = None
    for line in open(FONTS[name], encoding='latin1'):
        t = line.split()
        if not t: continue
        if t[0] == 'ENCODING': cur = {'enc': int(t[1])}
        elif t[0] == 'BBX' and cur is not None: cur['bbx'] = list(map(int, t[1:5]))
        elif t[0] == 'BITMAP' and cur is not None: cur['rows'] = []
        elif t[0] == 'ENDCHAR' and cur is not None: gl[cur['enc']] = cur; cur = None
        elif cur is not None and 'rows' in cur: cur['rows'].append(t[0])
    # 한글 공통 상자 (기준선 기준 위/아래)
    top = max(g['bbx'][3] + g['bbx'][1] for c, g in gl.items() if 0xAC00 <= c <= 0xD7A3)
    bot = min(g['bbx'][3] for c, g in gl.items() if 0xAC00 <= c <= 0xD7A3)
    _cache[name] = (gl, top, bot); return _cache[name]
def glyph(ch, name='Galmuri14', bold=False, cell=16):
    gl, top, bot = load(name); g = gl.get(ord(ch))
    if g is None: raise KeyError('글꼴에 없는 글자 %r (%s)' % (ch, name))
    w, h, xo, yo = g['bbx']; H = top - bot
    oy = (cell - 1 - H) // 2          # 게임 글자 잉크 행 0~14 → 위 여백 계산
    a = np.zeros((cell, cell), np.uint8)
    for r, hx in enumerate(g['rows']):
        v = int(hx, 16); nb = len(hx) * 4
        for x in range(w):
            if v >> (nb - 1 - x) & 1:
                X = xo + x; Y = oy + (top - (yo + h)) + r
                if 0 <= X < cell and 0 <= Y < cell: a[Y, X] = 1
                else: raise ValueError('칸 밖 %r' % ch)
    if bold:
        b = a.copy(); b[:, 1:] |= a[:, :-1]; a = b
    return a


# --- TTF 1비트 렌더(명조 후보) ---
from PIL import Image, ImageDraw, ImageFont
TTF = {'나눔명조': 'C:/claude/utils/font/nanum-myeongjo/NanumMyeongjo.ttf',
       '나눔명조Bold': 'C:/claude/utils/font/nanum-myeongjo/NanumMyeongjoBold.ttf',
       '나눔명조ExtraBold': 'C:/claude/utils/font/nanum-myeongjo/NanumMyeongjoExtraBold.ttf',
       '고운바탕': 'C:/claude/utils/font/gowunbatang/GowunBatang-Regular.ttf',
       '고운바탕Bold': 'C:/claude/utils/font/gowunbatang/GowunBatang-Bold.ttf',
       '송명': 'C:/claude/utils/font/songmyung/SongMyung-Regular.ttf',
       '바탕(MS·참고)': 'C:/Windows/Fonts/batang.ttc'}
_tbox = {}
def set_box(name, size, chars):
    """글자 상자를 «실제로 쓸 글자 전체»로 잡음(표본 몇 자로 잡으면 ㅎ 윗점·긴 받침이 잘림)"""
    f = ImageFont.truetype(TTF[name], size); bb = []
    for c in chars:
        im = Image.new('1', (size * 4, size * 4), 0); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.text((size, size), c, fill=1, font=f); b = im.getbbox()
        if b: bb.append(b)
    # ttf_glyph 의 그리기 원점(cell)과 맞추기 위해 cell=16 기준으로 다시 잼
    f2 = f; bb = []
    for c in chars:
        im = Image.new('1', (48, 48), 0); d = ImageDraw.Draw(im); d.fontmode = '1'; d.text((16, 16), c, fill=1, font=f2); b = im.getbbox()
        if b: bb.append(b)
    _tbox[(name, size)] = (min(b[0] for b in bb), min(b[1] for b in bb), max(b[2] for b in bb), max(b[3] for b in bb))
    return _tbox[(name, size)]


def ttf_glyph(ch, name, size=16, bold=False, cell=16):
    f = ImageFont.truetype(TTF[name], size)
    def draw(c):
        im = Image.new('1', (cell * 3, cell * 3), 0); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.text((cell, cell), c, fill=1, font=f); return im
    key = (name, size)
    if key not in _tbox:
        bb = [x for x in (draw(c).getbbox() for c in '가각한글를많뼈힘깊빠름쀍뾩') if x]
        t = min(b[1] for b in bb); btm = max(b[3] for b in bb); l = min(b[0] for b in bb); r = max(b[2] for b in bb)
        _tbox[key] = (l, t, r, btm)
    l, t, r, btm = _tbox[key]
    H = btm - t; W = r - l
    oy = (cell - 1 - H) // 2; ox = (cell - W) // 2
    a = np.asarray(draw(ch), np.uint8)[t - oy:t - oy + cell, l - ox:l - ox + cell].copy()
    if bold:
        b = a.copy(); b[:, 1:] |= a[:, :-1]; a = b
    return a


# --- 붓글씨 작은 글자(전투 커맨드 등, 하스피 2026-11-19 «붓글씨 손글씨 느낌») ---
YEONSUNG = 'C:/claude/utils/font/yeonsung/YeonSung-Regular.ttf'
def brush_glyph(ch, w, h, font=YEONSUNG, thr=90):
    """큰 크기로 그려 BOX 축소 → 문턱 → 가로 1px 굵게. (w,h) 안 가운데"""
    big = 12; f = ImageFont.truetype(font, h * big)
    im = Image.new('L', (w * big * 2, h * big * 2), 0); ImageDraw.Draw(im).text((10, 10), ch, fill=255, font=f)
    g = im.crop(im.getbbox()); sc = min((w - 1) / g.width, h / g.height)
    g = g.resize((max(1, round(g.width * sc)), max(1, round(g.height * sc))), Image.BOX)
    a = np.asarray(g) > thr; b = a.copy(); b[:, 1:] |= a[:, :-1]
    out = np.zeros((h, w), bool); oy = (h - b.shape[0]) // 2; ox = (w - b.shape[1]) // 2
    out[oy:oy + b.shape[0], ox:ox + b.shape[1]] = b
    return out


PEN = 'C:/claude/utils/font/nanum-pen/NanumPenScript-Regular.ttf'
def brush_line(text, w, h, font=PEN, thr=80, bold=True):
    """한 줄 글씨(손글씨/붓) — 크게 그려 BOX 축소 → 문턱 → 가로 1px 굵게, 높이 h 기준(폭 넘치면 줄임)"""
    big = 10; f = ImageFont.truetype(font, h * big)
    im = Image.new('L', (len(text) * h * big * 2 + 40, h * big * 2), 0); ImageDraw.Draw(im).text((10, 10), text, fill=255, font=f)
    g = im.crop(im.getbbox()); sc = min((w - 1) / g.width, h / g.height)
    g = g.resize((max(1, round(g.width * sc)), max(1, round(g.height * sc))), Image.BOX)
    a = np.asarray(g) > thr
    if bold: b = a.copy(); b[:, 1:] |= a[:, :-1]; a = b
    out = np.zeros((h, w), bool); oy = (h - a.shape[0]) // 2
    out[oy:oy + a.shape[0], 0:a.shape[1]] = a
    return out
