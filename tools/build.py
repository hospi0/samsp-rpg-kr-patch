# -*- coding: utf-8 -*-
"""전체 빌더 — 번역 TSV(my files/tsv/samsp_*.tsv) → 디스크.

  python tools/build.py --check        검사만(디스크 안 씀)
  python tools/build.py                work/build/full/ 에 트랙 1·2 산출(설치는 따로, 허락 후)

차례
  1) 적재·검사(«쓰는 순간» 강제): 제어 코드 순서 = 원문 · 대사 쪽당 2줄·줄당 16칸 · 고정 칸/실행 파일 예산 ·
     문장부호 뒤 공백 삭제 · 부호 정규화 · 인코딩 누락 = 오류 · 용어 검사(term_check) 보고
  2) 글꼴 칸: 최종 문장이 안 쓰는 한자 칸(224~1691)에 한글·새 부호 배정 → FIX.SDP 조각 2 에 나눔명조 ExtraBold 16px
  3) 대사 블록 다시 쓰기(바뀐 블록만, 포인터 기준·같은 단어열 공유) → 조각 머리표 → SDP 머리표 · F_TEST 0~3 머리 없는 블록 ·
     B_ETC 6·7 적 고정 칸 제자리 · 1ST.BIN 문자열 제자리(예산 안, 남는 칸 0)
  4) diskbuild.rebuild — 커진 파일 뒤 밀기·디렉터리·PVD·섹터·트랙 2
"""
import os, sys, re, json, glob, struct, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import sdp, piece, cmap, kglyph, extract as X, diskbuild, term_check
from iso9660 import Iso

ROOT = X.ROOT
OUT = os.path.join(ROOT, 'work', 'build', 'full')
FONT = '나눔명조ExtraBold'                       # 하스피 2026-11-19 «일단 첫번째»
KEEP_LO, KEEP_HI = 224, 1692                     # 한글로 바꿀 수 있는 칸 범위(한자). 0~223 가나·영숫자·기호, 1692~ 조각·아이콘 보존
LINE, LINES = 16, 2
FONT_SIZE = 13                                     # 2026-11-21: 16 은 높이 17 → 윗줄 잘림. 쓰인 한글 전체 기준 13 = 높이 15·폭 14(원본 한자처럼 0~14행)
PAGE = re.compile(r'\{03[0-9A-F]{2}\}|\{0400\}|\{0F00\}|\{쪽\}')
ADD_PAGE = '{쪽}'                                  # 번역이 넣는 쪽 넘김(2026-11-20 하스피 결정) → {0300} + 그 자리의 화자 코드 반복
SPEAKER = re.compile(r'\{01[0-9A-F]{2}\}')
TOKEN = re.compile(r'\{[0-9A-F]{4}\}')
PUNCT_MAP = {'!': '！', '?': '？', ',': '，', '~': '～', '…': '・・・', '...': '・・・', ':': '：', '+': '＋', '/': '／',
             '(': '（', ')': '）', '[': '［', ']': '］', '-': '－'}
PUNCT_SP = '.,!?~…、。，！？・～：'
LIMIT_TEST = {0: 0x400, 1: 0x400, 2: 0x400}       # F_TEST 0~2 → 0x230C00/0x231000 버퍼(0x400)
BLOCK_MAX = 0x7000


def load_tsv():
    tr = {}; meta = json.load(open(os.path.join(ROOT, 'work', 'extract.json'), encoding='utf8'))
    meta.update(json.load(open(os.path.join(ROOT, 'work', 'extract_place.json'), encoding='utf8')))   # 장소 이름(종류 26, tools/extract_place.py)
    for f in sorted(glob.glob(os.path.join(X.TSV_DIR, 'samsp_*.tsv'))):
        for n, l in enumerate(open(f, encoding='utf8').read().split('\n')[1:], 2):
            p = l.split('\t')
            if len(p) < 6 or not p[5].strip(): continue
            if p[0] not in meta: raise SystemExit('⛔ %s:%d 모르는 id %s' % (os.path.basename(f), n, p[0]))
            tr[p[0]] = (p[5], p[4], os.path.basename(f), n)
    return meta, tr


def normalize(ko):
    ko = ko.replace('...', '…')
    for a, b in PUNCT_MAP.items():
        if a != '...': ko = ko.replace(a, b)
    ko = re.sub('([%s])((?:\\{[0-9A-F]{4}\\})*)[ 　]+' % re.escape(PUNCT_SP + '！？，'), r'\1\2', ko)     # 문장부호 뒤 공백 삭제(전프로젝트 규칙) — 사이에 제어 코드가 끼어도(「,{0510} 다음」)
    return ko


EXE_BASE = 0x06010000
# 실행 파일 문자열 자리 맞바꿈(2026-11-20 하스피 «문자열 옮기기» — 覇王丸 3칸에 하오마루 4글자): 포인터는 표 한 곳(0xB1CC0~)에서만 참조 확인
SWAP_SLOTS = [('E00583', 'E00588')]          # チャムチャム(16 B 자리) ↔ 覇王丸(8 B 자리)
# 건물 출입 확인창 없애기: (1ST.BIN 오프셋, 원래 8 B, 새 8 B) — 6F00 8015/8016(中に入りますか/外に出ますか) + 7300 0000 → A400 0000 + 0600 0000
DOOR_NOPROMPT = [(0xB1220, bytes.fromhex('6f0080157300 0000'.replace(' ', '')), bytes.fromhex('a400000006000000')),   # RAM 0x203FD4 들어가기
                 (0xB1234, bytes.fromhex('6f0080167300 0000'.replace(' ', '')), bytes.fromhex('a400000006000000'))]   # RAM 0x203FE8 나가기


def slot_capacity(m):
    """자리 글자 수(종결 0 제외) = 원문 글자 + 종결 0 을 4바이트 정렬한 크기 안"""
    n = len(m['words']); byt = (2 * (n + 1) + 3) // 4 * 4
    return byt // 2 - 1


def budget_of(i, m, meta):
    for a, b in SWAP_SLOTS:
        if i == a: return slot_capacity(meta[b])
        if i == b: return slot_capacity(meta[a])
    return m.get('budget', len(m['words']))


# 화면별 한 줄 칸 수(스샷 실측 2026-11-21): 대화창·안내창 16, 캐릭터·시나리오·오의 방식 설명창(C_ALL 조각 5, 줄마다 문자열 하나) 12
LINE_BY_LOC = {'C_ALL:5': 12}


def line_limit(m):
    flat = []
    for l in m.get('locs', []): flat += l if isinstance(l, list) else [l]
    ls = [LINE_BY_LOC[l.split('#')[0]] for l in flat if isinstance(l, str) and l.split('#')[0] in LINE_BY_LOC]
    return min(ls) if ls else LINE


def expand_pages(ko):
    """{쪽} → {0300} + 바로 앞까지 마지막 화자 코드(있으면)"""
    if ADD_PAGE not in ko: return ko
    out = ''; last = ''
    for part in re.split(r'(\{[^}]*\})', ko):
        if SPEAKER.fullmatch(part): last = part
        out += ('{0300}' + last) if part == ADD_PAGE else part
    return out


def check_row(i, kind, ko, jp, budget, err, warn, LINE=LINE):
    if TOKEN.findall(ko) != TOKEN.findall(jp):
        err.append((i, '제어 코드 순서가 원문과 다름', jp, ko)); return
    if kind == 'dlg':
        if '{0700}' in jp:                       # 선택지: {0700} 앞 = 대사 창(2줄·16칸), {0700}~첫 {0900} = 질문 한 줄 16칸, 항목 = 원문 항목 최대 폭 이하
            pre_k, post_k = ko.split('{0700}', 1) if '{0700}' in ko else (ko, '')
            pre_j, post_j = jp.split('{0700}', 1)
            check_row(i, kind, pre_k, pre_j, budget, err, warn, LINE)
            parts_k = post_k.split('{0900}'); parts_j = post_j.split('{0900}')
            q = TOKEN.sub('', parts_k[0])
            if '⏎' in q or len(q) > LINE: err.append((i, '선택 질문 줄 %d칸(한 줄 최대 %d): %s' % (len(q.replace('⏎', '')), LINE, q), jp, ko))
            # 항목 = 6칸 이하(오류): 1ST.BIN 0x300E6/0x30174/0x301B6 항목 쓰기 반복이 최대 7번(mov #6,r9) — 7번째 호출이 {0900} 을 읽어야
            # 항목 끝을 넘김. 7칸 이상이면 {0900} 이 남아 다음 항목이 빈 항목으로 끝남(2026-11-21 실기 D05812 «저거는 저거» 사라짐)
            for x in parts_k[1:]:
                n = len(TOKEN.sub('', x).replace('⏎', ''))
                if n > 6: err.append((i, '선택 항목 %d칸(최대 6 — 넘으면 다음 항목이 사라짐): %s' % (n, x), jp, ko))
            return
        if '{0900}' in jp: warn.append((i, '선택지 줄 — 폭 검사 생략', ko)); return
        jpp = [p.split('⏎') for p in PAGE.split(jp)]
        for k, page in enumerate(PAGE.split(ko)):
            lines = page.split('⏎')
            if len(lines) > LINES and not (k < len(jpp) and len(jpp[k]) > LINES):
                err.append((i, '쪽 %d: %d줄(최대 %d)' % (k + 1, len(lines), LINES), jp, ko))
            for ln in lines:
                w = len(TOKEN.sub('', ln))
                if w > LINE:
                    jmax = max(len(TOKEN.sub('', x)) for p in jpp for x in p)
                    (warn if jmax > LINE else err).append((i, '줄 %d칸(최대 %d): %s' % (w, LINE, TOKEN.sub('', ln)), jp, ko))
    else:
        n = len(re.sub(r'\{H\d+\}', '#', TOKEN.sub('', ko)).replace('⏎', ''))     # 조각 칸 {Hn} = 한 글자
        if n > budget: err.append((i, '%d자 > 예산 %d자' % (n, budget), jp, ko))


def main(write):
    meta, tr = load_tsv()
    T = cmap.load()
    err = []; warn = []; final = {}            # id → 표기 문자열(번역 또는 원문)
    for i, m in meta.items():
        jp = X.decode(tuple(int(w, 16) for w in m['words']))
        if i in tr:
            ko = normalize(tr[i][0])
            kind = m['kind']; budget = budget_of(i, m, meta)
            if ADD_PAGE in ko and (kind != 'dlg' or '{0E00}' in jp or '{0700}' in jp or '{0900}' in jp):
                err.append((i, '쪽 넘김 {쪽} 은 일반 대사에만(음성 컷신·선택지·고정 칸 금지)', jp, ko))
            check_row(i, kind, ko, jp, budget, err, warn, line_limit(m))
            final[i] = expand_pages(ko)
        else:
            final[i] = jp
    print('번역 %d / %d 줄' % (len(tr), len(meta)))
    # --- 2) 글꼴 칸 ---
    rev = X.REV
    need = []
    for s in final.values():
        t = re.sub(r'\{[^}]*\}', '', s).replace('⏎', '')
        for m_ in X.MULTI: t = t.replace(m_, '')
        for ch in t:
            if ch == ' ' or ch in rev: continue
            if ch not in need: need.append(ch)
    used = set()
    for s in final.values():
        try: ws = X.encode(s, {c: 0 for c in need})
        except KeyError as e: raise SystemExit('⛔ 인코딩 불가 %r' % e)
        for w in ws:
            if w >= 0x8080 and w & 0x80: used.add(cmap.idx(w))
    # 대사 밖에서 원본 글꼴을 쓰는 소비자가 없음을 가정 — 안 쓰는 한자 칸만
    free = [k for k in range(KEEP_LO, KEEP_HI) if k not in used]
    print('필요한 새 글자 %d (한글 %d · 그 밖 %r) · 빈 한자 칸 %d' % (len(need), sum('가' <= c <= '힣' for c in need),
          ''.join(c for c in need if not '가' <= c <= '힣'), len(free)))
    if len(need) > len(free): raise SystemExit('⛔ 글꼴 칸 부족 %d > %d — 글꼴 늘리기 필요' % (len(need), len(free)))
    slot = dict(zip(need, free))
    for i, s in final.items():
        final[i] = X.encode(s, slot)
    # 보고
    for e in err[:40]: print('  ⛔', e[0], e[1], '|', e[3][:60])
    for w in warn[:10]: print('  ⚠', w[0], w[1])
    print('오류 %d · 경고 %d' % (len(err), len(warn)))
    term_check.check()
    if err:
        open(os.path.join(ROOT, 'work', 'build_errors.tsv'), 'w', encoding='utf8').write(
            'id\t문제\tJP\tKO\n' + ''.join('%s\t%s\t%s\t%s\n' % e for e in err))
        raise SystemExit('⛔ 검사 오류 — work/build_errors.tsv')

    # --- 3) 파일 다시 짜기 ---
    iso = Iso(diskbuild.TR % 1)
    gfx = load_gfx()
    def rd(path):
        for p, l, s in iso.walk():
            if p == path: return apply_gfx(path, iso.read(l, s), gfx)
    by_words = {}                               # (종류, 원문 단어열) → 새 단어열
    for i, m in meta.items():
        jw = tuple(int(w, 16) for w in m['words'])
        if final[i] != jw: by_words[(m['kind'] if m['kind'] in ('N', 'K', 'P') else 'dlg' if m['kind'] == 'dlg' else 'exe', jw, i)] = final[i]
    dlg_map = {k[1]: v for k, v in by_words.items() if k[0] == 'dlg'}
    place_map = {k[1]: v for k, v in by_words.items() if k[0] == 'P'}
    new_files = {}
    nplace = 0
    # 3a) 대사 블록
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'files', 'DATA', '*.SDP'))):
        fn = os.path.basename(f)[:-4]; path = '/DATA/%s.SDP' % fn
        d = rd(path); ents = sdp.entries(d); changed = {}
        for k, o, s in ents:
            if (fn, k) in X.SKIP: continue
            p = d[o:o + s]
            if (fn, k) in X.RAW_BLOCKS:
                nb = rebuild_block(p, dlg_map)
                if nb is not None:
                    lim = LIMIT_TEST.get(k, BLOCK_MAX)
                    if len(nb) > lim: raise SystemExit('⛔ %s#%d 블록 0x%X > 0x%X' % (fn, k, len(nb), lim))
                    changed[k] = nb
                continue
            h = piece.header(p)
            if not h: continue
            np_ = bytearray(p); nh = list(h); dirty = False
            for j, (t, sub, bo, bs) in enumerate(h):
                if t == 26:                      # 장소 이름 36 B 제자리(세이브 화면)
                    ws = struct.unpack('>18H', p[bo:bo + 36]); n = ws.index(0) if 0 in ws else 18
                    nw = place_map.get(ws[:n])
                    if nw is None: continue
                    assert bs == 36 and len(nw) <= 17, (fn, k, '장소 이름 넘침')
                    nbo = nh[j][2]; assert bytes(np_[nbo:nbo + 36]) == p[bo:bo + 36]    # 앞 대사 블록이 커지면 밀린 자리
                    np_ = bytearray(np_); np_[nbo:nbo + 36] = struct.pack('>%dH' % len(nw), *nw) + bytes(36 - 2 * len(nw)); dirty = True; nplace += 1
                    continue
                if t != 0x0A: continue
                nb = rebuild_block(p[bo:bo + bs], dlg_map)
                if nb is None: continue
                if len(nb) > BLOCK_MAX: raise SystemExit('⛔ %s#%d 블록 0x%X > 0x%X' % (fn, k, len(nb), BLOCK_MAX))
                np_, nh = replace_sub(bytes(np_), nh, j, nb); dirty = True
            if dirty: changed[k] = bytes(np_)
        if fn == 'B_ETC':
            for k, o, s in ents:
                if ('B_ETC', k) not in X.BTL: continue
                p = bytearray(changed.get(k, d[o:o + s]))
                for (kind, jw, i), nw in by_words.items():
                    if kind not in ('N', 'K'): continue
                    for (_, kk, off) in meta[i]['locs']:
                        if kk != k: continue
                        bw = meta[i]['budget']
                        assert tuple(struct.unpack_from('>%dH' % len(jw), p, off)) == jw, (i, '원문 불일치')
                        assert len(nw) <= bw
                        old_end = off + 2 * (bw + 1)
                        assert all(x == 0 for x in p[off + 2 * len(jw):old_end]), (i, '칸 뒤가 0 아님')
                        p[off:old_end] = struct.pack('>%dH' % len(nw), *nw) + bytes(old_end - off - 2 * len(nw))
                if bytes(p) != d[o:o + s]: changed[k] = bytes(p)
        if changed: new_files[path] = repack_sdp(d, changed)
        elif path in gfx: new_files[path] = d                 # 그림 패치만 있는 파일
    print('장소 이름 %d곳 (번역 %d종)' % (nplace, len(place_map)))
    # 3b) 글꼴
    fix = bytearray(new_files.get('/DATA/FIX.SDP', rd('/DATA/FIX.SDP')))
    fo, fs = {k: (o, s) for k, o, s in sdp.entries(fix)}[2]
    kglyph.set_box(FONT, FONT_SIZE, [c for c in slot if '가' <= c <= '힣'])
    for ch, i in slot.items():
        g = kglyph.ttf_glyph(ch, FONT, FONT_SIZE)
        tiles = [g[0:8, 0:8], g[0:8, 8:16], g[8:16, 0:8], g[8:16, 8:16]]
        fix[fo + i * 32: fo + i * 32 + 32] = b''.join(bytes(np.packbits(t, axis=1).ravel()) for t in tiles)
    new_files['/DATA/FIX.SDP'] = bytes(fix)
    # 3c) 실행 파일 제자리
    exe = bytearray(rd('/1ST.BIN')); nexe = 0
    for a, b in SWAP_SLOTS:                     # 두 문자열 자리 맞바꿈: a 글을 b 자리에, b 글을 a 자리에, 포인터도 맞바꿈
        ma, mb = meta[a], meta[b]
        for x, mx in ((a, ma), (b, mb)):
            jw = tuple(int(w, 16) for w in mx['words'])
            assert tuple(struct.unpack_from('>%dH' % len(jw), exe, mx['off'])) == jw, (x, '원문 불일치')
            for p in mx['ptrs']: assert struct.unpack_from('>I', exe, p)[0] == EXE_BASE + mx['off'], (x, '포인터 불일치', hex(p))
        for src, dst in ((a, mb), (b, ma)):
            nw = final[src]; cap = slot_capacity(dst)
            assert len(nw) <= cap, (src, '맞바꾼 자리 넘침', len(nw), cap)
            o = dst['off']; end = o + 2 * (cap + 1)
            exe[o:end] = struct.pack('>%dH' % len(nw), *nw) + bytes(end - o - 2 * len(nw))
        for p in ma['ptrs']: struct.pack_into('>I', exe, p, EXE_BASE + mb['off'])
        for p in mb['ptrs']: struct.pack_into('>I', exe, p, EXE_BASE + ma['off'])
        nexe += 2
    swapped = {x for pr in SWAP_SLOTS for x in pr}
    for i, m in meta.items():
        if i in swapped: continue
        if m['kind'] not in ('E', 'X') or final[i] == tuple(int(w, 16) for w in m['words']): continue
        o = m['off']; jw = tuple(int(w, 16) for w in m['words']); nw = final[i]
        assert tuple(struct.unpack_from('>%dH' % len(jw), exe, o)) == jw, (i, '원문 불일치')
        bw = m.get('budget', len(jw)); assert len(nw) <= bw
        end = o + 2 * (max(bw, len(jw)) + 1)
        assert all(x == 0 for x in exe[o + 2 * len(jw):end]), (i, '칸 뒤가 0 아님')
        exe[o:end] = struct.pack('>%dH' % len(nw), *nw) + bytes(end - o - 2 * len(nw)); nexe += 1
    # 3d) 건물 출입 예/아니오 창 없애기(하스피 2026-11-21) — 출입 스크립트(Low RAM 0x203FD0 들어가기·0x203FE4 나가기,
    #     호출 0x06031100) 의 «질문 6F + 예면 분기 73» 을 «이동 확정 A4 + 끝 06» 으로. 이동은 0x06031084 가 미리 걸어 둠.
    #     파일 오프셋 = RAM − 0x200000 + 0xAD24C. docs/00_초기조사.md «출입 창 없애기»
    for fo, old, new in DOOR_NOPROMPT:
        assert bytes(exe[fo:fo + len(old)]) == old, ('출입 스크립트 원문 불일치', hex(fo))
        exe[fo:fo + len(new)] = new; nexe += 1
    if nexe: new_files['/1ST.BIN'] = bytes(exe)
    print('바뀐 파일 %d: %s' % (len(new_files), ', '.join(sorted(p.split('/')[-1] for p in new_files))))
    out1, out2, rep = diskbuild.rebuild(new_files)
    print('트랙 1 %d → %d 섹터(+%d), 새로 만든 섹터 %d, 디렉터리 섹터 %d' % (rep['n1'], rep['new_n1'], rep['grow'], rep['resect'], rep['dirsec']))
    if not write: print('검사만(--check) — 디스크 안 씀'); return
    os.makedirs(OUT, exist_ok=True)
    p1 = os.path.join(OUT, os.path.basename(diskbuild.TR % 1)); p2 = os.path.join(OUT, os.path.basename(diskbuild.TR % 2))
    diskbuild.verify(out1, new_files, rep, p1)
    open(p2, 'wb').write(out2)
    json.dump({c: i for c, i in slot.items()}, open(os.path.join(OUT, 'slot.json'), 'w', encoding='utf8'), ensure_ascii=False)
    for p in (p1, p2): print('산출', p, hashlib.md5(open(p, 'rb').read()).hexdigest())


def load_gfx():
    """work/gfx/*.json 그림 패치(조각·머리표 순번·하위 블록 안 오프셋, 원래 바이트 확인)"""
    out = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'gfx', '*.json'))):
        J = json.load(open(f, encoding='utf8'))
        for p in J['patches']: out['/DATA/%s.SDP' % p['file']].append((os.path.basename(f), p))
    return out


def apply_gfx(path, d, gfx):
    if path not in gfx: return d
    d = bytearray(d); e = {k: (o, s) for k, o, s in sdp.entries(d)}; n = 0
    for src, p in gfx[path]:
        o, s = e[p['piece']]
        if p['hidx'] < 0: t, sub, bo, bs = -1, -1, 0, s                    # 머리표 없는 조각 통째
        else: t, sub, bo, bs = piece.header(bytes(d[o:o + s]))[p['hidx']]
        assert (t, sub) == (p['type'], p['sub']), (src, '하위 블록 종류 불일치')
        a = o + bo + p['off']; new = bytes.fromhex(p['new']); old = bytes.fromhex(p['old'])
        if bytes(d[a:a + len(new)]) == new: continue                     # 같은 패치가 다른 작업에도 있음(같은 셀)
        assert p['off'] + len(new) <= bs and bytes(d[a:a + len(old)]) == old, (src, '그림 원래 바이트 불일치', p['off'])
        d[a:a + len(new)] = new; n += 1
    print('그림 패치 %s: %d곳' % (path.split('/')[-1], n))
    return bytes(d)


def rebuild_block(b, dlg_map):
    """대사 블록 → 바뀐 문자열이 있으면 새 블록, 없으면 None. 포인터 기준·같은 단어열 공유·미참조 바이트 버림."""
    cnt, offs = piece.text_block(b)
    st = {ix: v for ix, x, v in piece.strings(b)}
    if not any(v in dlg_map for v in st.values()): return None
    body = bytearray(); at = {}; newoffs = []; base = 2 + 2 * cnt
    for ix in range(cnt):
        if offs[ix] == 0: newoffs.append(0); continue
        v = dlg_map.get(st[ix], st[ix])
        if v not in at: at[v] = base + len(body); body += struct.pack('>%dH' % len(v), *v) + b'\0\0'
        newoffs.append(at[v])
    if max(newoffs) > 0xFFFF: raise SystemExit('⛔ 블록 오프셋 16비트 초과')
    nb = struct.pack('>H%dH' % cnt, cnt, *newoffs) + bytes(body)
    chk = {ix: v for ix, x, v in piece.strings(nb)}
    assert all(chk[ix] == dlg_map.get(st[ix], st[ix]) for ix in st)
    return nb


def replace_sub(p, h, j, nb):
    """조각 p 의 하위 블록 j 를 nb 로 — 뒤 하위 블록을 4정렬로 밀고 머리표 갱신"""
    t, sub, bo, bs = h[j]; delta = len(nb) - bs; shift = (delta + 3) & ~3 if delta > 0 else -((-delta) & ~3)
    np_ = bytearray(p[:bo]) + nb + bytes(bs + shift - len(nb)) + bytearray(p[bo + bs:])
    nh = []
    for (tt, su, a, b) in h:
        if (tt, su, a) == (t, sub, bo): nh.append((tt, su, a, len(nb)))
        elif a > bo: nh.append((tt, su, a + shift, b))
        else: nh.append((tt, su, a, b))
    hdr_n = p[0]; idx = 0
    for q in range(hdr_n):                       # 빈 항목(전부 0)은 그대로
        if struct.unpack_from('>HHII', p, 4 + q * 12) == (0, 0, 0, 0): continue
        struct.pack_into('>HHII', np_, 4 + q * 12, *nh[idx]); idx += 1
    for (tt, su, a, b), (_, _, a2, _) in zip(h, nh):
        if (tt, su, a) != (t, sub, bo): assert p[a:a + b] == bytes(np_[a2:a2 + b])
    return bytes(np_), nh


def repack_sdp(d, changed):
    ents = sdp.entries(d); hdr = bytearray(d[:0x800]); body = bytearray(); cur = 0x800
    for k, o, s in ents:
        p = changed.get(k, d[o:o + s])
        body += bytes(cur - 0x800 - len(body)) + p
        struct.pack_into('>II', hdr, k * 8, cur, len(p))
        cur = (cur + len(p) + 0x7FF) & ~0x7FF
    out = bytes(hdr) + bytes(body); out += bytes((-len(out)) % 0x800)
    for k, o, s in sdp.entries(out):
        orig = [e for e in ents if e[0] == k][0]
        assert out[o:o + s] == changed.get(k, d[orig[1]:orig[1] + orig[2]])
    return out


if __name__ == '__main__':
    main('--check' not in sys.argv)
