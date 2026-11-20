# -*- coding: utf-8 -*-
"""오프닝 문구(C_ALL#2 7.2) 한글화 — 줄(프레임)마다 한글 한 줄 그림을 만들어 원래 항목 수만큼 8px 단위로 잘라 새 텍스처에 담음.
  영문 줄(17)·텍스처는 그대로, 블록 크기 불변. 글자 높이 13(공간 19,712 B 안).  산출 work/gfx/opening.json · preview"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import opening as O, spredit as P

FONT = 'C:/claude/utils/font/nanum-myeongjo/NanumMyeongjoExtraBold.ttf'
H = 13
KO = {1: '때는 텐메이 8년.', 2: '토쿠가와 막부의 태평성대.', 3: '참된 무사도는', 4: '잊혀 가고 있었다.',
      5: '그 역사의 그늘에서', 6: '이형의 것들이 꿈틀대기 시작한다…', 7: '마계로부터의 침략에', 8: '맞서는 자들이 있다.',
      9: '그 혼은 강하고 굳세게', 10: '굳이 수라의 길에 도전하려', 11: '하고 있었다…', 12: '사람들은 그들을',
      13: '「사무라이」라 불렀다…', 14: '오로지 자신의 길을 가는', 15: '그 삶의 방식을', 16: '「사무라이 스피리츠」라 부른다!', 18: '제작'}
RAMP = (2, 3, 4, 5, 6)


def line_img(text):
    a = P.text_mask(text, FONT, 400, H)
    m = a >= 0.3; xs = np.nonzero(m.any(0))[0]; a = a[:, xs.min():xs.max() + 1]
    out = np.zeros((H, a.shape[1]), int)
    for j in range(H):
        for i in range(a.shape[1]):
            v = a[j, i]
            if v >= 0.3: out[j, i] = RAMP[min(len(RAMP) - 1, int((v - 0.3) / 0.7 * len(RAMP)))]
    return out


def main():
    """줄마다 한 텍스처(번호 새로, 겹침 없음) + 나머지 항목은 공용 빈 텍스처. 영문 줄(17)·0x814 프레임의 텍스처 자리·번호 보존.
    (2026-11-19 실기: 위치만 바꾸고 번호를 그대로 두면 게임이 같은 번호 첫 위치를 써서 줄이 섞였음)"""
    b, hi = O.block(); b = bytearray(b); tex0, ntex, F = O.frames(bytes(b))
    space = len(b) - tex0; frame_offs = struct.unpack_from('>%dI' % len(F), b, 12)
    n814 = struct.unpack_from('>H', b, 0x814)[0]; ex = [struct.unpack_from('>HHhhHHHH', b, 0x818 + 16 * k) for k in range(n814)]
    keep = F[17] + ex
    used = sorted({(e[0] * 32, e[0] * 32 + (e[4] * e[5] // 2 + 31) // 32 * 32) for e in keep})
    tn_used = {e[1] for e in keep}; tn_free = iter([t for t in range(0, 161) if t not in tn_used])
    cur = 0
    def alloc(n):
        nonlocal cur
        n = (n + 31) // 32 * 32
        while True:
            hit = [k for k in used if not (cur + n <= k[0] or cur >= k[1])]
            if not hit: break
            cur = max(k[1] for k in hit)
        if cur + n > space: raise SystemExit('⛔ 텍스처 공간 부족')
        a = cur; cur += n; return a
    blank_off = alloc(32); blank_tn = next(tn_free); b[tex0 + blank_off:tex0 + blank_off + 32] = bytes(32)
    width_total = 0
    for fi, text in KO.items():
        es = F[fi]; img = line_img(text); W = (img.shape[1] + 7) // 8 * 8; width_total += W
        img = np.pad(img, ((0, 0), (0, W - img.shape[1])))
        x0 = min(e[2] for e in es); y0 = min(e[3] for e in es)
        if fi == 18: x0 = -W // 2
        off = alloc(W * H // 2); tn = next(tn_free)
        b[tex0 + off:tex0 + off + W * H // 2] = P.encode(img)
        for k, e in enumerate(es):
            to, tn0, x, y, ww, hh, pm, col = e
            if k == 0: struct.pack_into('>HHhhHHHH', b, frame_offs[fi] + 4, off // 32, tn, x0, y0 + 1, W, H, pm, col)
            else: struct.pack_into('>HHhhHHHH', b, frame_offs[fi] + 4 + 16 * k, blank_off // 32, blank_tn, x0, y0 + 1, 8, 1, pm, col)
    # 번호를 «등장 순서대로 0부터 빈틈 없이» 다시 매김(원본 규칙: 번호순으로 첫 항목 폭×높이만큼 VRAM 0x7A7E0 아래로 쌓음 — 오프닝.state 95개 전부 일치)
    a = 0x5c; ren = {}
    while a < tex0:
        n = struct.unpack_from('>H', b, a)[0]
        for k in range(n):
            p = a + 4 + 16 * k; tn = struct.unpack_from('>H', b, p + 2)[0]
            new_tn = tn not in ren
            ren.setdefault(tn, len(ren)); struct.pack_into('>H', b, p + 2, ren[tn])
            col = struct.unpack_from('>H', b, p + 14)[0]          # 0x400 = 이미 올린 텍스처 재사용(안 올림) — 원본 137항목 전부 «첫 등장만 0»
            struct.pack_into('>H', b, p + 14, (col & ~0x400) if new_tn else (col | 0x400))
        a += 4 + 16 * n
    nb = bytes(b)
    # 검산: 다시 풀어 그림
    t0, nt, F2 = O.frames(nb); rows = []
    for fi in sorted(KO):
        c = np.zeros((20, 260), int)
        for e in F2[fi]:
            t = O.texture(nb, t0, e); x = e[2] + 120
            c[e[3] + 18:e[3] + 18 + t.shape[0], x:x + t.shape[1]] = np.maximum(c[e[3] + 18:e[3] + 18 + t.shape[0], x:x + t.shape[1]], t)
        rows.append(c)
    img = np.vstack(rows) * 40
    Image.fromarray(img.astype(np.uint8)).resize((520, img.shape[0] * 2), Image.NEAREST).save(os.path.join(O.ROOT, 'work', 'preview', 'gfx_opening_새것.png'))
    old, _ = O.block()
    patches = P.patches(old, nb)
    json.dump({'what': '오프닝 문구', 'ko': KO, 'patches': patches}, open(os.path.join(O.ROOT, 'work', 'gfx', 'opening.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print('줄 폭 합 %d px · 사용 %d / %d B · 사본 %d' % (width_total, cur, space, len(patches)))


if __name__ == '__main__':
    main()
