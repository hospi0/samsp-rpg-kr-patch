# -*- coding: utf-8 -*-
r"""review_fix.py 산출(work/review/fixed.json) → my files/tsv/samsp_*.tsv 의 KO 칸에 병합(바뀐 줄만, 줄바꿈 그대로)
  순서: work/review/manual.tsv(id\t새 KO) 추가 → python tools/review_fix.py → python tools/merge_fixed.py → python tools/build.py --check
  ⚠ 병합 전에 TSV 백업(work/backup/…) 권장. 출력 = 바뀐 id 목록(의도한 줄만인지 확인)"""
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    F = json.load(open(os.path.join(ROOT, 'work', 'review', 'fixed.json'), encoding='utf8'))
    ids = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'samsp_*.tsv'))):
        L = open(f, encoding='utf-8', newline='').read().split('\n'); ch = False
        for k, l in enumerate(L):
            c = l.split('\t')
            if len(c) > 5 and c[0] in F and F[c[0]] != c[5]:
                c[5] = F[c[0]]; L[k] = '\t'.join(c); ch = True; ids.append(c[0])
        if ch: open(f, 'w', encoding='utf-8', newline='').write('\n'.join(L))
    print('병합 %d줄' % len(ids), ids)


if __name__ == '__main__':
    main()
