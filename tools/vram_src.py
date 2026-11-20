# -*- coding: utf-8 -*-
"""스테이트 VRAM(VDP1·VDP2) → 디스크 파일 출처 찾기(무압축 일치).

  python tools/vram_src.py <스테이트 이름…>
  VRAM 을 64 B 덩어리(서로 다른 바이트 8종 이상)로 잘라 사전 → 파일(SDP·1ST.BIN)을 4 B 간격으로 훑어 맞는 곳 →
  (VRAM, 파일 위치 차이) 로 묶어 연속 구간 출력. 결과 work/vram_src_<스테이트>.txt
"""
import os, sys, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rzip, mdfnstate as M, sdp, piece

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = 64


def where(fn, d, off):
    if fn == '1ST.BIN': return '1ST.BIN'
    for k, o, s in sdp.entries(d):
        if o <= off < o + s:
            h = piece.header(d[o:o + s])
            for t, sub, bo, bs in (h or []):
                if bo <= off - o < bo + bs: return '%s#%d/%X.%d+%X' % (fn, k, t, sub, off - o - bo)
            return '%s#%d+%X' % (fn, k, off - o)
    return fn


def main(states):
    keys = {}
    vr = {}
    for st in states:
        d = rzip.unpack(os.path.join(ROOT, 'work', 'states_user', st + '.state'))[0]; S = M.sections(d)
        for nm in ('VDP1', 'VDP2'):
            V = M.swap16(S[nm]['VRAM']); vr[(st, nm)] = V
            for a in range(0, len(V) - CH, CH):
                blk = V[a:a + CH]
                if len(set(blk)) >= 8: keys.setdefault(blk, []).append((st, nm, a))
    print('VRAM 덩어리 %d' % len(keys))
    hits = collections.defaultdict(list)
    files = [('1ST.BIN', os.path.join(ROOT, 'work', 'files', '1ST.BIN'))] + [(os.path.basename(f)[:-4], f) for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'files', 'DATA', '*.SDP')))]
    for fn, f in files:
        d = open(f, 'rb').read(); n = 0
        for q in range(0, len(d) - CH, 4):
            v = keys.get(d[q:q + CH])
            if v:
                for st, nm, a in v: hits[(st, nm, fn, q - a)].append(a); n += 1
        sys.stdout.write('%s %d\n' % (fn, n)); sys.stdout.flush()
    for st in states:
        lines = []
        for (s, nm, fn, delta), addrs in hits.items():
            if s != st or len(addrs) < 4: continue
            d = open(dict(files)[fn], 'rb').read()
            lines.append('%s 0x%05X~0x%05X ← %s (덩어리 %d)' % (nm, min(addrs), max(addrs) + CH, where(fn, d, min(addrs) + delta), len(addrs)))
        lines.sort()
        open(os.path.join(ROOT, 'work', 'vram_src_%s.txt' % st), 'w', encoding='utf8').write('\n'.join(lines) + '\n')
        print('==', st, len(lines))


if __name__ == '__main__':
    main(sys.argv[1:])
