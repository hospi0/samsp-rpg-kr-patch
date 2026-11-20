# -*- coding: utf-8 -*-
"""미추출(번역 안 된) 일본어 전수 검사 — 새 디스크(work/build/full 트랙 1)의 «모든 파일»을 BE16 로 훑어
  글자 코드인데 한글 칸(slot.json)이 아니고 원래 글꼴로 가나·한자인 것이 이어진 곳(가나·한자 3자 이상)을 보고.
  python tools/leftover_scan.py → work/review/leftover.tsv"""
import os, sys, re, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmap, extract as X, diskbuild as DB
from iso9660 import Iso

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T1 = os.path.join(ROOT, 'work', 'build', 'full', 'Shinsetsu Samurai Spirits - Bushidou Retsuden (Japan) (Track 1).bin')
JP = re.compile(r'[ぁ-んァ-ヶ一-龥々ー]')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    slot = json.load(open(os.path.join(ROOT, 'work', 'build', 'full', 'slot.json'), encoding='utf8'))
    hang = {cmap.code(v) for v in slot.values()}
    iso = Iso(T1); out = []
    for lba, _, path, l, s, isdir in DB.dir_records(iso):
        if isdir or s == 0 or path.upper().endswith('.XA'): continue
        b = iso.read(l, s); n = len(b) // 2
        v = struct.unpack('>%dH' % n, b[:n * 2])
        i = 0
        while i < n:
            run = []; j = i
            while j < n:
                w = v[j]
                if w >= 0x8080 and w & 0x80 and w not in hang and cmap.idx(w) < 1859:
                    ch = X.T.get(cmap.idx(w), '?'); run.append(ch); j += 1
                elif w >> 8 == 0x05 or w == 0x0200: run.append('·' if w != 0x0200 else '⏎'); j += 1   # 대기·줄바꿈은 이어 봄
                else: break
            txt = ''.join(run).strip('·⏎')
            if sum(1 for c in txt if JP.match(c)) >= 3:
                out.append((path, '%X' % (i * 2), txt[:60]))
            i = max(j, i + 1)
    cnt = collections.Counter(p for p, _, _ in out)
    p = os.path.join(ROOT, 'work', 'review', 'leftover.tsv')
    open(p, 'w', encoding='utf8').write('파일\t오프셋\t글자\n' + ''.join('\t'.join(r) + '\n' for r in out))
    print('후보 %d → %s' % (len(out), p)); [print(' ', k, c) for k, c in cnt.most_common()]


if __name__ == '__main__':
    main()
