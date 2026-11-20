# -*- coding: utf-8 -*-
"""PoC-A — 한글 글자 표시 + 조각 안에서 대사 블록 키우기(조각 머리표 따르는지).

  python tools/poc_a.py [--font A|B|C|D] [--check]      (--check = 디스크 안 씀, 검사만)

바꾸는 것(전부 원본 바이트 확인 후):
  1) FIX.SDP 조각 2(글꼴) — 안 쓰는 한자 칸 12개에 한글 12음절
  2) F_KAT2.SDP 조각 14·26·28·41 대사 블록 — «座禅の最中に⏎また雑念に…» 줄을 한글 2쪽으로(블록이 커짐)
     → 블록 다시 쓰기(포인터 기준, 같은 바이트열 공유), 조각 안 뒤 하위 블록을 밀고 조각 머리표·SDP 머리표 크기 갱신
  3) 트랙 1 에 같은 LBA 로 되쓰기 + 바뀐 섹터 EDC/ECC
산출: work/build/poc_a_t1.bin (나머지 트랙은 원본 그대로 씀)
"""
import os, sys, struct, hashlib, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import sdp, piece, cmap, kglyph, cdrom_ecc
from iso9660 import Iso

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = r'C:\claude\roms\ss\Shinsetsu Samurai Spirits - Bushidou Retsuden (Japan)'
T1 = os.path.join(SRC_DIR, 'Shinsetsu Samurai Spirits - Bushidou Retsuden (Japan) (Track 1).bin')
T1_MD5 = '0fa884818a70b7451d13ce7311f92a78'
OUT = os.path.join(ROOT, 'work', 'build', 'poc_a_t1.bin')

FONTS = {'N': ('ttf:나눔명조ExtraBold', False), 'A': ('Galmuri14', False), 'B': ('Galmuri14', True), 'C': ('Galmuri11-Bold', False), 'D': ('Galmuri11', True)}
SP = 163                     # 대사 띄어쓰기 칸({SP2}, 원문 대사에서 공백으로 쓰임)
OLD_JP = '{0128}座禅の最中に{0501}⏎また{0501}雑念にとらわれおったな'
NEW_KO = ['{0128}', '좌선 중에', '{0501}', '⏎', '또 잡념에 사로잡혔구나', '{0300}', '{0128}',
          '좌선 중에 또 잡념에', '⏎', '사로잡혔구나', '{0300}', '{0128}', '또 잡념에 사로잡혔구나']
PIECES = [14, 26, 28, 41]


def read_file(iso, path):
    for p, l, s in iso.walk():
        if p == path: return l, s, iso.read(l, s)
    raise SystemExit('없음 ' + path)


def build(font_key, write, pad=None, files_only=False):
    """pad = {조각: 블록 끝에 덧붙일 0 바이트} · files_only = 트랙 안 쓰고 (FIX, F_KAT2 새 바이트, 조각별 새 조각 바이트) 반환(PoC-B)"""
    pad = pad or {}; newpieces = {}
    raw = open(T1, 'rb').read()
    if hashlib.md5(raw).hexdigest() != T1_MD5: raise SystemExit('⛔ 원본 트랙 1 md5 불일치')
    iso = Iso(T1)
    T = cmap.load(); R = {c: i for i, c in T.items()}

    # --- 한글 음절 → 빈 칸 ---
    syl = []
    for t in NEW_KO:
        for ch in t:
            if '가' <= ch <= '힣' and ch not in syl: syl.append(ch)
    free = [int(x) for x in open(os.path.join(ROOT, 'work', 'poc_free_slots.txt')).read().split()]
    if len(free) < len(syl): raise SystemExit('빈 칸 부족')
    slot = dict(zip(syl, free))
    print('한글 %d음절 → 칸 %s' % (len(syl), ' '.join('%s%d' % (c, slot[c]) for c in syl)))

    def enc(parts):
        out = []
        for t in parts:
            if t.startswith('{'): out.append(int(t[1:5], 16)); continue
            if t == '⏎': out.append(0x0200); continue
            for ch in t:
                if ch == ' ': out.append(cmap.code(SP))
                elif ch in slot: out.append(cmap.code(slot[ch]))
                else: raise SystemExit('⛔ 인코딩 불가 %r' % ch)   # 인코딩 누락 = 빌드 에러
        return tuple(out)
    new_words = enc(NEW_KO)

    # --- 1) 글꼴 ---
    fl, fs, fix = read_file(iso, '/DATA/FIX.SDP'); fix = bytearray(fix)
    e = {k: (o, s) for k, o, s in sdp.entries(fix)}; fo, fsz = e[2]
    name, bold = FONTS[font_key]
    for ch, i in slot.items():
        g = kglyph.ttf_glyph(ch, name[4:], 16, bold) if name.startswith('ttf:') else kglyph.glyph(ch, name, bold=bold)
        tiles = [g[0:8, 0:8], g[0:8, 8:16], g[8:16, 0:8], g[8:16, 8:16]]
        fix[fo + i * 32: fo + i * 32 + 32] = b''.join(bytes(np.packbits(t, axis=1).ravel()) for t in tiles)

    # --- 2) 대사 블록 ---
    kl, ks, kat = read_file(iso, '/DATA/F_KAT2.SDP'); kat = bytearray(kat)
    ents = sdp.entries(kat); pos = {k: i for i, (k, o, s) in enumerate(ents)}
    for pk in PIECES:
        i = pos[pk]; k, o, s = ents[i]
        slot_end = ents[i + 1][1] if i + 1 < len(ents) else len(kat)
        p = bytes(kat[o:o + s]); h = piece.header(p)
        ti = [j for j, x in enumerate(h) if x[0] == 0x0A]; assert len(ti) == 1
        t_, sub, bo, bs = h[ti[0]]; blk = p[bo:bo + bs]
        cnt, offs = piece.text_block(blk)
        st = {ix: v for ix, x, v in piece.strings(blk)}
        hit = [ix for ix, v in st.items() if cmap.decode(v, T) == OLD_JP]
        if len(hit) != 1: raise SystemExit('⛔ 조각 %d 원문 줄 %d개' % (pk, len(hit)))
        st[hit[0]] = new_words
        # 다시 쓰기: 같은 단어열 공유, 표 순서대로
        body = bytearray(); at = {}; newoffs = []
        base = 2 + 2 * cnt
        for ix in range(cnt):
            if offs[ix] == 0: newoffs.append(0); continue
            v = st[ix]
            if v not in at:
                at[v] = base + len(body); body += struct.pack('>%dH' % len(v), *v) + b'\0\0'
            newoffs.append(at[v])
        nb = struct.pack('>H%dH' % cnt, cnt, *newoffs) + bytes(body) + bytes(pad.get(pk, 0))
        if max(newoffs) > 0xFFFF: raise SystemExit('오프셋 16비트 초과')
        # 검산: 다시 읽으면 바뀐 줄 말고 전부 같아야
        chk = {ix: v for ix, x, v in piece.strings(nb)}
        assert all(chk[ix] == (new_words if ix == hit[0] else st[ix]) for ix in chk) and set(chk) == set(st)
        if len(nb) > 0x7000: raise SystemExit('블록 0x7000 초과')
        delta = len(nb) - bs
        # 조각 다시 쓰기: 텍스트 블록 뒤 하위 블록을 4정렬로 밀기
        shift = (delta + 3) & ~3
        np_ = bytearray(p[:bo]) + nb + b'\0' * (shift - delta) + bytearray(p[bo + bs:])
        nh = []
        for (tt, su, a, b) in h:
            if (tt, su, a) == (t_, sub, bo): nh.append((tt, su, a, len(nb)))
            elif a > bo: nh.append((tt, su, a + shift, b))
            else: nh.append((tt, su, a, b))
        for j, (tt, su, a, b) in enumerate(nh): struct.pack_into('>HHII', np_, 4 + j * 12, tt, su, a, b)
        # 뒤 하위 블록 내용이 옮겨진 자리와 같은지
        for (tt, su, a, b), (_, _, a2, _) in zip(h, nh):
            if (tt, su, a) != (t_, sub, bo): assert p[a:a + b] == bytes(np_[a2:a2 + b])
        newpieces[pk] = bytes(np_)
        if o + len(np_) > slot_end:
            if files_only: print('조각 %2d: 칸 넘침 %d B → PoC-B 가 재배치' % (pk, o + len(np_) - slot_end)); continue
            raise SystemExit('조각 %d 칸 넘침 %d B' % (pk, o + len(np_) - slot_end))
        kat[o:o + len(np_)] = np_
        if len(np_) < s: kat[o + len(np_):o + s] = b'\0' * (s - len(np_))
        struct.pack_into('>I', kat, k * 8 + 4, len(np_))
        print('조각 %2d: 블록 0x%X→0x%X (+%d), 조각 0x%X→0x%X, 칸 여유 남음 0x%X' % (pk, bs, len(nb), delta, s, len(np_), slot_end - o - len(np_)))

    if files_only: return bytes(fix), newpieces, (fl, fs), (kl, ks)
    # --- 3) 트랙 되쓰기 ---
    out = bytearray(raw); ranges = []
    for lba, size, data in ((fl, fs, bytes(fix)), (kl, ks, bytes(kat))):
        assert len(data) == size
        for q in range(0, size, 2048):
            off = (lba * 2352) + 16 + (q // 2048) * 2352 - 0  # 트랙 1 = LBA 0 부터
            chunk = data[q:q + 2048]
            if bytes(out[off:off + len(chunk)]) != chunk:
                out[off:off + len(chunk)] = chunk; ranges.append((off, len(chunk)))
    print('바뀐 섹터 %d개' % len({o // 2352 for o, _ in ranges}))
    if not write:
        print('검사만(--check) — 디스크 안 씀'); return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'wb').write(out)
    with open(OUT, 'r+b') as f: cdrom_ecc.fix_sectors(f, ranges)
    # 되읽기 검산
    iso2 = Iso(OUT)
    assert read_file(iso2, '/DATA/FIX.SDP')[2] == bytes(fix) and read_file(iso2, '/DATA/F_KAT2.SDP')[2] == bytes(kat)
    print('산출', OUT, hashlib.md5(open(OUT, 'rb').read()).hexdigest())


if __name__ == '__main__':
    fk = sys.argv[sys.argv.index('--font') + 1] if '--font' in sys.argv else 'N'   # 2026-11-19 하스피 «일단 첫번째» = 나눔명조 ExtraBold
    build(fk, '--check' not in sys.argv)
