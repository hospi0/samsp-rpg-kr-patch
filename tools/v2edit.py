# -*- coding: utf-8 -*-
"""VDP2 층 영역 편집기 — 스테이트 화면 영역의 색 번호 화소를 읽고, 고친 화소를 «셀 → 디스크 파일 위치»로 되돌린다.

  cells(state, n)                  → {(타일 x, 타일 y): (VRAM 주소, 팔레트, hf, vf)}  (8×8 단위, 16색 층)
  read(state, n, x, y, w, h)       → (색 번호 배열[h,w], 팔레트 번호 배열)
  plan(state, n, x, y, w, h, new)  → {VRAM 주소: 새 32 B}  (같은 셀이 영역 밖에서도 쓰이면 오류)
  vram_to_file(state, addr)        → (파일, 파일 오프셋) — work/vram_src_<state>.txt 의 VDP2 구간 사용
"""
import os, sys, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import vdp2render as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cells(state, n):
    v, reg, cram = V.load(state); I = V.info(reg, n)
    assert not I['bmen'] and I['colors'] == 16, '16색 셀 층만'
    one = (I['pncn'] >> 15) & 1; cnsm = (I['pncn'] >> 14) & 1
    tiles = 2 if I['chsz'] else 1; ncell = 64 if not I['chsz'] else 32
    pagebytes = ncell * ncell * (2 if one else 4)
    base = ((((I['mpof'] << 6) | I['mpA'])) * pagebytes) % len(v)
    out = {}
    for cy in range(ncell):
        for cx in range(ncell):
            o = (base + (cy * ncell + cx) * (2 if one else 4)) % len(v)
            if one:
                w = struct.unpack_from('>H', v, o)[0]; pal = (w >> 12) & 0xF
                if cnsm == 0:
                    chn = (((I['pncn'] >> 2) & 7) << 12) | ((w & 0x3FF) << 2) | (I['pncn'] & 3) if I['chsz'] else (w & 0x3FF) | ((I['pncn'] & 0x1F) << 10)
                    hf, vf = (w >> 10) & 1, (w >> 11) & 1
                else:
                    chn = (w & 0xFFF) | ((I['pncn'] & 0x1C) << 10); hf = vf = 0
                pal |= ((I['pncn'] >> 5) & 7) << 4
            else:
                w0, w1 = struct.unpack_from('>HH', v, o); chn = w1 & 0x7FFF; pal = w0 & 0x7F; hf, vf = (w0 >> 14) & 1, (w0 >> 15) & 1
            for ty in range(tiles):
                for tx in range(tiles):
                    k = ty * tiles + tx; addr = (chn + k) * 0x20
                    yy = cy * tiles + (tiles - 1 - ty if vf else ty); xx = cx * tiles + (tiles - 1 - tx if hf else tx)
                    out[(xx, yy)] = (addr, pal, hf, vf)
    return out, v, cram, I


def px(v, addr, hf, vf):
    a = np.frombuffer(v[addr:addr + 32], np.uint8); p = np.stack([a >> 4, a & 15], 1).ravel().reshape(8, 8).astype(int)
    if hf: p = p[:, ::-1]
    if vf: p = p[::-1]
    return p


def read(state, n, x, y, w, h):
    C, v, cram, I = cells(state, n)
    idx = np.zeros((h, w), int); pal = np.zeros((h, w), int)
    for ty in range(y // 8, (y + h + 7) // 8):
        for tx in range(x // 8, (x + w + 7) // 8):
            addr, pl, hf, vf = C[(tx, ty)]; p = px(v, addr, hf, vf)
            for j in range(8):
                for i in range(8):
                    X, Y = tx * 8 + i - x, ty * 8 + j - y
                    if 0 <= X < w and 0 <= Y < h: idx[Y, X] = p[j, i]; pal[Y, X] = pl
    return idx, pal, cram, I


def plan(state, n, x, y, w, h, new):
    """new = 영역 색 번호 배열. 영역 타일이 다른 곳(영역 밖)에서도 쓰이면 오류. 반환 {VRAM 주소: 32 B}"""
    assert x % 8 == 0 and y % 8 == 0 and w % 8 == 0 and h % 8 == 0, '영역은 8 픽셀 단위'
    C, v, cram, I = cells(state, n)
    inside = {(tx, ty) for ty in range(y // 8, (y + h) // 8) for tx in range(x // 8, (x + w) // 8)}
    users = {}
    for k, (addr, pl, hf, vf) in C.items(): users.setdefault(addr, set()).add(k)
    out = {}
    for (tx, ty) in sorted(inside):
        addr, pl, hf, vf = C[(tx, ty)]
        p = new[(ty * 8 - y):(ty * 8 - y) + 8, (tx * 8 - x):(tx * 8 - x) + 8].copy()
        if vf: p = p[::-1]
        if hf: p = p[:, ::-1]
        b = bytes(((int(p[j, 2 * i]) << 4) | int(p[j, 2 * i + 1])) for j in range(8) for i in range(4))
        if b == v[addr:addr + 32]: continue
        outside = users[addr] - inside
        if outside: raise SystemExit('⛔ 셀 0x%X 이 영역 밖 %s 에서도 쓰임' % (addr, sorted(outside)[:4]))
        if addr in out and out[addr] != b: raise SystemExit('⛔ 셀 0x%X 영역 안에서 다른 내용으로 두 번' % addr)
        out[addr] = b
    return out


def vram_map(state):
    m = []
    for l in open(os.path.join(ROOT, 'work', 'vram_src_%s.txt' % state), encoding='utf8'):
        r = re.match(r'(VDP\d) 0x([0-9A-F]+)~0x([0-9A-F]+) ← (\S+)', l)
        if r: m.append((r.group(1), int(r.group(2), 16), int(r.group(3), 16), r.group(4)))
    return m


def to_patches(state, layer_vdp, changes):
    """{VRAM 주소: 바이트} → [{'loc': '파일#조각/종류.번호', 'off': 하위블록 안 오프셋, 'old': hex, 'new': hex}] — 같은 그림 사본 전부.
    출처는 work/vram_src_<state>.txt(64 B 덩어리 연속 일치 구간)."""
    import sdp, piece
    M = [m for m in vram_map(state) if m[0] == layer_vdp]
    out = []
    for addr, b in sorted(changes.items()):
        hit = False
        for _, a0, a1, loc in M:
            if not (a0 <= addr and addr + len(b) <= a1): continue
            r = re.match(r'(\w+)#(\d+)/([0-9A-F]+)\.(\d+)\+([0-9A-F]+)', loc)
            if not r: continue
            fn, k, t, sub, off0 = r.group(1), int(r.group(2)), int(r.group(3), 16), int(r.group(4)), int(r.group(5), 16)
            off = off0 + addr - a0
            out.append({'file': fn, 'piece': k, 'type': t, 'sub': sub, 'off': off, 'new': b.hex()}); hit = True
        if not hit: raise SystemExit('⛔ VRAM 0x%X 의 디스크 출처 없음' % addr)
    # 원문 바이트 확인
    cache = {}
    for p in out:
        d = cache.setdefault(p['file'], open(os.path.join(ROOT, 'work', 'files', 'DATA', p['file'] + '.SDP'), 'rb').read())
        e = {k: (o, s) for k, o, s in sdp.entries(d)}; o, s = e[p['piece']]
        h = [x for x in piece.header(d[o:o + s]) if (x[0], x[1]) == (p['type'], p['sub'])][0]
        a = o + h[2] + p['off']; p['old'] = d[a:a + len(p['new']) // 2].hex()
    return out


_whole = {}
def whole_blocks(state, vdp):
    """VRAM 에 «하위 블록 통째로» 올라간 곳 → [(VRAM 시작, 길이, 파일, 조각, 종류, 번호)] (64 B 이상, 내용 있는 블록만)"""
    key = (state, vdp)
    if key in _whole: return _whole[key]
    import glob, sdp, piece, rzip, mdfnstate as MS
    d = rzip.unpack(os.path.join(ROOT, 'work', 'states_user', state + '.state'))[0]; S = MS.sections(d)
    vr = MS.swap16(S[vdp]['VRAM']); out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'files', 'DATA', '*.SDP'))):
        fn = os.path.basename(f)[:-4]; dd = open(f, 'rb').read()
        for k, o, s in sdp.entries(dd):
            hdr = piece.header(dd[o:o + s])
            if not hdr and s >= 0x400:                                 # 머리표 없는 조각(FIX#0 등) = 통째
                b = dd[o:o + s]
                if len(set(b)) >= 8:
                    i = vr.find(b)
                    while i >= 0: out.append((i, s, fn, k, (-1, -1, -1), None)); i = vr.find(b, i + 1)
            for hi, (t, sub, bo, bs) in enumerate(hdr or []):
                b = dd[o + bo:o + bo + bs]
                if bs < 64 or len(set(b)) < 8: continue
                i = vr.find(b)
                while i >= 0:
                    out.append((i, bs, fn, k, (t, sub, hi), None)); i = vr.find(b, i + 1)
    _whole[key] = out
    return out


def to_patches2(state, vdp, changes):
    W = whole_blocks(state, vdp); out = []
    for addr, b in sorted(changes.items()):
        hits = [(fn, k, tsh, addr - a) for a, n, fn, k, tsh, _ in W if a <= addr and addr + len(b) <= a + n]
        if not hits: raise SystemExit('⛔ VRAM 0x%X: 통째로 올라간 하위 블록 없음' % addr)
        import rzip as _r, mdfnstate as _m
        for fn, k, (t, sub, hi), off in hits:
            out.append({'file': fn, 'piece': k, 'type': t, 'sub': sub, 'hidx': hi, 'off': off, 'new': b.hex(), 'old': old_bytes(fn, k, hi, off, len(b)).hex()})
    return out


def old_bytes(fn, k, hi, off, n):
    import sdp, piece
    d = open(os.path.join(ROOT, 'work', 'files', 'DATA', fn + '.SDP'), 'rb').read()
    e = {kk: (o, s) for kk, o, s in sdp.entries(d)}; o, s = e[k]
    if hi < 0: return d[o + off:o + off + n]
    t, sub, bo, bs = piece.header(d[o:o + s])[hi]
    return d[o + bo + off:o + bo + off + n]
