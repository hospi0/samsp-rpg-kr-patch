# -*- coding: utf-8 -*-
r"""맵 장소 이름(조각 하위 블록 종류 26, 36 B = BE16 코드 18칸, 0 채움) 추출 — 세이브 화면 «장소 [ ]» 에 찍힘(2026-11-21 하스피 «저장장소명 미추출»)
  흐름: 맵 들어갈 때 종류 26 → 세이브 데이터 +0xB 에 strcpy(0x06095C5E) → 세이브 화면 0x060E7CF8 버퍼 → (0x0A,9) 에 찍기(0x060980A0)
  python tools/extract_place.py [--write]
    → work/extract_place.json (id → kind P, words, budget, locs)
    → --write 면 my files/tsv/samsp_place_001.tsv (KO 는 F_TEST#3 지명표 번역과 «원문이 똑같은» 것만 미리 채움)
  예산 = 12칸(세이브 화면 [ ] 안 폭, 원문 최대 8) · 레코드 36 B 안(17칸)."""
import os, sys, struct, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdp, piece, extract as X

ROOT = X.ROOT
BUDGET = 12


def scan():
    names = collections.OrderedDict()
    for fn in sorted(glob.glob(os.path.join(ROOT, 'work', 'files', 'DATA', '*.SDP'))):
        b = open(fn, 'rb').read(); f = os.path.basename(fn)[:-4]
        for k, o, sz in sdp.entries(b):
            h = piece.header(b[o:o + sz])
            if not h: continue
            for t, sub, po, ps in h:
                if t != 26: continue
                assert ps == 36, (f, k, ps)
                ws = struct.unpack('>18H', b[o + po:o + po + ps])
                n = ws.index(0) if 0 in ws else 18
                assert all(w == 0 for w in ws[n:]), (f, k)
                names.setdefault(ws[:n], []).append('%s:%d' % (f, k))
    return names


def main(write):
    names = scan()
    meta = {}
    for n, (ws, locs) in enumerate(names.items(), 1):
        meta['P%04d' % n] = {'kind': 'P', 'words': ['%04X' % w for w in ws], 'budget': BUDGET, 'locs': locs}
    json.dump(meta, open(os.path.join(ROOT, 'work', 'extract_place.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    tr = {}
    for f in glob.glob(os.path.join(X.TSV_DIR, 'samsp_dlg_*.tsv')):
        for l in open(f, encoding='utf8'):
            c = l.rstrip('\n').split('\t')
            if len(c) > 5 and 'F_TEST:3#' in c[2] and c[5]: tr.setdefault(c[4], c[5])
    rows = []; pre = 0
    for i, m in meta.items():
        jp = X.decode(tuple(int(w, 16) for w in m['words']))
        ko = tr.get(jp, ''); pre += bool(ko)
        loc = m['locs'][0] + (' 외%d' % (len(m['locs']) - 1) if len(m['locs']) > 1 else '')
        rows.append('%s\t장소\t%s\t%d칸\t%s\t%s' % (i, loc, BUDGET, jp, ko))
    print('장소 이름 레코드 %d · 고유 %d · 지명표에서 미리 채움 %d' % (sum(len(v) for v in names.values()), len(meta), pre))
    if write:
        out = os.path.join(X.TSV_DIR, 'samsp_place_001.tsv')
        if os.path.exists(out): raise SystemExit('⛔ 이미 있음(번역이 덮임): ' + out)
        open(out, 'w', encoding='utf8').write('id\t종류\t위치\t예산\tJP\tKO\n' + '\n'.join(rows) + '\n')
        print('→', out)


if __name__ == '__main__':
    main('--write' in sys.argv)
