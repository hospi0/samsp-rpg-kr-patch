# -*- coding: utf-8 -*-
"""고유명사 표기 검사(용어표 밖) — 원문 가타카나 낱말·후리가나 붙은 한자 이름을 우리 규칙(か행 ㅋ·た행 ㅌ·つ 츠)으로 음역,
번역에서 그 이름 자리에 쓰인 변형을 모아 «여러 표기» 또는 «규칙과 다른 표기»만 보고.
  python tools/name_check.py [fixed.json]  → work/review/names.tsv"""
import os, sys, re, json, collections, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract as X

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'; JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
def syl(c, v, f=0): return chr(0xAC00 + (CHO.index(c) * 21 + JUNG.index(v)) * 28 + f)
def kata(s): return ''.join(chr(ord(ch) - 0x60) if 'ァ' <= ch <= 'ヶ' else ch for ch in s)   # → 히라가나
BASE = {}
rows = {'': 'ㅇ', 'k': 'ㅋ', 'g': 'ㄱ', 's': 'ㅅ', 'z': 'ㅈ', 't': 'ㅌ', 'd': 'ㄷ', 'n': 'ㄴ', 'h': 'ㅎ', 'b': 'ㅂ', 'p': 'ㅍ', 'm': 'ㅁ', 'y': 'ㅇ', 'r': 'ㄹ', 'w': 'ㅇ'}
KANA = {'あ': ('', 'ㅏ'), 'い': ('', 'ㅣ'), 'う': ('', 'ㅜ'), 'え': ('', 'ㅔ'), 'お': ('', 'ㅗ'),
        'か': ('k', 'ㅏ'), 'き': ('k', 'ㅣ'), 'く': ('k', 'ㅜ'), 'け': ('k', 'ㅔ'), 'こ': ('k', 'ㅗ'),
        'が': ('g', 'ㅏ'), 'ぎ': ('g', 'ㅣ'), 'ぐ': ('g', 'ㅜ'), 'げ': ('g', 'ㅔ'), 'ご': ('g', 'ㅗ'),
        'さ': ('s', 'ㅏ'), 'し': ('s', 'ㅣ'), 'す': ('s', 'ㅡ'), 'せ': ('s', 'ㅔ'), 'そ': ('s', 'ㅗ'),
        'ざ': ('z', 'ㅏ'), 'じ': ('z', 'ㅣ'), 'ず': ('z', 'ㅡ'), 'ぜ': ('z', 'ㅔ'), 'ぞ': ('z', 'ㅗ'),
        'た': ('t', 'ㅏ'), 'ち': ('ch', 'ㅣ'), 'つ': ('ch', 'ㅡ'), 'て': ('t', 'ㅔ'), 'と': ('t', 'ㅗ'),
        'だ': ('d', 'ㅏ'), 'ぢ': ('z', 'ㅣ'), 'づ': ('z', 'ㅡ'), 'で': ('d', 'ㅔ'), 'ど': ('d', 'ㅗ'),
        'な': ('n', 'ㅏ'), 'に': ('n', 'ㅣ'), 'ぬ': ('n', 'ㅜ'), 'ね': ('n', 'ㅔ'), 'の': ('n', 'ㅗ'),
        'は': ('h', 'ㅏ'), 'ひ': ('h', 'ㅣ'), 'ふ': ('h', 'ㅜ'), 'へ': ('h', 'ㅔ'), 'ほ': ('h', 'ㅗ'),
        'ば': ('b', 'ㅏ'), 'び': ('b', 'ㅣ'), 'ぶ': ('b', 'ㅜ'), 'べ': ('b', 'ㅔ'), 'ぼ': ('b', 'ㅗ'),
        'ぱ': ('p', 'ㅏ'), 'ぴ': ('p', 'ㅣ'), 'ぷ': ('p', 'ㅜ'), 'ぺ': ('p', 'ㅔ'), 'ぽ': ('p', 'ㅗ'),
        'ま': ('m', 'ㅏ'), 'み': ('m', 'ㅣ'), 'む': ('m', 'ㅜ'), 'め': ('m', 'ㅔ'), 'も': ('m', 'ㅗ'),
        'や': ('y', 'ㅑ'), 'ゆ': ('y', 'ㅠ'), 'よ': ('y', 'ㅛ'), 'ら': ('r', 'ㅏ'), 'り': ('r', 'ㅣ'), 'る': ('r', 'ㅜ'),
        'れ': ('r', 'ㅔ'), 'ろ': ('r', 'ㅗ'), 'わ': ('w', 'ㅘ'), 'を': ('', 'ㅗ'), 'ゔ': ('b', 'ㅜ')}
SMALL = {'ゃ': 'ㅑ', 'ゅ': 'ㅠ', 'ょ': 'ㅛ', 'ぁ': 'ㅏ', 'ぃ': 'ㅣ', 'ぅ': 'ㅜ', 'ぇ': 'ㅔ', 'ぉ': 'ㅗ'}
YV = {'ㅑ': 'ㅑ', 'ㅠ': 'ㅠ', 'ㅛ': 'ㅛ'}


def translit(s):
    """음역(규칙: か행 ㅋ·た행 ㅌ·つ 츠·ち 치·ちゃ 챠·ん ㄴ받침·っ ㅅ받침·ー 생략)"""
    h = kata(s); out = []; i = 0
    while i < len(h):
        ch = h[i]
        if ch == 'ん' and out: out[-1] = out[-1][:2] + ['ㄴ']; i += 1; continue
        if ch == 'っ': out.append('っ'); i += 1; continue
        if ch in 'ーｰ～': i += 1; continue
        if ch not in KANA: i += 1; continue
        c, v = KANA[ch]; nx = h[i + 1] if i + 1 < len(h) else ''
        if nx in SMALL:
            sv = SMALL[nx]
            if sv in YV and v == 'ㅣ': v = sv
            elif ch in 'ふ' : v = sv
            elif ch in 'てで' and sv == 'ㅣ': v = 'ㅣ'
            elif ch in 'うゔ': v = {'ㅏ': 'ㅝ', 'ㅣ': 'ㅟ', 'ㅔ': 'ㅞ', 'ㅗ': 'ㅝ'}.get(sv, sv); c = 'w' if ch == 'う' else c
            else: v = sv
            i += 1
        cj = {'ch': 'ㅊ'}.get(c, rows.get(c, 'ㅇ'))
        if c == 's' and v in ('ㅑ', 'ㅠ', 'ㅛ') and ch == 'し': v = {'ㅑ': 'ㅑ', 'ㅠ': 'ㅠ', 'ㅛ': 'ㅛ'}[v]
        if c == 'z' and v in ('ㅑ', 'ㅠ', 'ㅛ'): v = v                    # じゃ 쟈
        if c == 'ch' and v in ('ㅑ', 'ㅠ', 'ㅛ'): v = v                    # ちゃ 챠
        out.append([cj, v, None])
        i += 1
    s2 = ''; prev_tt = False
    for o in out:
        if o == 'っ':
            if s2 and '가' <= s2[-1] <= '힣': b = ord(s2[-1]) - 0xAC00; s2 = s2[:-1] + chr(0xAC00 + b - b % 28 + 19)
            continue
        f = 4 if o[2] == 'ㄴ' else 0
        try: s2 += syl(o[0], o[1], f)
        except ValueError: pass
    return s2


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'review', 'fixed.json')
    meta = json.load(open(os.path.join(ROOT, 'work', 'extract.json'), encoding='utf8'))
    F = json.load(open(src, encoding='utf8'))
    J = {i: re.sub(r'\{[^}]*\}|⏎', '', X.decode(tuple(int(w, 16) for w in m['words']))) for i, m in meta.items()}
    K = {i: re.sub(r'\{[^}]*\}|⏎', ' ', v) for i, v in F.items()}
    names = collections.defaultdict(set)               # 원문 표기 → 줄
    reading = {}
    for i, t in J.items():
        if i not in F: continue
        for w in re.findall(r'[ァ-ヶー]{3,}', t): names[w].add(i); reading[w] = w
        for w, r in re.findall(r'([一-鿿々]{2,6})[（(]([ぁ-んァ-ヶー　 ]{2,})[）)]', t):
            reading[w] = r.replace('　', '').replace(' ', '')
    for w in list(reading):
        if not re.fullmatch(r'[ァ-ヶー]+', w):
            for i, t in J.items():
                if w in t and i in F: names[w].add(i)
    out = []
    for w, ids in names.items():
        if len(ids) < 2: continue
        exp = translit(reading[w])
        if len(exp) < 2: continue
        var = collections.Counter(); miss = []
        for i in ids:
            words = re.findall(r'[가-힣]+', K[i]); best = None
            for x in words:
                for n in range(len(exp) - 1, len(exp) + 2):
                    y = x[:n]
                    r = difflib.SequenceMatcher(None, y, exp).ratio()
                    if best is None or r > best[0]: best = (r, y)
            if best and best[0] >= 0.5: var[best[1]] += 1
            else: miss.append(i)
        if not var: continue
        top = var.most_common(1)[0][0]
        if len(var) > 1 or top != exp:
            out.append((w, reading[w], exp, len(ids), var.most_common(6), miss[:5]))
    out.sort(key=lambda x: -x[3])
    with open(os.path.join(ROOT, 'work', 'review', 'names.tsv'), 'w', encoding='utf8') as f:
        f.write('원문\t읽기\t규칙 음역\t줄\t번역 변형\t못 찾은 줄\n')
        for r in out: f.write('\t'.join(map(str, r)) + '\n')
    print('검사 이름', len([w for w in names if len(names[w]) >= 2]), '· 보고', len(out))
    for r in out[:60]: print(r[0], r[1], '→', r[2], r[3], r[4])


if __name__ == '__main__':
    main()
