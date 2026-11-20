# -*- coding: utf-8 -*-
"""하스피 그림 가져오기 → 게임 팔레트 최근접색(알파<128 = 투명 0) → layout 칸대로 잘라 스프라이트 패치.
  python tools/import_gfx.py <이름(layout.json 키)> <그림.png> [...]   → work/gfx/user_<이름>.json · work/preview/user_<이름>_받은_변환.png
  같은 그림의 임시 패치(gfx/title.json·logos.json)는 해당 스프라이트 항목을 빼서 겹치지 않게 함."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import spredit as P

EX = os.path.join(P.ROOT, 'work', 'export_gfx')


def run(name, path):
    L = json.load(open(os.path.join(EX, 'layout.json'), encoding='utf8'))[name]
    o = Image.open(os.path.join(EX, name + '_원본.png')); pal = np.array(o.getpalette()[:48]).reshape(16, 3)
    im = np.asarray(Image.open(path).convert('RGBA')).astype(int)
    if im.shape[:2] != (o.size[1], o.size[0]): raise SystemExit('⛔ 크기 %s ≠ 원본 %s' % (im.shape[:2], o.size[::-1]))
    rgb = im[..., :3]; d = ((rgb[..., None, :] - pal[None, None, 1:, :]) ** 2).sum(-1)
    idx = d.argmin(-1) + 1; idx[im[..., 3] < 128] = 0
    cover = np.zeros(idx.shape, bool); allp = []; used = set()
    for sa, x, y, w, h in L['sprites']:
        cover[y:y + h, x:x + w] = True
        _, _, _, old = P.get(L['state'], sa)
        new = idx[y:y + h, x:x + w]
        allp += P.patches(old, P.encode(new)); used.add(old.hex())
    lost = int(((idx > 0) & ~cover).sum())
    json.dump({'what': '하스피 그림 ' + name, 'src': path, 'patches': allp}, open(os.path.join(P.ROOT, 'work', 'gfx', 'user_%s.json' % name), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    for f in ('title.json', 'logos.json'):                       # 임시 패치에서 같은 스프라이트 빼기
        fp = os.path.join(P.ROOT, 'work', 'gfx', f)
        if not os.path.exists(fp): continue
        J = json.load(open(fp, encoding='utf8')); n0 = len(J['patches'])
        J['patches'] = [p for p in J['patches'] if p['old'] not in used]
        if len(J['patches']) != n0: json.dump(J, open(fp, 'w', encoding='utf8'), ensure_ascii=False, indent=0); print('  %s 에서 %d 항목 뺌' % (f, n0 - len(J['patches'])))
    a = rgb.astype(np.uint8).copy(); a[im[..., 3] < 128] = (255, 0, 255)
    b = pal[idx].astype(np.uint8); b[idx == 0] = (255, 0, 255); b[(idx > 0) & ~cover] = (0, 255, 0)
    c = np.hstack([a, np.full((a.shape[0], 3, 3), 255, np.uint8), b])
    Image.fromarray(c).resize((c.shape[1] * 4, c.shape[0] * 4), Image.NEAREST).save(os.path.join(P.ROOT, 'work', 'preview', 'user_%s_받은_변환.png' % name))
    print(name, '패치 %d · 칸 밖(초록, 안 보임) %d 화소' % (len(allp), lost))


if __name__ == '__main__':
    a = sys.argv[1:]
    for k in range(0, len(a), 2): run(a[k], a[k + 1])
