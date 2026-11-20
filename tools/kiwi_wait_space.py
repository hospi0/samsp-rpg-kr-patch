# -*- coding: utf-8 -*-
"""대기 코드({05xx}) 자리 띄어쓰기 — kiwi-venv 에서 실행. stdin JSON {id: text} → stdout JSON {id: new_text}(바뀐 것만)
규칙: 한글 사이에 {05xx}(여러 개 가능)만 끼고 공백이 없는 자리에서,
  - 양쪽 한글 조각이 둘 다 1음절이면(한 글자씩 끊어 읽기 «허{0501}허») 건드리지 않음
  - Kiwi 형태소 분석으로 오른쪽 첫 형태소가 조사·어미·접미사·지정사(J* E* XS* VCP) 이거나 왼쪽 끝이 접두사(XP)면 낱말 안 → 그대로
  - 그 밖(새 어절 시작)이면 대기 코드 «뒤»에 공백을 넣음"""
import sys, re, json
from kiwipiepy import Kiwi

kiwi = Kiwi()
NAMES = ['하오마루', '나코루루', '갈포드', '우쿄', '겐쥬로', '챰챰', '레온', '쥬베이', '니코친', '가이라', '아마쿠사', '미즈키', '비즈키',
         '하온', '히온', '왕푸', '지거', '샤를로트', '쿄시로', '생제르맹', '스테아', '어스퀘이크', '리무루루', '마마하하', '시쿠루', '파피']
for n in NAMES: kiwi.add_user_word(n, 'NNP')
TOK = re.compile(r'\{[^}]*\}|⏎')
RUN = re.compile(r'(?<=[가-힣])((?:\{05[0-9A-F]{2}\})+)(?=[가-힣])')


def plain_map(s):
    """토큰 뺀 글과, 원문 위치 → 글 위치 표"""
    out = ''; pos = {}
    i = 0
    while i < len(s):
        m = TOK.match(s, i)
        if m:
            pos[i] = len(out)
            if m.group(0) == '⏎': out += ' '
            i = m.end(); continue
        pos[i] = len(out); out += s[i]; i += 1
    pos[len(s)] = len(out)
    return out, pos


def main():
    data = json.load(sys.stdin); res = {}
    for i, s in data.items():
        cands = [m for m in RUN.finditer(s)]
        if not cands: continue
        text, pos = plain_map(s)
        toks = kiwi.tokenize(text)
        starts = {t.start: t for t in toks}
        ends = {t.start + t.len: t for t in toks}
        ins = []
        for m in cands:
            a = m.start(); b = m.end()
            lseg = re.search(r'[가-힣]+$', TOK.sub(lambda x: '\x00', s[:a])).group(0)
            rseg = re.match(r'[가-힣]+', s[b:]).group(0)
            if len(lseg) == 1 and len(rseg) == 1: continue
            p = pos[b]
            rt = starts.get(p); lt = ends.get(p)
            if rt is None or lt is None: continue          # 형태소 경계가 아니면 낱말 안
            if re.match(r'^(J|E|XS|VCP)', rt.tag) or lt.tag.startswith('XP'): continue
            ins.append(b)
        if ins:
            new = s
            for b in sorted(ins, reverse=True): new = new[:b] + ' ' + new[b:]
            res[i] = new
    json.dump(res, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
