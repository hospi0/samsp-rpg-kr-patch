# -*- coding: utf-8 -*-
"""번역 모집단 추출 → my files/tsv/*.tsv (18KB 단위) + work/extract.json

  python tools/extract.py [--write]      (없으면 왕복 검산·집계만)

모집단
  D  대사 블록(조각 머리표 종류 0x000A) + F_TEST.SDP 조각 0~3(머리표 없는 블록) — 포인터 기준 문자열, 같은 단어열은 하나로
     ⛔제외: F_ISS1 조각 35·36(다른 글자 순서로 깨진 옛 데이터), 포인터가 안 닿는 바이트
  E  1ST.BIN 포인터 문자열(BE32 절대 주소) — 예산 = 원문 바이트(제자리, 옮기기는 빌더에서 결정)
  X  1ST.BIN 포인터 없는 고정 표 후보 — 예산 = 원문 바이트(제자리), 거짓 양성은 번역 때 «원문 유지»
표기: 글자 = charmap, 163번 칸 = « »(반각 공백), 0200 = ⏎, 그 밖 단어 = {XXXX}(0Axx 뒤 인수 포함), 조각 칸 = {Hn}
"""
import os, sys, struct, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdp, piece, cmap, exe_strings as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV_DIR = os.path.join(ROOT, 'my files', 'tsv')
SP = 163
SKIP = {('F_ISS1', 35), ('F_ISS1', 36)}
RAW_BLOCKS = {('F_TEST', 0), ('F_TEST', 1), ('F_TEST', 2), ('F_TEST', 3)}

T = cmap.load()
REV = {}
for i, c in T.items():
    if i == SP: continue
    if c not in REV: REV[c] = i
MULTI = sorted((c for c in REV if len(c) > 1 and not c.startswith('{')), key=len, reverse=True)   # 예: ㇷ゚(2 코드포인트)


def decode(ws):
    out = []
    for w in ws:
        if w >= 0x8080 and w & 0x80:
            i = cmap.idx(w); out.append(' ' if i == SP else T[i])
        elif w == 0x0200: out.append('⏎')
        else: out.append('{%04X}' % w)
    return ''.join(out)


def encode(s, extra=None):
    """표기 → 단어열. extra = {글자: 칸}(한글 배정). 없는 글자는 KeyError(인코딩 누락 = 빌드 에러)."""
    out = []; i = 0
    while i < len(s):
        ch = s[i]
        if ch == '{':
            j = s.index('}', i); tok = s[i + 1:j]
            if len(tok) == 4 and all(c in '0123456789ABCDEF' for c in tok): out.append(int(tok, 16))
            else: out.append(cmap.code(REV['{' + tok + '}']))
            i = j + 1; continue
        m = next((c for c in MULTI if s.startswith(c, i)), None)
        if m: out.append(cmap.code(REV[m])); i += len(m); continue
        if ch == '⏎': out.append(0x0200)
        elif ch == ' ': out.append(cmap.code(SP))
        elif extra and ch in extra: out.append(cmap.code(extra[ch]))
        else: out.append(cmap.code(REV[ch]))
        i += 1
    return tuple(out)


def blocks():
    """[(파일, 조각, 블록 바이트)]"""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'files', 'DATA', '*.SDP'))):
        fn = os.path.basename(f)[:-4]; d = open(f, 'rb').read()
        for k, o, s in sdp.entries(d):
            if (fn, k) in SKIP: continue
            p = d[o:o + s]
            if (fn, k) in RAW_BLOCKS: out.append((fn, k, p)); continue
            for t, sub, bo, bs in (piece.header(p) or []):
                if t == 0x0A: out.append((fn, k, p[bo:bo + bs]))
    return out


def collect():
    recs = collections.OrderedDict()      # 단어열 → {'loc': [...]}
    for fn, k, b in blocks():
        for ix, x, v in piece.strings(b):
            if not any(w >= 0x8080 and w & 0x80 for w in v): continue   # 글자 없는 문자열(제어만)은 번역 대상 아님
            recs.setdefault(v, []).append('%s:%d#%d' % (fn, k, ix))
    b = open(os.path.join(ROOT, 'work', 'files', '1ST.BIN'), 'rb').read()
    ptr = E.scan(b); exe = []
    cov = bytearray(len(b))
    for o in sorted(ptr):
        v, e = E.parse(b, o)
        for q in range(o, e + 2): cov[q] = 1
        exe.append(('E', o, tuple(v), ptr[o]))
    n = len(b) // 2; i = 0
    xs = []
    while i < n:
        o = i * 2; w = struct.unpack_from('>H', b, o)[0]
        if E.is_ch(w) and not cov[o]:
            v, e = E.parse(b, o)
            if v and sum(1 for x in v if E.is_ch(x)) >= 2 and not any(cov[o:e]):
                xs.append((o, tuple(v), slot_words(b, o, len(v)))); i = e // 2 + 1; continue
        i += 1
    # 고정 칸 예산: 칸(글자+뒤 0) 을 같은 4KB 구역의 최빈 칸 길이로 자르고 끝 표시 1단어 뺌
    mode = {}
    for o, v, sl in xs: mode.setdefault(o >> 12, collections.Counter())[sl] += 1
    for o, v, sl in xs:
        cap = mode[o >> 12].most_common(1)[0][0]
        exe.append(('X', o, v, [], max(len(v), min(sl, cap) - 1)))
    return recs, exe


def slot_words(b, o, nv):
    """글자 nv 단어 뒤로 이어지는 0 단어까지 합한 칸 길이(단어)"""
    z = o + 2 * nv
    while z + 1 < len(b) and b[z:z + 2] == b'\0\0': z += 2
    return (z - o) // 2


BTL = {('B_ETC', 6): ('N', 9), ('B_ETC', 7): ('K', 16)}      # 적 이름(50 B 레코드, 칸 9단어) · 적 기술·외침(56 B 레코드, 칸 16단어)
def collect_btl():
    """B_ETC 조각 6·7 종류 0x10 블록의 고정 칸 문자열 → {(종류, 단어열): [(파일, 조각, 조각 안 오프셋, 예산 단어)]}"""
    out = collections.OrderedDict()
    d = open(os.path.join(ROOT, 'work', 'files', 'DATA', 'B_ETC.SDP'), 'rb').read()
    for k, o, s in sdp.entries(d):
        if ('B_ETC', k) not in BTL: continue
        kind, cap = BTL[('B_ETC', k)]
        p = d[o:o + s]; h = piece.header(p)
        t, sub, bo, bs = [x for x in h if x[0] == 0x10][0]
        b = p[bo:bo + bs]; n = len(b) // 2; v = struct.unpack('>%dH' % n, b[:n * 2]); i = 0
        while i < n:
            if E.is_ch(v[i]) and (i == 0 or (not E.is_ch(v[i - 1]) and v[i - 1] >> 8 != 0x80)):
                j = i
                while j < n and E.is_ch(v[j]): j += 1
                if j < n and v[j] == 0:
                    sl = slot_words(b, i * 2, j - i)
                    out.setdefault((kind, tuple(v[i:j])), []).append(('B_ETC', k, bo + i * 2, max(j - i, min(sl, cap) - 1)))
                    i = j; continue
            i += 1
    return out


def main(write):
    recs, exe = collect()
    btl = collect_btl()
    bad = [v for v in recs if encode(decode(v)) != v] + [e[2] for e in exe if encode(decode(e[2])) != e[2]] + [v for (_, v) in btl if encode(decode(v)) != v]
    print('대사 고유 %d (출현 %d) · 실행 파일 포인터 %d · 고정 후보 %d · 적 이름 %d · 적 기술/외침 %d · 왕복 불일치 %d'
          % (len(recs), sum(len(x) for x in recs.values()), sum(1 for e in exe if e[0] == 'E'), sum(1 for e in exe if e[0] == 'X'),
             sum(1 for k in btl if k[0] == 'N'), sum(1 for k in btl if k[0] == 'K'), len(bad)))
    if bad:
        for v in bad[:5]: print('  ', decode(v))
        raise SystemExit('⛔ 왕복 불일치')
    if not write: return
    rows = []; meta = {}
    for n, (v, locs) in enumerate(recs.items(), 1):
        i = 'D%05d' % n
        rows.append(('dlg', [i, 'dlg', locs[0] + (' 외%d' % (len(locs) - 1) if len(locs) > 1 else ''), '2줄·16칸', decode(v), '']))
        meta[i] = {'kind': 'dlg', 'words': ['%04x' % w for w in v], 'locs': locs}
    ne = nx = 0
    for e in exe:
        kind, o, v, ps = e[:4]
        if kind == 'E': ne += 1; i = 'E%05d' % ne; bw = len(v)
        else: nx += 1; i = 'X%05d' % nx; bw = e[4]
        rows.append(('exe', [i, 'exe' if kind == 'E' else 'exe고정', '1ST:%X' % o, '%d자' % bw, decode(v), '']))
        meta[i] = {'kind': kind, 'off': o, 'ptrs': ps, 'words': ['%04x' % w for w in v], 'budget': bw}
    cnt = collections.Counter()
    for (kind, v), locs in btl.items():
        cnt[kind] += 1; i = '%s%05d' % (kind, cnt[kind]); bw = min(x[3] for x in locs)
        rows.append(('btl', [i, '적이름' if kind == 'N' else '적기술', '%s:%d@%X' % locs[0][:3] + (' 외%d' % (len(locs) - 1) if len(locs) > 1 else ''), '%d자' % bw, decode(v), '']))
        meta[i] = {'kind': kind, 'words': ['%04x' % w for w in v], 'locs': [list(x[:3]) for x in locs], 'budget': bw}
    json.dump(meta, open(os.path.join(ROOT, 'work', 'extract.json'), 'w', encoding='utf8'), ensure_ascii=False)
    os.makedirs(TSV_DIR, exist_ok=True)
    head = 'id\t종류\t위치\t예산\tJP\tKO\n'
    for group in ('dlg', 'exe', 'btl'):
        part = []; size = 0; k = 0
        def flush():
            nonlocal part, size, k
            if not part: return
            k += 1; p = os.path.join(TSV_DIR, 'samsp_%s_%03d.tsv' % (group, k))
            open(p, 'w', encoding='utf8', newline='\n').write(head + ''.join(part)); part = []; size = 0
        for g, r in rows:
            if g != group: continue
            line = '\t'.join(r) + '\n'; lb = len(line.encode('utf8'))
            if size + lb + len(head.encode('utf8')) > 18 * 1024: flush()
            part.append(line); size += lb
        flush()
        print(group, 'TSV %d개' % k)


if __name__ == '__main__':
    main('--write' in sys.argv)
