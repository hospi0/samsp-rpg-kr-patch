# -*- coding: utf-8 -*-
"""스테이트 → work/mem/<이름>/ (vdp2render.py 형식): VDP2_VRAM(BE) · VDP2_REGS(u16 BE) · CRAM(원래 LE 그대로, 렌더러가 뒤집음)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rzip, mdfnstate as M
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for st in sys.argv[1:]:
    d = rzip.unpack(os.path.join(ROOT, 'work', 'states_user', st + '.state'))[0]; S = M.sections(d)
    D = os.path.join(ROOT, 'work', 'mem', st); os.makedirs(D, exist_ok=True)
    open(os.path.join(D, 'VDP2_VRAM.bin'), 'wb').write(M.swap16(S['VDP2']['VRAM']))
    open(os.path.join(D, 'VDP2_REGS.bin'), 'wb').write(M.swap16(S['VDP2']['RawRegs']))
    open(os.path.join(D, 'CRAM.bin'), 'wb').write(S['VDP2']['CRAM'])
    print(st)
