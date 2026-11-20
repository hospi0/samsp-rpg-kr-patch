# -*- coding: utf-8 -*-
"""하스피 번역 TSV 검수 — 자동 수정 단계(바뀐 줄은 전부 work/review/changes.tsv 에 기록, TSV 는 안 건드림)
  입력: work/review/merged.json(ko) · 수동 수정표 work/review/manual.tsv(id\t새 KO, 있으면 먼저 적용)
  1) 글꼴에 없는 부호: · → ・, 전각 공백 → 공백, 、 → ,, — → ー, ‥ → ・・
  2) 원문 후리가나 자리에 남긴 한자 괄호 «(柳生十兵衛)» 삭제
  3) 제어 코드가 대기(05xx)만 다를 때: 구조 코드 사이 구간마다 원문 대기 코드를 한글 글자 뒤에 고르게 다시 배치
  4) 쪽(03xx·0400·0F00 사이) 안 줄 다시 나누기: 띄어쓰기 자리에서만, 16칸·2줄(원문 쪽이 3줄 이상이면 그 줄 수)
  산출: work/review/fixed.json · changes.tsv · left.tsv(여전히 검사 오류)"""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract as X, build as B, term_check as TC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RV = os.path.join(ROOT, 'work', 'review')
TOK = re.compile(r'\{[0-9A-F]{4}\}')
DELAY = re.compile(r'^\{05[0-9A-F]{2}\}$')
PAGE = B.PAGE
CHARMAP = {'·': '・', '　': ' ', '、': ',', '—': 'ー', '‥': '・・', '･': '・'}


# 용어 통일(하스피 결정 2026-11-20): (원문에 있어야 할 문자열, 원문에 없어야 할 문자열, 잘못된 표기 정규식, 바른 표기)
H = r'(?<![가-힣])'
GLOSS = TC.glossary()
TERMS = [
    ('王虎', None, H + r'왕[호후]', '왕푸'),
    ('チャム', None, H + r'참참', '챰챰'),
    ('美州姫', 'ミヅキ', H + r'미즈키|미슈히메|미슈(?![가-힣]{2})', '비즈키'),
    ('鈴音', None, H + r'스즈네', '레온'),
    ('和狆', None, H + r'와친', '니코친'),
    ('花諷院', None, H + r'가후인', '카후인'),
    ('十兵衛', None, H + r'[쥬주]베(?:이|에)?(?![가-힣]*[다요])', '쥬베이'),
    ('牙神', None, H + r'기바가미', '키바가미'),
    ('ズィーガー', None, H + r'지가(?=$|[^가-힣]|[는를의에도와])', '지거'),
    ('ガルフォード', None, H + r'갤포드', '갈포드'),
    ('シャルロット', None, H + r'샤르로트', '샤를로트'),
    ('服部', None, H + r'하토리', '핫토리'),
    ('枯華院', None, H + r'[고코]카인', '고화원'),
    ('首斬り', None, H + r'쿠비기리', '쿠비키리'),
    ('時貞', None, H + r'도키사다', '토키사다'),
    ('裏五光', None, r'이면\s?오광|뒷\s?오광', '이오광'),
    ('ウプン', None, r'우푼\s?오프', '우픈 오프'),
    ('キルクルス', None, r'키르쿨?루스\s?코르누|키르쿠루스\s?코르누', '키루쿠루스 코루누'),
    ('インペトゥス', None, r'테(?:룸|루무)\s?임페투스', '테룸 인페투스'),
    ('ヌペキ', None, r'칸토(?=\s?시키테)', '칸트'),
    ('鬼の舞', None, r'오니의\s?춤|귀무', '귀신의 춤'),
    ('スプラッシュファーント', None, r'스플래시\s?판트', '스플래시 펀트'),
    ('酒攻撃', None, r'술\s?공격', '주공격'),
    ('三剣洞光', None, H + r'산켄도코', '미츠루기 도코'),
    # 고유명사 통일(용어표 밖, 2026-11-20 — 다수·원문 후리가나 기준)
    ('法鈴', None, H + r'법령', '호린'), ('アンブロジ', None, H + r'(?:안|앰|암)브로지아', '암브로지아'),
    ('アンブ', None, H + r'(?:안부|앰브|암부)(?![가-힣]*로지)', '암브'), ('パレンケ', None, H + r'(?:팔렌케|파렌케)', '팔렝케'),
    ('破怨', None, H + r'파원', '하온'),
    ('界三兄弟', None, H + r'계 ?삼형제', '카이 삼형제'), ('三剣洞光', None, H + r'삼검동광', '미츠루기 도코'),
    ('王竜', None, H + r'왕룡', '왕롱'), ('コルデ', None, H + r'콜데', '코르데'),
    ('チョナチョナ', None, H + r'쵸나쵸나', '초나초나'), ('阿号', None, H + r'아호', '아고'), ('吽号', None, H + r'운호', '운고'),
    ('羅将神', None, H + r'라쇼신', '라쇼진'), ('サムライスピリッツ', None, r'스피릿츠?', '스피리츠'),
    # 거센소리 규칙(일본어 고유명사, 하스피 규칙) — 읽기 사전(pykakasi) 대조로 찾음 2026-11-20
    ('九州', None, H + r'규슈', '큐슈'), ('切支丹', None, H + r'기리시탄', '키리시탄'), ('キリシタン', None, H + r'기리시탄', '키리시탄'),
    ('時姫', None, H + r'도키히메', '토키히메'), ('京都', None, H + r'교토', '쿄토'), ('キョート', None, H + r'교토', '쿄토'),
    ('狂死郎', None, H + r'교시로', '쿄시로'), ('鉄火', None, H + r'뎃카', '텟카'), ('勝山', None, r'카쓰야마', '카츠야마'),
    ('徳川', None, H + r'도쿠가와', '토쿠가와'), ('高崎', None, H + r'다카사키', '타카사키'), ('黒子', None, H + r'구로코', '쿠로코'),
    ('小太夫', None, H + r'고다유', '코다유'), ('太夫', None, H + r'다유', '타유'), ('義経', None, r'요시쓰네', '요시츠네'),
    ('関西', None, H + r'간사이', '칸사이'), ('関東', None, H + r'간토', '칸토'), ('勘蔵', None, H + r'간조', '칸조'),
    ('北町', None, H + r'기타마치', '키타마치'), ('小町', None, H + r'고마치', '코마치'), ('松戸', None, r'마쓰도', '마츠도'),
    ('松本', None, r'마쓰모토', '마츠모토'), ('万太', None, H + r'만다', '만타'), ('河野', None, H + r'고노', '코노'),
    ('川井', None, H + r'가와이', '카와이'), ('床の間', None, H + r'도코노마', '토코노마'), ('歌舞伎', None, H + r'가부키', '카부키'),
    ('富山', None, H + r'도야마', '토야마'), ('天神', None, H + r'덴진', '텐진'), ('東京', None, H + r'도쿄', '토쿄'),
    ('千代田', None, H + r'지요다', '치요다'), ('天狗', None, H + r'덴구', '텐구'),
    ('', None, r'우쓰세미', '우츠세미'), ('', None, r'미쓰루기', '미츠루기'), ('', None, r'게쓰젠', '게츠젠'), ('', None, r'오니쓰노이와', '오니츠노이와'),
    ('', None, r'(?<=[가-힣])쓰(?=노이와)', '츠'),

    ('幻十郎', None, H + r'겐주로', '겐쥬로'),
    ('橘', None, H + r'다치바나', '타치바나'),
    ('三剣洞光', None, H + r'미쓰루기', '미츠루기'),
    ('飛音', None, H + r'히네', '히온'),
    ('波音', None, H + r'나미네', '하온'),
]


def whole_term(jp, k, budget):
    """원문이 용어 하나뿐인 칸(기술·이름 칸) → 용어표 표기 그대로(예산 안일 때만)"""
    j = TC.norm_jp(jp)
    for tj, tk in GLOSS:
        if j == tj.replace('　', '').replace(' ', ''):
            if budget and len(tk) > budget: return k
            return tk
    return k


def fix_terms(jp, k):
    j = TC.norm_jp(jp)
    for need, avoid, pat, good in TERMS:
        if need in j and not (avoid and avoid in j): k = TC.fix_text(k, [(pat, good)])
    return k


# 선택 질문 줄(한 줄 16칸) 줄이기 — {0700} 뒤 첫 구간에만
PROMPT_FIX = [
    (r'묵으시겠습니([까꺼])\s*[?？]\s*[（(](?:1인분|1인|한 사람)\s*[,，]?\s*금\s*(\d+)\s*[）)]', r'묵겠습니\1?（1인 금 \2）'),
    (r'클리어 데이터를 저장하시겠습니까', '클리어 데이터를 저장할까요'), (r'모두 잊어 주실 수 없겠습니까', '모두 잊어 주시겠습니까'),
    (r'할아버지의 이야기를 들으시겠습니까', '할아버지 얘기를 들으시겠어요'), (r'이세의 장로와 이야기하시겠습니까', '이세 장로와 이야기하겠습니까'),
    (r'([을를]) 사시겠습니까', r'\1 살까요'), (r'에도 코마치의 공연을 보고 가시겠습니까', '코마치 공연을 보겠습니까'),
    (r'관문을 (?:통과하시|지나가시)겠습니까', '관문을 지나겠습니까'), (r'배를 타고 벳푸에 가시겠습니까', '배로 벳푸에 가시겠습니까'),
    (r'온천 만주 정식을 드시겠습니까', '온천 만주 정식을 드실래요'), (r'오사카행 정기선을 타시겠습니까', '오사카행 정기선을 탈까요'),
]


def fix_prompt(k):
    if '{0700}' not in k: return k
    pre, post = k.split('{0700}', 1); parts = post.split('{0900}')
    for a, b in PROMPT_FIX: parts[0] = re.sub(a, b, parts[0])
    return pre + '{0700}' + '{0900}'.join(parts)


def jp_of(meta, i): return X.decode(tuple(int(w, 16) for w in meta[i]['words']))


def fix_chars(k):
    for a, b in CHARMAP.items(): k = k.replace(a, b)
    return k


def dots_between_delays(k):
    """«…{05xx}…{05xx}…» 처럼 대기 코드로 이어진 … 는 원문의 ・ 하나씩 → ・"""
    return re.sub(r'…(?:(?:\{05[0-9A-F]{2}\})+…)+', lambda m: m.group(0).replace('…', '・'), k)


def drop_kanji_paren(k):
    k2 = re.sub(r'⏎?[（(][一-鿿・ ]+[）)]', '', k)
    return k2


def redistribute_delays(jp, k):
    """구조 코드(05xx 아닌 것) 순서가 같으면, 구간마다 원문 대기 코드 목록을 한글 글자 뒤에 고르게 배치"""
    js = [t for t in TOK.findall(jp) if not DELAY.match(t)]; ks = [t for t in TOK.findall(k) if not DELAY.match(t)]
    if js != ks: return None
    jparts = re.split(r'(\{[0-9A-F]{4}\})', jp); kparts = re.split(r'(\{[0-9A-F]{4}\})', k)
    def segs(parts):
        out = [[]]; struct = []
        for p in parts:
            if TOK.fullmatch(p) and not DELAY.match(p): struct.append(p); out.append([])
            else: out[-1].append(p)
        return out, struct
    jsg, _ = segs(jparts); ksg, st = segs(kparts)
    res = []
    for n, (jg, kg) in enumerate(zip(jsg, ksg)):
        jd = [p for p in jg if DELAY.match(p or '')]
        ktext = ''.join(p for p in kg if not DELAY.match(p or ''))
        kd_now = [p for p in kg if DELAY.match(p or '')]
        if jd == kd_now: res.append(''.join(kg))
        else:
            # 원문 대기 코드 위치 비율(원문 글자 위치 / 구간 글자 수)을 한글 구간 글자 위치에 옮김
            jtxt_len = sum(len(p) for p in jg if not DELAY.match(p or '')); pos = 0; jpos = []
            for p in jg:
                if DELAY.match(p or ''): jpos.append((pos, p))
                else: pos += len(p)
            L = len(ktext); ins = collections.defaultdict(list)
            for jp_pos, d in jpos:
                at = round(jp_pos / jtxt_len * L) if jtxt_len else L
                ins[min(at, L)].append(d)
            s = ''
            for c_i in range(L + 1):
                s += ''.join(ins.get(c_i, []))
                if c_i < L: s += ktext[c_i]
            res.append(s)
        if n < len(st): res.append(st[n])
    return ''.join(res)


SOFT = '\x01'                                    # 부호 뒤 줄바꿈 자리(공백 없이 나눌 수 있는 곳)
KIWI_PY = 'C:/claude/utils/kiwi-venv/Scripts/python.exe'
def width(s): return len(TOK.sub('', B.normalize(s.replace(SOFT, ''))))


def rewrap_page(page, maxlines):
    lines = page.split('⏎')
    if len(lines) <= maxlines and all(width(l) <= B.LINE for l in lines): return page
    # 합치기: ⏎ 를 공백으로(이미 공백·코드 경계면 그대로)
    s = ''
    for n, l in enumerate(lines):
        if n:
            prev = TOK.sub('', s).rstrip('⏎')
            if prev.endswith(' ') or TOK.sub('', l).startswith(' ') or not prev: s += ''
            elif prev[-1:] in B.PUNCT_SP + '！？，」': s += SOFT
            else: s += ' '
        s += l
    words = re.split(r'(?<=[ \x01])', s)        # 공백·부호 뒤 자리를 앞 낱말 끝에 붙여 나눔
    out = ['']
    for w in words:
        cand = out[-1] + w
        if width(cand.rstrip(' ')) <= B.LINE or not TOK.sub('', out[-1]).strip(): out[-1] = cand
        else: out[-1] = out[-1].rstrip(' '); out.append(w)
    out = [o.rstrip(' ' + SOFT) for o in out]
    if len(out) == 2:                          # 두 줄이면 폭이 고르게 되는 자리로
        best = None; acc = ''
        for n in range(1, len(words)):
            a = ''.join(words[:n]).rstrip(' ' + SOFT); b = ''.join(words[n:]).rstrip(' ' + SOFT)
            wa, wb = width(a), width(b)
            if wa <= B.LINE and wb <= B.LINE and TOK.sub('', a).strip() and TOK.sub('', b).strip():
                if best is None or max(wa, wb) < best[0]: best = (max(wa, wb), a, b)
        if best: out = [best[1], best[2]]
    out = [o.replace(SOFT, '') for o in out]
    if len(out) <= maxlines and all(width(o) <= B.LINE for o in out): return '⏎'.join(out)
    return None


def SPLIT_OK(jp): return not any(t in jp for t in ('{0E00}', '{0700}', '{0900}'))


def split_page(page):
    """2줄에 안 들어가는 쪽 → 최소 쪽 수로, 쪽마다 2줄 안. 쪽 경계는 문장부호 뒤를 우선, 쪽 길이 고르게(DP)"""
    s = re.sub(r' {2,}', ' ', page.replace('⏎', ' '))
    words = re.split(r'(?<= )', s)
    n = len(words); fit = {}
    def ok(a, b):
        if (a, b) not in fit: fit[(a, b)] = rewrap_page(''.join(words[a:b]).rstrip(' '), 2)
        return fit[(a, b)]
    INF = float('inf'); best = [(INF, INF, None)] * (n + 1); best[0] = (0, 0, None)
    for b in range(1, n + 1):
        for a in range(b - 1, -1, -1):
            if best[a][0] == INF: continue
            if width(''.join(words[a:b]).rstrip(' ')) > B.LINE * 2 + 2: break
            if ok(a, b) is None: continue
            seg = TOK.sub('', ''.join(words[a:b]).rstrip(' '))
            punct = seg[-1:] in '.!?…！？。・」' if b < n else True
            cost = (best[a][0] + 1, best[a][1] + (B.LINE * 2 - width(seg)) ** 2 + (0 if punct else 60))
            if cost < best[b][:2]: best[b] = (cost[0], cost[1], a)
    if best[n][0] == INF: return None
    cuts = []; b = n
    while b: a = best[b][2]; cuts.append((a, b)); b = a
    return '{쪽}'.join(ok(a, b) for a, b in reversed(cuts))


def rewrap(jp, k):
    jpp = [p.split('⏎') for p in PAGE.split(jp)]
    seps = PAGE.findall(k); pages = PAGE.split(k); new = []; ok = True
    for n, p in enumerate(pages):
        ml = max(B.LINES, len(jpp[n]) if n < len(jpp) else B.LINES)
        r = rewrap_page(p, ml)
        if r is None and SPLIT_OK(jp): r = split_page(p)
        if r is None: ok = False; r = p
        new.append(r)
    s = new[0]
    for sep, p in zip(seps, new[1:]): s += sep + p
    return s, ok


def main():
    meta = json.load(open(os.path.join(ROOT, 'work', 'extract.json'), encoding='utf8'))
    KO = json.load(open(os.path.join(RV, 'merged.json'), encoding='utf8'))['ko']
    man = {}
    mp = os.path.join(RV, 'manual.tsv')
    if os.path.exists(mp):
        for l in open(mp, encoding='utf8').read().splitlines():
            if l and not l.startswith('#'): a, b = l.split('\t', 1); man[a] = b
    log = []; fixed = {}; left = []; stage1 = {}
    for i, k0 in KO.items():
        jp = jp_of(meta, i); k = man.get(i, k0); why = ['수동'] if i in man else []
        k1 = fix_prompt(k)
        if k1 != k: why.append('선택질문'); k = k1
        k1 = fix_chars(k)
        if k1 != k: why.append('부호'); k = k1
        k1 = whole_term(jp, k, meta[i].get('budget') if meta[i]['kind'] != 'dlg' else None)
        if k1 != k: why.append('용어칸'); k = k1
        k1 = fix_terms(jp, k)
        bud = meta[i].get('budget') if meta[i]['kind'] != 'dlg' else None
        if k1 != k and bud and len(TOK.sub('', B.normalize(k1)).replace('⏎', '')) > bud: k1 = k   # 고정 칸 예산 넘으면 용어 치환 안 함(질문 목록)
        if k1 != k: why.append('용어'); k = k1
        k1 = dots_between_delays(k)
        if k1 != k: why.append('점'); k = k1
        k1 = drop_kanji_paren(k)
        if k1 != k: why.append('한자괄호'); k = k1
        stage1[i] = (k, why)
    # 대기 코드 자리 띄어쓰기(Kiwi, kiwi-venv) — 줄 나누기 전에
    import subprocess
    dl = {i: kw[0] for i, kw in stage1.items() if meta[i]['kind'] == 'dlg' and '{05' in kw[0]}
    r = subprocess.run([KIWI_PY, '-X', 'utf8', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiwi_wait_space.py')],
                       input=json.dumps(dl, ensure_ascii=False).encode('utf8'), capture_output=True, check=True)
    sp = json.loads(r.stdout.decode('utf8'))
    for i, new in sp.items(): stage1[i] = (new, stage1[i][1] + ['대기띄어쓰기'])
    for i, k0 in KO.items():
        jp = jp_of(meta, i); k, why = stage1[i]
        if TOK.findall(B.normalize(k)) != TOK.findall(jp):
            r = redistribute_delays(jp, k)
            if r is not None and TOK.findall(B.normalize(r)) == TOK.findall(jp): why.append('대기코드'); k = r
        if meta[i]['kind'] == 'dlg' and '{0700}' not in jp and '{0900}' not in jp:
            r, ok = rewrap(jp, k)
            if r != k: why.append('줄나눔'); k = r
        elif meta[i]['kind'] == 'dlg' and '{0700}' in jp and '{0700}' in k:      # 선택지: 질문 앞 대사 부분만 다시 나눔(쪽 추가 없음)
            pk, qk = k.split('{0700}', 1); pj = jp.split('{0700}', 1)[0]
            r, ok = rewrap(pj + '{0E00}', pk)                                   # {0E00} 표식 = 쪽 추가 금지
            if r != pk: why.append('줄나눔'); k = r + '{0700}' + qk
        fixed[i] = k
        if k != k0: log.append((i, '+'.join(why), k0, k))
        e = []; w = []
        B.check_row(i, meta[i]['kind'], B.normalize(k), jp, B.budget_of(i, meta[i], meta), e, w, B.line_limit(meta[i]))
        for x in e: left.append((i, x[1], jp, k))
    json.dump(fixed, open(os.path.join(RV, 'fixed.json'), 'w', encoding='utf8'), ensure_ascii=False)
    with open(os.path.join(RV, 'changes.tsv'), 'w', encoding='utf8') as f:
        f.write('id\t사유\t전\t후\n'); [f.write('\t'.join(x) + '\n') for x in log]
    with open(os.path.join(RV, 'left.tsv'), 'w', encoding='utf8') as f:
        f.write('id\t오류\tJP\tKO\n'); [f.write('\t'.join(x) + '\n') for x in left]
    c = collections.Counter(w for x in log for w in x[1].split('+'))
    lc = collections.Counter(re.sub(r'\d+', 'N', x[1].split(':')[0]) for x in left)
    print('바뀐 줄', len(log), dict(c)); print('남은 오류', len(left), dict(lc))


if __name__ == '__main__':
    main()
