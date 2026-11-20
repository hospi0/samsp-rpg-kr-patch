# -*- coding: utf-8 -*-
"""PoC-B — 조각·파일·트랙이 커져서 밀려도 게임이 따라 읽는지.

  python tools/poc_b.py [--pad N] [--check]

PoC-A 내용(한글 12음절·첫 대사 3쪽) + F_KAT2 조각 14 대사 블록 끝에 0 바이트 N(기본 0x900)을 덧붙여
조각이 원래 칸(섹터)을 넘게 만든다.
  1) F_KAT2.SDP 다시 짜기: 조각을 섹터 정렬로 다시 놓고 SDP 머리표(오프셋·크기) 갱신 → 파일이 커짐
  2) 트랙 1 다시 짜기: F_KAT2 뒤(LBA 순) 파일을 모두 밀고, ISO 디렉터리 레코드(LBA·크기, XA 포함)와
     PVD 볼륨 크기 갱신. 옮긴/바뀐 섹터는 머리(MSF)+EDC/ECC 새로 계산
  3) 트랙 2(XA): 섹터 머리 MSF +N. Mode 1 섹터(앞 공백 구간)만 ECC 다시, Mode 2 는 머리만(ECC 가 머리를 0 으로 봄)
  4) 트랙 3~6 원본 그대로, cue 그대로(파일 단위)
산출: work/build/pocb/ (트랙 1·2 + 원본 3~6 복사 아님 — 설치 때 1·2 만 덮어씀)
"""
import os, sys, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdp, piece, cdrom_ecc, poc_a
from iso9660 import Iso

ROOT = poc_a.ROOT
SRC = poc_a.SRC_DIR
TR = os.path.join(SRC, 'Shinsetsu Samurai Spirits - Bushidou Retsuden (Japan) (Track %d).bin')
MD5 = {1: '0fa884818a70b7451d13ce7311f92a78', 2: '61eb2b61d673071d20f3c9de59cc0c10'}
OUTD = os.path.join(ROOT, 'work', 'build', 'pocb')
S = 2352


def bcd(x): return ((x // 10) << 4) | (x % 10)
def msf_bytes(lba):
    a = lba + 150; return bytes([bcd(a // 4500), bcd(a // 75 % 60), bcd(a % 75)])


def mode1_sector(lba, data):
    sec = bytearray(S)
    sec[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
    sec[12:15] = msf_bytes(lba); sec[15] = 1; sec[16:16 + 2048] = data
    return cdrom_ecc.recalc_sector(bytes(sec))


def dir_records(iso):
    """[(디렉터리 섹터 LBA, 섹터 안 위치, 이름, LBA, 크기, 디렉터리?)] — 디렉터리 레코드 위치까지."""
    out = []
    def walk(lba, size):
        data = iso.read(lba, size); pos = 0
        while pos < len(data):
            n = data[pos]
            if n == 0: pos = (pos // 2048 + 1) * 2048; continue
            rec = data[pos:pos + n]
            name = rec[33:33 + rec[32]]
            l, s = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
            isdir = bool(rec[25] & 2)
            out.append((lba + pos // 2048, pos % 2048, name, l, s, isdir))
            if isdir and name not in (b'\x00', b'\x01'): walk(l, s)
            pos += n
    walk(*iso.root())
    return out


def build(pad, write):
    raw1 = open(TR % 1, 'rb').read(); raw2 = open(TR % 2, 'rb').read()
    for k, r in ((1, raw1), (2, raw2)):
        if hashlib.md5(r).hexdigest() != MD5[k]: raise SystemExit('⛔ 원본 트랙 %d md5 불일치' % k)
    iso = Iso(TR % 1)
    fix, newp, (fl, fs), (kl, ks) = poc_a.build('N', False, pad={14: pad}, files_only=True)

    # --- 1) F_KAT2.SDP 다시 짜기 ---
    kat0 = iso.read(kl, ks); ents = sdp.entries(kat0)
    hdr = bytearray(kat0[:0x800]); body = bytearray(); cur = 0x800
    moved = 0
    for k, o, s in ents:
        p = newp.get(k, kat0[o:o + s])
        if cur != o: moved += 1
        body += bytes(cur - 0x800 - len(body)) + p
        struct.pack_into('>II', hdr, k * 8, cur, len(p))
        cur = (cur + len(p) + 0x7FF) & ~0x7FF
    kat = bytes(hdr) + bytes(body); kat += bytes((-len(kat)) % 0x800)
    # 검산: 모든 조각이 새 머리표 자리에 그대로(바뀐 조각은 새 바이트)
    for k, o, s in sdp.entries(kat):
        assert kat[o:o + s] == newp.get(k, kat0[[e for e in ents if e[0] == k][0][1]:][:s])
    assert set(k for k, _, _ in sdp.entries(kat)) == set(k for k, _, _ in ents)
    grow = (len(kat) - ((ks + 0x7FF) & ~0x7FF)) // 0x800
    print('F_KAT2.SDP 0x%X → 0x%X (+%d 섹터), 자리 옮긴 조각 %d개' % (ks, len(kat), grow, moved))
    if grow <= 0: raise SystemExit('PoC-B 는 파일이 커져야 함 — --pad 를 키울 것')

    # --- 2) 트랙 1 ---
    n1 = len(raw1) // S
    recs = dir_records(iso)
    files = {}
    for dlba, dpos, name, l, s, isdir in recs:
        if not isdir: files[(dlba, dpos)] = (name, l, s)
    after = lambda l: l > kl
    # 사용자 데이터 섹터 배열(새 트랙 1)
    user = [raw1[i * S + 16:i * S + 16 + 2048] for i in range(n1)]
    new_n1 = n1 + grow
    newuser = [None] * new_n1
    for i in range(n1):
        j = i + grow if i > kl + (ks + 2047) // 2048 - 1 else i
        if kl <= i < kl + (ks + 2047) // 2048: continue
        newuser[j] = user[i]
    for q in range(len(kat) // 2048): newuser[kl + q] = kat[q * 2048:(q + 1) * 2048]
    nfl = fl + grow if after(fl) else fl                       # 글꼴(FIX.SDP) 새 자리
    fixp = fix + bytes((-len(fix)) % 2048)
    for q in range(len(fixp) // 2048): newuser[nfl + q] = fixp[q * 2048:(q + 1) * 2048]
    assert all(x is not None for x in newuser)
    # 디렉터리 레코드 갱신
    dirsec = {}
    for (dlba, dpos), (name, l, s) in files.items():
        nl = l + grow if after(l) else l
        ns = len(kat) if l == kl else s
        if (nl, ns) != (l, s):
            b = bytearray(dirsec.get(dlba, newuser[dlba]))
            struct.pack_into('<I', b, dpos + 2, nl); struct.pack_into('>I', b, dpos + 6, nl)
            struct.pack_into('<I', b, dpos + 10, ns); struct.pack_into('>I', b, dpos + 14, ns)
            dirsec[dlba] = bytes(b)
    for dlba, b in dirsec.items():
        assert dlba < kl; newuser[dlba] = b
    pvd = bytearray(newuser[16]); vs = struct.unpack_from('<I', pvd, 80)[0]
    struct.pack_into('<I', pvd, 80, vs + grow); struct.pack_into('>I', pvd, 84, vs + grow); newuser[16] = bytes(pvd)
    print('디렉터리 섹터 %d개 고침, 볼륨 %d → %d' % (len(dirsec), vs, vs + grow))
    out1 = bytearray()
    nre = 0
    for i in range(new_n1):
        if i < n1 and newuser[i] == user[i] and i < kl:
            out1 += raw1[i * S:(i + 1) * S]
        else:
            out1 += mode1_sector(i, newuser[i]); nre += 1
    print('트랙 1: %d → %d 섹터, 새로 만든 섹터 %d' % (n1, new_n1, nre))

    # --- 3) 트랙 2 ---
    out2 = bytearray(raw2); n2 = len(raw2) // S; m1 = 0
    for i in range(n2):
        o = i * S
        old = raw2[o + 12:o + 15]
        out2[o + 12:o + 15] = msf_bytes(n1 + i + grow)
        if raw2[o + 15] == 1:
            out2[o:o + S] = cdrom_ecc.recalc_sector(bytes(out2[o:o + S])); m1 += 1
    print('트랙 2: 머리 MSF +%d (%d 섹터, Mode 1 ECC 재계산 %d)' % (grow, n2, m1))

    # --- 되읽기 검산 ---
    if not write: print('검사만(--check) — 디스크 안 씀'); return
    os.makedirs(OUTD, exist_ok=True)
    p1 = os.path.join(OUTD, os.path.basename(TR % 1)); p2 = os.path.join(OUTD, os.path.basename(TR % 2))
    open(p1, 'wb').write(out1); open(p2, 'wb').write(out2)
    iso2 = Iso(p1)
    old = {p: (l, s) for p, l, s in iso.walk()}
    for p, l, s in iso2.walk():
        ol, osz = old[p]
        if p.endswith('/'): assert l == ol; continue
        if p == '/DATA/F_KAT2.SDP': assert iso2.read(l, s) == kat; continue
        if p == '/DATA/FIX.SDP': assert l == nfl and iso2.read(l, s) == fix; continue
        assert l == (ol + grow if ol > kl else ol) and s == osz, p
        if l < new_n1: assert iso2.read(l, s) == iso.read(ol, osz), p
    for k in (1, 2):
        pth = p1 if k == 1 else p2
        print('산출', pth, hashlib.md5(open(pth, 'rb').read()).hexdigest())


if __name__ == '__main__':
    pad = int(sys.argv[sys.argv.index('--pad') + 1], 0) if '--pad' in sys.argv else 0x900
    build(pad, '--check' not in sys.argv)
