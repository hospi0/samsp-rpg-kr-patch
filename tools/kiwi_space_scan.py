# -*- coding: utf-8 -*-
r"""번역 KO 의 «붙여 쓴 띄어쓰기» 검출·교정안 (kiwi-venv 에서 실행, 2026-11-21 하스피 «띄어쓰기 토나옴»)
  C:/claude/utils/kiwi-venv/Scripts/python.exe -X utf8 tools/kiwi_space_scan.py  → work/review/space_scan.tsv (id\t옛 KO\t새 KO\t고친 자리)
규칙(reference_kiwi_spacing_detector): 제어 코드·⏎ 를 빼고 분석해서
  - 앞 형태소가 조사·어미(J*·E*) 이고 뒤가 체언·용언·부사·관형사·감탄사로 시작하는데 공백 없는 자리
  - 고유명사(NNP)끼리 맞붙은 자리(아마쿠사시로토키사다)
  만 «새 어절 시작»으로 본다. 공백은 그 자리 앞 제어 코드들 «뒤»(다음 글자 바로 앞)에 넣는다.
  ⏎·{03xx}·{04xx}·{쪽} 은 경계(공백 취급) — 줄·쪽이 바뀌는 자리엔 안 넣음.
  한 글자씩 끊어 읽기(허{0501}허{0501}허) 는 양쪽이 한 음절씩이면 건드리지 않음.
"""
import glob, os, re, sys
from kiwipiepy import Kiwi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kiwi_wait_space import NAMES

kiwi = Kiwi()
for n in NAMES + ['시로', '토키사다', '한조', '하오마루', '텐히메', '토키히메', '츠키마에', '하쿠도', '쥬베이', '야규']:
    kiwi.add_user_word(n, 'NNP')
TOK = re.compile(r'\{[^}]*\}|⏎')
BREAK = re.compile(r'⏎|\{(?!05)[0-9A-F]{4}\}|\{쪽\}')     # {05xx} 대기만 글 안, 나머지(쪽·선택지·화자 등)는 경계
CONTENT = re.compile(r'^(NNG|NNP|NP|NR|VV|VA|MAG|MAJ|MM|IC)(-[IR])?$')
PACED_R = re.compile(r'^(NNG|NNP|NNB|NP|NR|VV|VA|MAG|MAJ|MM|IC|XPN)(-[IR])?$')
KNOWN = set(NAMES + ['시로', '토키사다', '한조', '텐히메', '토키히메', '츠키마에', '하쿠도', '야규'])


def plain(s):
    out = []; pos = []          # pos[k] = 원문 인덱스 (글자 k 의)
    i = 0
    while i < len(s):
        m = TOK.match(s, i)
        if m:
            if BREAK.fullmatch(m.group(0)): out.append(' '); pos.append(None)
            i = m.end(); continue
        out.append(s[i]); pos.append(i); i += 1
    return ''.join(out), pos


def fix(s):
    text, pos = plain(s)
    toks = kiwi.tokenize(text)
    ins = []
    # 한 음절씩 대기 코드로 끊은 대사(원문 한자마다 {0501}) — 음절 사이 절반 이상에 {05xx}
    gaps = re.findall(r'[가-힣](\{05[0-9A-F]{2}\})*(?=[가-힣])', s)
    paced = len(gaps) >= 4 and sum(1 for g in gaps if g) * 2 >= len(gaps)
    for a, b in zip(toks, toks[1:]):
        p = b.start
        if p != a.start + a.len or p == 0: continue
        if not ('가' <= text[p - 1] <= '힣' and '가' <= text[p] <= '힣'): continue
        glued = (paced and re.match(r'^(J|EC|EF|ETM)', a.tag) and PACED_R.match(b.tag)) or                 (re.match(r'^J', a.tag) and CONTENT.match(b.tag) and b.len >= 2) or                 (a.tag in ('EF', 'EC') and re.match(r'^(NNG|NNP|NP|MAG|MM)$', b.tag) and b.len >= 2) or \
                (a.form in KNOWN and b.form in KNOWN)
        if not glued: continue
        if re.fullmatch(r'([아어에오우으])*[~!？！?]*', re.match(r'[가-힣]+', text[p:]).group(0)): continue   # «떠난다아아» 늘임
        lw = re.search(r'[가-힣]+$', text[:p]).group(0); rw = re.match(r'[가-힣]+', text[p:]).group(0)
        if len(lw) == 1 and len(rw) == 1 and text[p - 1] == text[p] and not paced: continue   # 허허 끊어 읽기
        ins.append(pos[p])
    new = s
    for q in sorted(ins, reverse=True): new = new[:q] + ' ' + new[q:]
    return new, len(ins)


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'samsp_dlg_*.tsv'))):
        for l in open(f, encoding='utf-8'):
            c = l.rstrip('\n').split('\t')
            if len(c) < 6 or c[0] == 'id' or not c[5]: continue
            new, n = fix(c[5])
            if n: rows.append((c[0], c[5], new, n))
    out = os.path.join(ROOT, 'work', 'review', 'space_scan.tsv')
    with open(out, 'w', encoding='utf-8') as w:
        w.write('id\t옛 KO\t새 KO\t고친 자리\n')
        for r in rows: w.write('%s\t%s\t%s\t%d\n' % r)
    print(len(rows), '줄', sum(r[3] for r in rows), '자리 →', out)


if __name__ == '__main__':
    main()
