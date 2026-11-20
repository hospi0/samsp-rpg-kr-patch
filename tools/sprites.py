# -*- coding: utf-8 -*-
"""스테이트의 VDP1 스프라이트 전부 → 시트 그림 + 출처(디스크 파일 무압축 일치).

  python tools/sprites.py <스테이트…>  → work/sheet/<스테이트>.png · work/sheet/<스테이트>.tsv
  (airsadventure tools/spritesheet.py·vdp1cmd.py 방식, 이 프로젝트 RZIP+Mednafen 스테이트용)
"""
import os, sys, struct, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw
import rzip, mdfnstate as M, sdp, piece

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_files = None


def files():
    global _files
    if _files is None:
        _files = [('1ST.BIN', open(os.path.join(ROOT, 'work', 'files', '1ST.BIN'), 'rb').read())]
        for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'files', 'DATA', '*.SDP'))):
            _files.append((os.path.basename(f)[:-4], open(f, 'rb').read()))
    return _files


def locate(tex):
    """텍스처 바이트 → [(파일, 조각, 하위블록, 하위블록 안 오프셋, 파일 오프셋)]"""
    out = []
    if len(set(tex)) < 3: return out
    for fn, d in files():
        i = d.find(tex)
        while i >= 0 and len(out) < 6:
            loc = fn
            if fn != '1ST.BIN':
                for k, o, s in sdp.entries(d):
                    if o <= i < o + s:
                        h = piece.header(d[o:o + s]); loc = '%s#%d+%X' % (fn, k, i - o)
                        for t, sub, bo, bs in (h or []):
                            if bo <= i - o < bo + bs: loc = '%s#%d/%X.%d+%X' % (fn, k, t, sub, i - o - bo)
            out.append((loc, fn, i)); i = d.find(tex, i + 1)
    return out


def load(state):
    d = rzip.unpack(os.path.join(ROOT, 'work', 'states_user', state + '.state'))[0]; S = M.sections(d)
    return M.swap16(S['VDP1']['VRAM']), M.swap16(S['VDP2']['CRAM'])


def cmds(v):
    """JP: 하위 2비트 0 다음·1 점프·2 호출·3 복귀, 비트 2 = 이 명령 건너뜀(그리지 않음)"""
    i = 0; seen = set(); out = []; stack = []
    sx = lambda u: struct.unpack('>h', struct.pack('>H', u))[0]
    while len(seen) < 4000 and i * 32 < len(v):
        if (i, len(stack)) in seen: break
        seen.add((i, len(stack))); c = struct.unpack_from('>16H', v, i * 32)
        if c[0] & 0x8000: break
        cmd = c[0] & 0xF; jp = (c[0] >> 12) & 7
        if not jp & 4 and cmd in (0, 1, 2):
            out.append((i, cmd, c[2], c[3], c[4] * 8, ((c[5] >> 8) & 0x3F) * 8, c[5] & 0xFF, sx(c[6]), sx(c[7])))
        j = jp & 3
        if j == 0: i += 1
        elif j == 1: i = c[1] // 4
        elif j == 2: stack.append(i + 1); i = c[1] // 4
        else: i = stack.pop() if stack else i + 1
    return out


def rgb(e):
    e = np.asarray(e).astype(int)
    return np.stack([(e & 31) << 3, (e >> 5 & 31) << 3, (e >> 10 & 31) << 3], -1).astype(np.uint8)


def texbytes(pm, w, h):
    mode = (pm >> 3) & 7
    return {0: w * h // 2, 1: w * h // 2, 2: w * h, 3: w * h, 4: w * h, 5: w * h * 2}.get(mode)


def render(v, cram, pm, col, sa, w, h):
    mode = (pm >> 3) & 7; n = texbytes(pm, w, h)
    if n is None or sa + n > len(v): return None
    cr = np.frombuffer(cram, '>u2').astype(int)
    if mode == 5: return rgb(np.frombuffer(v[sa:sa + n], '>u2').reshape(h, w))
    if mode in (0, 1):
        a = np.frombuffer(v[sa:sa + n], np.uint8); idx = np.stack([a >> 4, a & 15], 1).ravel().reshape(h, w).astype(int)
        img = rgb(np.frombuffer(v[col * 8:col * 8 + 32], '>u2').astype(int)[idx]) if mode == 1 else rgb(cr[((col & 0x7F0) + idx) & 0x7FF])
    else:
        idx = np.frombuffer(v[sa:sa + n], np.uint8).reshape(h, w).astype(int); img = rgb(cr[((col & 0x700) + idx) & 0x7FF])
    img[idx == 0] = (255, 0, 255)
    return img


def sheet(state):
    v, cram = load(state); items = []; seen = set(); rows = []
    for i, cmd, pm, col, sa, w, h, x, y in cmds(v):
        k = (pm, col, sa, w, h)
        if k in seen or w * h < 64: continue
        seen.add(k); im = render(v, cram, pm, col, sa, w, h)
        if im is None: continue
        n = texbytes(pm, w, h); src = locate(v[sa:sa + n])
        lab = '%05X %dx%d m%d' % (sa, w, h, (pm >> 3) & 7)
        items.append((lab, im)); rows.append((lab, x, y, ' | '.join(s[0] for s in src) or '-'))
    W = 1400; x = y = 0; rowh = 0; pos = []
    for lab, im in items:
        h, w = im.shape[:2]; sc = 2 if w <= 160 and h <= 120 else 1
        if x + w * sc > W: x = 0; y += rowh + 4; rowh = 0
        pos.append((x, y, sc)); x += max(w * sc, 90) + 6; rowh = max(rowh, h * sc + 12)
    cv = Image.new('RGB', (W, y + rowh + 4), (30, 30, 30)); dr = ImageDraw.Draw(cv)
    for (lab, im), (x, y, sc) in zip(items, pos):
        cv.paste(Image.fromarray(im).resize((im.shape[1] * sc, im.shape[0] * sc), Image.NEAREST), (x, y + 12)); dr.text((x, y), lab, fill=(255, 255, 0))
    os.makedirs(os.path.join(ROOT, 'work', 'sheet'), exist_ok=True)
    cv.save(os.path.join(ROOT, 'work', 'sheet', '%s.png' % state))
    open(os.path.join(ROOT, 'work', 'sheet', '%s.tsv' % state), 'w', encoding='utf8').write(
        '\n'.join('%s\t화면(%d,%d)\t%s' % r for r in rows) + '\n')
    return len(items)


if __name__ == '__main__':
    for s in sys.argv[1:]: print(s, sheet(s))
