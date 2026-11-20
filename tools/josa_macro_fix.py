# -*- coding: utf-8 -*-
"""이름·아이템 코드({0600} 주인공 · {0C00} 아이템) 뒤 «은(는)·을(를)» 같은 두 꼴 조사 없애기 — 하스피 «쉼표»(2026-11-21)
  python tools/josa_macro_fix.py [--write] → work/review/manual.tsv"""
import os, re, sys, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = [(r'\{0600\}은\(는\)⏎', '{0600},⏎'), (r'\{0600\}은\(는\) ?', '{0600}, '),
         (r' ?\{0C00\}을\(를\)⏎손에 넣었다!!', '⏎{0C00} 획득!!'), (r' ?\{0C00\}을\(를\)⏎\{0D00\}개 손에 넣었다!!', '⏎{0C00} {0D00}개 획득!!'),
         (r' ?\{0C00\}을\(를\)⏎포기했다…', '⏎{0C00} 포기…')]   # 아이템 이름 뒤 조사 없는 꼴 · «일행은»은 그대로(받침 고정 낱말)
BY_ID = {
    'D02040': [(r'^\{0600\}은⏎', '{0600},⏎')],
    'D05527': [(r'^\{0600\}의 전 재산을', '{0600}, 전 재산을')],
}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    new = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'samsp_*.tsv'))):
        for l in open(f, encoding='utf8'):
            c = l.rstrip('\n').split('\t')
            if len(c) < 6 or c[0] == 'id': continue
            ko = c[5]
            for p, g in RULES + BY_ID.get(c[0], []): ko = re.sub(p, g, ko)
            if ko != c[5]: new[c[0]] = ko; print(c[0], '|', c[5], '\n   →', ko)
    left = [i for i in BY_ID if i not in new]
    print('바뀔 줄', len(new), '· 안 맞은 BY_ID', left)
    if '--write' in sys.argv:
        p = os.path.join(ROOT, 'work', 'review', 'manual.tsv')
        L = [l for l in open(p, encoding='utf8').read().splitlines() if l.split('\t')[0] not in new]
        open(p, 'w', encoding='utf8').write('\n'.join(L + ['%s\t%s' % kv for kv in new.items()]) + '\n')


if __name__ == '__main__':
    main()
