# -*- coding: utf-8 -*-
"""타이틀 로고 한글화(VDP1 스프라이트 덩어리, 사본 C_ALL#3 8.6·#5 7.15·#16 7.0)
  덩어리마다: 화면 위치대로 합성 → 줄별 채움색(0·15 제외 최빈)·테두리 15 학습 → 덩어리 칸 비우고 한글 그림 → 스프라이트 칸대로 잘라 넣기
  산출 work/gfx/title.json · work/preview/gfx_title_원본_새것.png"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import sprites as S, spredit as P

ST = '타이틀'
BHS = 'C:/claude/utils/font/blackhansans/BlackHanSans-Regular.ttf'
MYEONG = 'C:/claude/utils/font/nanum-myeongjo/NanumMyeongjoExtraBold.ttf'
# (이름, 스프라이트, [(상자, 글, 글꼴)], 채움 단계(위→아래), 안쪽 테두리, 바깥 테두리, 그림자 색, 그림자 거리)
GROUPS = [
    ('무사도열전', [0x7EC20, 0x7EA00, 0x7E7E0, 0x7E5C0, 0x7E3A0, 0x7DE80, 0x7D2C0], [((66, 74, 182, 56), '무사도열전', BHS)],
     (9, 8, 7, 6, 5, 4, 3), 15, 1, 12, 3),
    ('진설 사무라이 스피리츠', [0x7EE40, 0x7F5C0], [((82, 28, 30, 16), '진설', MYEONG), ((82, 45, 150, 24), '사무라이 스피리츠', BHS)],
     (5, 10, 4, 3, 2), 15, None, 14, 2),
]


def main():
    v, cram = S.load(ST); C = {}
    for i, cmd, pm, col, sa, w, h, x, y in S.cmds(v):
        if sa not in C: C[sa] = (w, h, x, y)
    allp = []; prev = []
    for name, sas, texts, ramp, ol_in, ol_out, shc, shd in GROUPS:
        X0 = min(C[s][2] for s in sas); Y0 = min(C[s][3] for s in sas)
        X1 = max(C[s][2] + C[s][0] for s in sas); Y1 = max(C[s][3] + C[s][1] for s in sas)
        cv = np.zeros((Y1 - Y0, X1 - X0), int); cover = np.zeros_like(cv, bool); tex = {}
        for s in sas:
            idx, lut, info, old = P.get(ST, s); w, h, x, y = C[s]; tex[s] = (idx, old, lut)
            sub = cv[y - Y0:y - Y0 + h, x - X0:x - X0 + w]; sub[idx > 0] = idx[idx > 0]; cover[y - Y0:y - Y0 + h, x - X0:x - X0 + w] = True
        rowc = []
        for j in range(cv.shape[0]):
            c = collections.Counter(int(t) for t in cv[j] if t not in (0, 15))
            rowc.append(c.most_common(1)[0][0] if c else None)
        new = np.zeros_like(cv); M = np.zeros_like(cv, bool)
        for (bx, by, bw, bh), text, font in texts:
            a = P.text_mask(text, font, bw - 6, bh - 6) >= 0.4
            M[by - Y0 + 2:by - Y0 + 2 + a.shape[0], bx - X0 + 2:bx - X0 + 2 + a.shape[1]] |= a
        def grow(m, r):
            p = np.pad(m, r); o = np.zeros_like(m)
            for dy in range(2 * r + 1):
                for dx in range(2 * r + 1): o |= p[dy:dy + m.shape[0], dx:dx + m.shape[1]]
            return o
        G1 = grow(M, 1); G2 = grow(M, 2) if ol_out is not None else G1
        sh = np.zeros_like(G2); sh[shd:, shd:] = G2[:-shd, :-shd]
        new[sh & ~G2] = shc
        if ol_out is not None: new[G2 & ~G1] = ol_out
        new[G1 & ~M] = ol_in
        ys = np.nonzero(M.any(1))[0]
        for j in ys:
            r = (j - ys.min()) / max(1, ys.max() - ys.min())
            new[j][M[j]] = ramp[min(len(ramp) - 1, int(r * len(ramp)))]
        if (new > 0)[~cover].any(): raise SystemExit('⛔ %s: 스프라이트 칸 밖으로 넘침' % name)
        for s in sas:
            idx, old, lut = tex[s]; w, h, x, y = C[s]
            nt = new[y - Y0:y - Y0 + h, x - X0:x - X0 + w]
            allp += P.patches(old, P.encode(nt))
        lut = tex[sas[0]][2]
        A = lut[cv].copy(); A[cv == 0] = 30; B = lut[new].copy(); B[new == 0] = 30
        prev.append(np.hstack([A, np.full((A.shape[0], 4, 3), 255, np.uint8), B]))
        print(name, '패치 %d' % len(allp))
    json.dump({'what': '타이틀 로고', 'patches': allp}, open(os.path.join(P.ROOT, 'work', 'gfx', 'title.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    W = max(p.shape[1] for p in prev)
    img = np.vstack([np.pad(p, ((0, 4), (0, W - p.shape[1]), (0, 0)), constant_values=90) for p in prev])
    Image.fromarray(img).resize((img.shape[1] * 3, img.shape[0] * 3), Image.NEAREST).save(os.path.join(P.ROOT, 'work', 'preview', 'gfx_title_원본_새것.png'))


if __name__ == '__main__':
    main()
