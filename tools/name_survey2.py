# -*- coding: utf-8 -*-
"""고유명사 전수조사 2차 — name_survey.py 목록 «밖» 이름(2026-11-21)
  후보 = 원문 가타카나 낱말(2자+) · 후리가나 붙은 한자 · 존칭(様·殿·さん·公·どの·さま·ちゃん·大人·和尚·先生) 앞 한자 낱말
  읽기 = 후리가나 > pykakasi(utils/whisper-venv) → 거센소리 음역(name_check.translit)
  줄마다 번역에서 음역과 가장 닮은 낱말(조사·존칭 뗌)을 모아 «표기 여러 개 / 못 찾음»을 보고.
  python tools/name_survey2.py → work/review/name_survey2.tsv"""
import os, re, sys, glob, collections, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import name_check as NC, name_survey as NS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r'\{[^}]*\}|⏎')
HON = r'(?:様|さま|殿|どの|さん|公|ちゃん|大人|和尚|先生|姫)'
SUF = sorted(['님', '씨', '공', '의', '은', '는', '이', '가', '을', '를', '에게', '에서', '와', '과', '도', '만', '로', '으로', '이여', '여',
              '야', '아', '라고', '이라고', '한테', '께', '께서', '이다', '다', '이야', '이랑', '랑', '에', '부터', '까지', '처럼', '님의', '님이',
              '님은', '님을', '님께', '공의', '공은', '공이', '씨가', '씨는', '씨의'], key=len, reverse=True)


def core(w):
    for s in SUF:
        if w.endswith(s) and len(w) - len(s) >= 2: return w[:-len(s)]
    return w


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path.append(os.path.join(ROOT, '..', '..', 'utils', 'whisper-venv', 'Lib', 'site-packages'))   # pykakasi(순수 파이썬)
    import pykakasi
    kks = pykakasi.kakasi()
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'samsp_*.tsv'))):
        for l in open(f, encoding='utf8'):
            c = l.rstrip('\n').split('\t')
            if len(c) >= 6 and c[0] != 'id' and c[5]: rows.append((c[0], c[1], TOK.sub('', c[4]).replace('　', ''), TOK.sub(' ', c[5])))
    known = set(NS.names())
    reading = {}
    for _, _, jp, _ in rows:
        for w in re.findall(r'[ァ-ヶ][ァ-ヶー]{1,}', jp): reading.setdefault(w, w)
        for w, r in re.findall(r'([一-鿿々]{1,6})[（(]([ぁ-んァ-ヶー ]{2,})[）)]', jp): reading[w] = r.replace(' ', '')
        for w in re.findall(r'([一-鿿々]{2,5})' + HON, jp):
            if w not in reading: reading[w] = ''.join(x['hira'] for x in kks.convert(w))
    cand = {w: r for w, r in reading.items() if not any(w in k or k in w for k in known if len(k) >= 2)}
    ids = collections.defaultdict(list)
    for i, kind, jp, ko in rows:
        for w in cand:
            if w in jp: ids[w].append((i, ko))
    out = []
    for w, L in ids.items():
        exp = NC.translit(cand[w])
        if len(exp) < 2: continue
        var = collections.Counter(); ex = collections.defaultdict(list); miss = []
        for i, ko in L:
            best = None
            for x in re.findall(r'[가-힣]+', ko):
                y = core(x); r = difflib.SequenceMatcher(None, y, exp).ratio()
                if best is None or r > best[0]: best = (r, y)
            if best and best[0] >= 0.6: var[best[1]] += 1; ex[best[1]].append(i)
            else: miss.append(i)
        if len(var) > 1:
            out.append((w, cand[w], exp, len(L), ' · '.join('%s %d(%s)' % (v, n, ','.join(ex[v][:3])) for v, n in var.most_common(6)),
                        ','.join(miss[:6])))
    out.sort(key=lambda x: -x[3])
    p = os.path.join(ROOT, 'work', 'review', 'name_survey2.tsv')
    open(p, 'w', encoding='utf8').write('원문\t읽기\t음역\t줄\t번역 표기(예 id)\t못 찾은 줄\n' + ''.join('\t'.join(map(str, r)) + '\n' for r in out))
    print('후보 %d · 출현 %d · 표기 여럿 %d → %s' % (len(cand), len(ids), len(out), p))


if __name__ == '__main__':
    main()
