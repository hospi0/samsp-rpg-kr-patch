# -*- coding: utf-8 -*-
"""디스크 재조립(PoC-B 일반화, 실기 통과 2026-11-19): 바뀐 파일을 넣고 커진 만큼 뒤 파일을 밀기.

rebuild(new_files) — new_files = {'/DATA/F_KAT2.SDP': bytes, ...} (트랙 1 파일만)
  · 파일을 LBA 순으로 다시 놓음(커지면 뒤 파일 전부 밀림, 줄면 원래 칸 유지 — 섹터 수 줄이지 않음)
  · ISO 디렉터리 레코드(LBA·크기, 트랙 2 XA 포함) · PVD 볼륨 크기 갱신
  · 트랙 1: 바뀐/옮긴 섹터만 MSF+EDC/ECC 새로(나머지 원본 바이트), 트랙 2: 머리 MSF +밀린 섹터(Mode 1 만 ECC)
반환 (트랙1 바이트, 트랙2 바이트, 보고 dict)
"""
import os, sys, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdrom_ecc
from iso9660 import Iso

SRC = r'C:\claude\roms\ss\Shinsetsu Samurai Spirits - Bushidou Retsuden (Japan)'
TR = os.path.join(SRC, 'Shinsetsu Samurai Spirits - Bushidou Retsuden (Japan) (Track %d).bin')
MD5 = {1: '0fa884818a70b7451d13ce7311f92a78', 2: '61eb2b61d673071d20f3c9de59cc0c10'}
S = 2352


def bcd(x): return ((x // 10) << 4) | (x % 10)
def msf_bytes(lba):
    a = lba + 150; return bytes([bcd(a // 4500), bcd(a // 75 % 60), bcd(a % 75)])
def mode1_sector(lba, data):
    sec = bytearray(S); sec[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
    sec[12:15] = msf_bytes(lba); sec[15] = 1; sec[16:16 + 2048] = data
    return cdrom_ecc.recalc_sector(bytes(sec))


def dir_records(iso):
    out = []
    def walk(lba, size, prefix):
        data = iso.read(lba, size); pos = 0
        while pos < len(data):
            n = data[pos]
            if n == 0: pos = (pos // 2048 + 1) * 2048; continue
            rec = data[pos:pos + n]; name = rec[33:33 + rec[32]]
            l, s = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
            isdir = bool(rec[25] & 2)
            path = prefix + name.decode('ascii', 'replace').split(';')[0]
            out.append((lba + pos // 2048, pos % 2048, path, l, s, isdir))
            if isdir and name not in (b'\x00', b'\x01'): walk(l, s, path + '/')
            pos += n
    walk(*iso.root(), '/')
    return out


def originals():
    r1 = open(TR % 1, 'rb').read(); r2 = open(TR % 2, 'rb').read()
    for k, r in ((1, r1), (2, r2)):
        if hashlib.md5(r).hexdigest() != MD5[k]: raise SystemExit('⛔ 원본 트랙 %d md5 불일치' % k)
    return r1, r2


def rebuild(new_files):
    raw1, raw2 = originals(); iso = Iso(TR % 1); n1 = len(raw1) // S
    recs = dir_records(iso)
    files = sorted({(l, s, p) for _, _, p, l, s, d in recs if not d and l < n1})
    for p in new_files:
        if p not in {f[2] for f in files}: raise SystemExit('트랙 1 에 없는 파일 ' + p)
    first_data = files[0][0]
    user = [raw1[i * S + 16:i * S + 16 + 2048] for i in range(n1)]
    newuser = list(user[:first_data])
    newpos = {}; shift = 0
    for l, s, p in files:
        nl = l + shift
        if nl != len(newuser): raise SystemExit('파일 사이 빈 섹터 가정 깨짐 %s' % p)
        data = new_files.get(p)
        oldsec = (s + 2047) // 2048
        if data is None:
            newuser += user[l:l + oldsec]; ns = s; nsec = oldsec
        else:
            nsec = max(oldsec, (len(data) + 2047) // 2048); ns = len(data)
            pad = data + bytes(nsec * 2048 - len(data))
            newuser += [pad[q * 2048:(q + 1) * 2048] for q in range(nsec)]
        newpos[p] = (nl, ns); shift += nsec - oldsec
    tail = user[files[-1][0] + (files[-1][1] + 2047) // 2048:]
    newuser += tail
    grow = len(newuser) - n1
    assert grow == shift
    # 디렉터리·PVD
    dirsec = {}
    for dlba, dpos, p, l, s, isdir in recs:
        if isdir: continue
        nl, ns = newpos.get(p, (l + grow if l >= n1 else l, s))
        if (nl, ns) != (l, s):
            b = bytearray(dirsec.get(dlba, newuser[dlba]))
            struct.pack_into('<I', b, dpos + 2, nl); struct.pack_into('>I', b, dpos + 6, nl)
            struct.pack_into('<I', b, dpos + 10, ns); struct.pack_into('>I', b, dpos + 14, ns)
            dirsec[dlba] = bytes(b)
    for dlba, b in dirsec.items():
        assert dlba < first_data; newuser[dlba] = b
    pvd = bytearray(newuser[16]); vs = struct.unpack_from('<I', pvd, 80)[0]
    struct.pack_into('<I', pvd, 80, vs + grow); struct.pack_into('>I', pvd, 84, vs + grow); newuser[16] = bytes(pvd)
    out1 = bytearray(); nre = 0
    for i, u in enumerate(newuser):
        if i < n1 and u == user[i]:            # 같은 LBA·같은 데이터 = 원본 섹터 그대로(MSF 는 LBA 로만 정해짐)
            out1 += raw1[i * S:(i + 1) * S]
        else:
            out1 += mode1_sector(i, u); nre += 1
    out2 = bytearray(raw2)
    if grow:
        for i in range(len(raw2) // S):
            o = i * S
            out2[o + 12:o + 15] = msf_bytes(n1 + i + grow)
            if raw2[o + 15] == 1: out2[o:o + S] = cdrom_ecc.recalc_sector(bytes(out2[o:o + S]))
    rep = {'grow': grow, 'n1': n1, 'new_n1': len(newuser), 'resect': nre, 'dirsec': len(dirsec), 'newpos': newpos}
    return bytes(out1), bytes(out2), rep


def verify(out1, new_files, rep, tmp_path):
    """되읽기: 바뀐 파일은 새 바이트, 나머지는 원본과 같은 내용·밀린 LBA"""
    open(tmp_path, 'wb').write(out1)
    iso0 = Iso(TR % 1); iso2 = Iso(tmp_path); old = {p: (l, s) for p, l, s in iso0.walk()}
    n1 = rep['n1']; bad = []
    for p, l, s in iso2.walk():
        if p.endswith('/'): continue
        ol, osz = old[p]
        if p in new_files:
            if (l, s) != rep['newpos'][p] or iso2.read(l, s) != new_files[p]: bad.append(p)
        elif ol < n1:
            if (l, s) != rep['newpos'][p] or iso2.read(l, s) != iso0.read(ol, osz): bad.append(p)
        else:
            if l != ol + rep['grow'] or s != osz: bad.append(p)
    if bad: raise SystemExit('⛔ 되읽기 불일치 %s' % bad[:5])
    return True
