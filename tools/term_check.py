# -*- coding: utf-8 -*-
"""용어 최종 검사(하스피 지시 2026-11-19: 번역은 자유롭게, 용어표 통일은 Claude 가 적재 때 바로잡음).

  python tools/term_check.py            → work/term_report.tsv (위반 줄, 쓰인 변형 후보)
  python tools/term_check.py --fix FILE → FILE(용어별 «잘못된 표기 → 바른 표기» 표, 하스피 확인 후) 을 TSV 에 적용, 뒤 조사 받침 교정

규칙
  - 원문(JP) 매칭은 제어 코드·⏎·공백을 걷어낸 사본으로(개행·띄어쓰기로 쪼개진 용어도 잡음). 긴 용어부터, 잡힌 자리는 소비.
  - 한국어(KO)에 용어표 표기(공백 무시)가 없으면 위반.
  - 교정은 치환 표로만(자동 추측 치환 안 함), 치환 바로 뒤 조사를 새 낱말 받침에 맞춰 다시 고름.
"""
import os, re, sys, glob, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, 'my files', 'tsv')
TOK = re.compile(r'\{[^}]*\}|⏎')


def glossary():
    g = []
    for l in open(os.path.join(ROOT, 'work', 'glossary.tsv'), encoding='utf8').read().splitlines()[1:]:
        p = l.split('\t')
        if len(p) >= 2 and p[0] and p[1]: g.append((p[0], p[1]))
    g.sort(key=lambda x: -len(x[0].replace('　', '')))
    return g


def norm_jp(s): return re.sub(r'[\s　]', '', TOK.sub('', s))
def norm_ko(s): return re.sub(r'\s', '', TOK.sub('', s))


def rows():
    for f in sorted(glob.glob(os.path.join(TSV, 'samsp_*.tsv'))):
        for n, l in enumerate(open(f, encoding='utf8').read().split('\n')[1:], 2):
            p = l.split('\t')
            if len(p) >= 6: yield os.path.basename(f), n, p


def check():
    G = glossary(); bad = []; stat = collections.Counter()
    for fn, n, p in rows():
        i, jp, ko = p[0], p[4], p[5]
        if not ko.strip(): continue
        j = norm_jp(jp); k = norm_ko(ko)
        for tj, tk in G:
            key = tj.replace('　', '')
            if key in j:
                j = j.replace(key, '\0')                 # 소비(짧은 용어가 긴 용어 안에서 또 잡히지 않게)
                stat[tj] += 1
                if tk.replace(' ', '') not in k: bad.append((fn, n, i, tj, tk, jp, ko))
    out = os.path.join(ROOT, 'work', 'term_report.tsv')
    with open(out, 'w', encoding='utf8') as f:
        f.write('파일\t줄\tid\t원문 용어\t용어표 표기\tJP\tKO\n')
        for r in bad: f.write('\t'.join(map(str, r)) + '\n')
    print('용어 출현 줄 %d · 위반 %d → %s' % (sum(stat.values()), len(bad), out))
    by = collections.Counter(r[3] for r in bad)
    for t, c in by.most_common(20): print('  %s → %s : %d' % (t, dict(G)[t], c))


JOSA = ['으로', '이라', '이란', '이나', '이랑', '이여', '은', '는', '을', '를', '이', '가', '과', '와', '로', '라', '란', '나', '랑', '여']
PAIR = {'은': ('은', '는'), '는': ('은', '는'), '을': ('을', '를'), '를': ('을', '를'), '이': ('이', '가'), '가': ('이', '가'),
        '과': ('과', '와'), '와': ('과', '와'), '으로': ('으로', '로'), '로': ('으로', '로'), '이라': ('이라', '라'), '라': ('이라', '라'),
        '이란': ('이란', '란'), '란': ('이란', '란'), '이나': ('이나', '나'), '나': ('이나', '나'), '이랑': ('이랑', '랑'), '랑': ('이랑', '랑'),
        '이여': ('이여', '여'), '여': ('이여', '여')}


def josa_for(word, j):
    ch = word[-1]
    if not ('가' <= ch <= '힣'): return j
    b = (ord(ch) - 0xAC00) % 28
    yes, no = PAIR[j]
    if yes == '으로' and b == 8: return '로'          # ㄹ 받침 + 로
    return yes if b else no


def fix_text(ko, pairs):
    """pairs = [(정규식 문자열, 바른 표기)] — 바로 뒤(띄어쓰기 없음) 조사를 받침에 맞춤"""
    for pat, good in pairs:
        rx = re.compile('(?:%s)(%s)?' % (pat, '|'.join(JOSA)))
        ko = rx.sub(lambda m: good + (josa_for(good, m.group(1)) if m.group(1) else ''), ko)
    return ko


def apply(fixfile):
    pairs = [tuple(l.split('\t')[:2]) for l in open(fixfile, encoding='utf8').read().splitlines() if l and not l.startswith('#')]
    nfix = 0
    for f in sorted(glob.glob(os.path.join(TSV, 'samsp_*.tsv'))):
        L = open(f, encoding='utf8').read().split('\n'); ch = False
        for n in range(1, len(L)):
            p = L[n].split('\t')
            if len(p) < 6 or not p[5]: continue
            ko = fix_text(p[5], pairs)
            if ko != p[5]: p[5] = ko; L[n] = '\t'.join(p); ch = True; nfix += 1
        if ch: open(f, 'w', encoding='utf8', newline='\n').write('\n'.join(L))
    print('고친 줄', nfix)


if __name__ == '__main__':
    if '--fix' in sys.argv: apply(sys.argv[sys.argv.index('--fix') + 1])
    else: check()
