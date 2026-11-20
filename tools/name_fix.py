# -*- coding: utf-8 -*-
"""고유명사 전수조사 고침(2026-11-21, tools/name_survey.py 결과 · 하스피 결정: 벨몬트, 토키사다는 칸 안 넘으면)
  현재 TSV KO 에 «원문 조건 + 잘못된 표기 → 바른 표기»(뒤 조사 받침 맞춤) → work/review/manual.tsv 에 id 별로 덮어 넣기.
  python tools/name_fix.py [--write]   (없으면 바뀔 줄만 출력)"""
import os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import term_check as TC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = r'(?<![가-힣])'
# (원문에 있어야 할 문자열, 잘못된 표기 정규식, 바른 표기)
RULES = [
    ('和狆', H + r'와[츄추친]', '니코친'),
    ('羅将神', H + r'(?:나찰장군신|나장신|라쇼신)', '라쇼진'),
    ('北京', H + r'북경(?!채관)', '베이징'),
    ('法鈴', H + r'법방울', '호린'),
    ('恐山', H + r'오소레산', '오소레야마'),
    ('アンブ', H + r'앙브', '암브'),
    ('安生村', H + r'(?:안생촌|안조무라|안조마을)', '안조 마을'), ('安城村', H + r'(?:안조무라|안조마을)', '안조 마을'),   # 村 = «마을»(하스피 2026-11-21)
    ('忍野村', H + r'(?:오시노무라|오시노마을)', '오시노 마을'),
    ('ステア', H + r'스테어', '스테아'),
    ('吽号', r'훔고', '운고'),
    ('京', H + r'교토', '쿄토'),
    ('ホーリー', H + r'호리', '홀리'),
    ('東海', H + r'도카이', '토카이'),
    ('月前', H + r'츠키마에', '게츠젠'),
    ('牙神', H + r'가신(?=\))', '키바가미'),
    ('バナナン', H + r'바나나(?!난)', '바나난'),
    ('ベルモント', H + r'(?:베르몬트|벨몽|베르몽)', '벨몬트'),
    ('サンゼルマン', H + r'상제르망', '생제르맹'), ('パクパク', H + r'팍팍', '파쿠파쿠'), ('眠眠', H + r'면면', '민민'), ('大虎', H + r'대호', '다후'),   # 2차(목록 밖) 조사
    ('ルプシ', H + r'루프시', '루푸시'), ('シャンバラ', H + r'샴발라', '샹발라'),
    ('ナハトムジーク', H + r'나하트무지크', '나흐트무지크'),
    ('インペトゥス', H + r'임페투스', '인페투스'), ('エデッセ', H + r'에데세', '에뎃세'), ('サリーレ', H + r'살리레', '사리레'),
    ('キルクルス', H + r'키르쿠루스', '키루쿠루스'), ('コルヌー', H + r'코르누', '코루누'), ('エプンキネ', H + r'에푼키네', '에픈키네'),
]
# 줄마다 손으로(낱말이 흔한 말과 겹치거나 띄어쓰기까지 고칠 것)
BY_ID = {
    'D00565': [(r'참', '챰')], 'D01464': [(r'참이세요', '챰이세요')], 'D04633': [(r'참은', '챰은')],
    'X00169': [(r'^참 ', '챰 ')], 'X00171': [(r'^참 ', '챰 ')],
    'D05020': [(r'아마쿠사 시로님', '아마쿠사 시로 토키사다 님')], 'D05713': [(r'아마쿠사 시로의', '아마쿠사 시로 토키사다의')],
    'D08469': [(r'아마쿠사 시로는', '아마쿠사 시로 토키사다는')],
    'P0281': [(r'카무이 의 항구', '카무이의 항구')], 'D10084': [(r'카무이 의 항구', '카무이의 항구')],
    'D03631': [(r'냠냠!', '파쿠파쿠!')], 'D00697': [(r'상제\{0501\}르\{0501\}망\{0501\}님\{0501\}이\{0504\}만', '생제{0501}르{0501}맹{0501} 님{0501}이{0504} 만'), (r'최\{0501\}강\{0501\}육탄', '최{0501}강{0501} 육탄')], 'D09171': [(r'시로 오오노', '시로 오노')],
    'D01657': [(r'에도의\{0506\}주\{0501\}베\{0501\}이\{0501\}님', '에도의{0506} 쥬{0501}베{0501}이{0501} 님')],
    'D02543': [(r'게츠젠 이라 한다', '게츠젠이라 한다')],
    'E00497': [(r'금방울과 쌍', '금 호린 짝')], 'E00499': [(r'은방울', '은 호린')], 'E00504': [(r'금방울', '금 호린')],
}
# 天草四郎時貞: 줄마다(BY_ID) — 이미 «시로⏎토키사다»로 들어간 줄이 있음 · 적 이름 N00202 은 8자 칸이라 «아마쿠사 시로» 그대로
SKIP_RULE = set()
COP = re.compile(r'(?<=[가-힣])(이)(?=다|야|었|에요|예요|지[만요]?(?![가-힣]))')


def fix(ko, pat, good):
    """term_check.fix_text + 서술격 조사(이다·이야·이었…)는 조사 바꾸기에서 빼고 받침 없는 말 뒤면 줄임(안조무라다·오소레야마였던)"""
    rx = re.compile('(?:%s)(?!이(?:다|야|었|에요))' % pat)
    ko = TC.fix_text(ko, [('(?:%s)(?!이(?:다|야|었|에요))' % pat, good)])
    def cop(m):
        b = (ord(good[-1]) - 0xAC00) % 28
        if m.group(1) == '었': return '였' if not b else '이었'
        return ('' if not b else '이') + m.group(1)
    return re.sub('(?:%s)이(다|야|었|에요)' % pat, lambda m: good + cop(m), ko)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    new = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'samsp_*.tsv'))):
        for l in open(f, encoding='utf8'):
            c = l.rstrip('\n').split('\t')
            if len(c) < 6 or c[0] == 'id': continue
            jp = re.sub(r'[\s　]', '', TC.TOK.sub('', c[4])); ko = c[5]
            for need, pat, good in RULES:
                if need in jp and (c[0], need) not in SKIP_RULE: ko = fix(ko, pat, good)
            for pat, good in BY_ID.get(c[0], []): ko = re.sub(pat, good, ko)
            ko = re.sub(r'(?<=마을)(다|야)(?![가-힣])', lambda m: '이' + m.group(1), ko)   # 받침 있는 바뀐 이름 뒤 서술격(안조 마을이다)
            if ko != c[5]: new[c[0]] = (c[5], ko)
    for i, (a, b) in new.items(): print(i, '|', a.replace('\n', ''), '\n   →', b)
    print('바뀔 줄 %d' % len(new))
    if '--write' in sys.argv:
        p = os.path.join(ROOT, 'work', 'review', 'manual.tsv')
        L = [l for l in open(p, encoding='utf8').read().splitlines() if l.split('\t')[0] not in new]
        L += ['%s\t%s' % (i, b) for i, (a, b) in new.items()]
        open(p, 'w', encoding='utf8').write('\n'.join(L) + '\n')
        print('manual.tsv 에 %d줄 반영' % len(new))


if __name__ == '__main__':
    main()
