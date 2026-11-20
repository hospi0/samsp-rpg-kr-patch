# -*- coding: utf-8 -*-
"""선택 항목 6칸 제한 고침(2026-11-21 실기 D05812 — build.py check_row 주석 참고)
  현재 TSV KO 에서 «{0900}옛 항목» → «{0900}새 항목» 바꿔 work/review/manual.tsv 에 덮어 넣음.  python tools/choice_fix.py [--write]"""
import os, re, sys, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = {   # 하스피 지정(2026-11-21): 뒷거래통행증·밀항 안한다·아가씨 선택·설득한다 | 옛 항목 → 새 항목(6칸 이하, 띄어쓰기 포함)
    '밀항하지 않는다': '밀항 안한다', '용서 못 한다!': '용서 못 해', '아가씨에 대해 묻는다': '물어본다', '아가씨를 고른다': '아가씨 선택',
    '쿄토 여인이 낫지': '쿄토 여인!', '허어, 그렇군': '아, 그렇군', '베어 버린다！': '베어 버려！', '잠자리에 든다': '잠을 잔다',
    '즉시 싸운다！': '즉시 싸움！', '제정신으로 되돌린다': '설득한다', '어쩔 수 없다': '할 수 없다', '에도 코마치！': '에도 코마치',
    '뒷거래 통행증': '뒷거래통행증', '들어가지 않는다': '안 들어간다', '아이를 고른다': '아이 고른다', '사실을 말한다': '사실 말한다',
    '어쩔 수 없이': '할 수 없이', '계속 나아간다': '앞으로 간다', '놓아주지 않는다': '안 놓아준다',
}
PREV = {}
PREV_ID = {('D06084', '어떤 아이?'): '어떤 아가씨', ('D06089', '어떤 아이?'): '어떤 아가씨', ('D06084', '어떤 아가씨?'): '어떤 아가씨', ('D06089', '어떤 아가씨?'): '어떤 아가씨', ('D06084', '아이 고른다'): '아가씨 선택', ('D06089', '아이 고른다'): '아가씨 선택', ('D01832', '안 한다'): '밀항 안한다', ('D01844', '안 한다'): '밀항 안한다', ('D05812', '통행증'): '뒷거래통행증', ('D04219', '정신 차리게'): '설득한다',   # 1차 고침 → 하스피 지정
           ('D04084', '아이 고른다'): '아가씨 선택', ('D04089', '아이 고른다'): '아가씨 선택'}
QFIX = {'D10179': ('무슨 일이십니까?', '무슨 일입니까?')}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for v in FIX.values(): assert len(v) <= 6, v
    new = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'samsp_*.tsv'))):
        for l in open(f, encoding='utf8'):
            c = l.rstrip('\n').split('\t')
            if len(c) < 6 or '{0700}' not in c[5]: continue
            pre, post = c[5].split('{0700}', 1); parts = post.split('{0900}')
            parts = [parts[0]] + [PREV_ID.get((c[0], x), PREV.get(x, FIX.get(x, x))) for x in parts[1:]]
            parts = [parts[0]] + [FIX.get(re.sub(r'\{[0-9A-F]{4}\}', '', x), x) if re.sub(r'\{[0-9A-F]{4}\}', '', x) == x else x for x in parts[1:]]
            ko = pre + '{0700}' + '{0900}'.join(parts)
            if c[0] in QFIX: ko = ko.replace(*QFIX[c[0]])
            if ko != c[5]: new[c[0]] = ko; print(c[0], '|', c[5].split('{0700}', 1)[1], '→', ko.split('{0700}', 1)[1])
    print('바뀔 줄', len(new))
    if '--write' in sys.argv:
        p = os.path.join(ROOT, 'work', 'review', 'manual.tsv')
        L = [l for l in open(p, encoding='utf8').read().splitlines() if l.split('\t')[0] not in new]
        open(p, 'w', encoding='utf8').write('\n'.join(L + ['%s\t%s' % kv for kv in new.items()]) + '\n')


if __name__ == '__main__':
    main()
