# -*- coding: utf-8 -*-
"""하스피가 직접 그릴 그림 — 원본 화소·색 내보내기 → work/export_gfx/
  각 그림: <이름>_원본.png(원래 크기, 인덱스 PNG, 팔레트 16색 = 게임 색, 0번 투명) · <이름>_확대4배.png · <이름>_팔레트.png
  타이틀 로고는 스프라이트 덩어리를 화면 배치대로 합침(칸 위치 = layout.json, 다시 넣을 때 그 칸대로 자름 — 칸 밖은 못 그림, 칸_가림.png 참고)"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw
import sprites as S, spredit as P

OUT = os.path.join(P.ROOT, 'work', 'export_gfx')
LOGOS = [('하오마루', 0x72A20), ('갈포드', 0x72220), ('나코루루', 0x72620), ('겐쥬로', 0x71A60), ('우쿄', 0x71E40), ('참참', 0x71680)]
TITLE = [('타이틀_무사도열전', [0x7EC20, 0x7EA00, 0x7E7E0, 0x7E5C0, 0x7E3A0, 0x7DE80, 0x7D2C0]),
         ('타이틀_진설사무라이스피리츠', [0x7EE40, 0x7F5C0])]


def save(name, idx, lut, cover=None):
    pal = []
    for c in lut: pal += [int(x) for x in c]
    im = Image.fromarray(idx.astype(np.uint8), 'P'); im.putpalette(pal + [0] * (768 - len(pal)))
    im.save(os.path.join(OUT, name + '_원본.png'), transparency=0)
    rgb = lut[idx].copy(); rgb[idx == 0] = (255, 0, 255)
    if cover is not None: rgb[~cover] = (60, 60, 60)
    Image.fromarray(rgb).resize((idx.shape[1] * 4, idx.shape[0] * 4), Image.NEAREST).save(os.path.join(OUT, name + '_확대4배.png'))
    sw = Image.new('RGB', (16 * 40, 56), (255, 255, 255)); d = ImageDraw.Draw(sw)
    for i, c in enumerate(lut):
        d.rectangle([i * 40, 0, i * 40 + 38, 36], fill=tuple(int(x) for x in c) if i else (255, 0, 255)); d.text((i * 40 + 4, 40), str(i) if i else '0투명', fill=(0, 0, 0))
    sw.save(os.path.join(OUT, name + '_팔레트.png'))


def main():
    os.makedirs(OUT, exist_ok=True); layout = {}
    for st, sa in LOGOS:
        idx, lut, info, old = P.get(st, sa)
        save('이름로고_' + st, idx, lut); layout['이름로고_' + st] = {'state': st, 'sprites': [[sa, 0, 0, idx.shape[1], idx.shape[0]]]}
    v, cram = S.load('타이틀'); C = {}
    for i, cmd, pm, col, sa, w, h, x, y in S.cmds(v):
        if sa not in C: C[sa] = (w, h, x, y)
    for name, sas in TITLE:
        X0 = min(C[s][2] for s in sas); Y0 = min(C[s][3] for s in sas)
        X1 = max(C[s][2] + C[s][0] for s in sas); Y1 = max(C[s][3] + C[s][1] for s in sas)
        cv = np.zeros((Y1 - Y0, X1 - X0), int); cover = np.zeros_like(cv, bool); lut = None; rects = []
        for s in sas:
            idx, lut, info, old = P.get('타이틀', s); w, h, x, y = C[s]
            sub = cv[y - Y0:y - Y0 + h, x - X0:x - X0 + w]; sub[idx > 0] = idx[idx > 0]
            cover[y - Y0:y - Y0 + h, x - X0:x - X0 + w] = True; rects.append([s, x - X0, y - Y0, w, h])
        save(name, cv, lut, cover)
        layout[name] = {'state': '타이틀', 'origin': [X0, Y0], 'sprites': rects}
    json.dump(layout, open(os.path.join(OUT, 'layout.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    open(os.path.join(OUT, '읽어주세요.txt'), 'w', encoding='utf8').write(
        '이 폴더 = 하스피님이 직접 그릴 그림의 원본(2026-11-19).\n'
        '- *_원본.png: 원래 크기·게임 색 팔레트 16색 인덱스 PNG(0번 = 투명). 같은 크기로, 팔레트 안 색으로 그려 주세요(다른 색은 가장 가까운 색으로 바뀝니다).\n'
        '- *_확대4배.png: 보기용(분홍 = 투명, 회색 = 스프라이트 칸 밖 — 타이틀은 회색 자리에 그려도 화면에 안 나옵니다).\n'
        '- *_팔레트.png: 쓸 수 있는 색과 번호.\n'
        '- 타이틀 로고 두 덩어리는 화면 배치대로 합친 그림입니다(칸 위치 layout.json).\n')
    print(sorted(os.listdir(OUT)))


if __name__ == '__main__':
    main()
