# -*- coding: utf-8 -*-
"""SDP 조각 머리(가설): BE32 항목 수 N(첫 바이트=N?) 다음 12 B 항목 [u16 종류, u16 번호, u32 오프셋, u32 크기].
   종류 0x000A = 대사 블록: u16 개수 + u16 오프셋[개수](블록 기준) + 문자열(BE16 코드, 0000 끝)."""
import struct
def header(p):
    n = p[0]
    if n == 0 or 4 + n * 12 > len(p): return None
    out = []
    for i in range(n):
        t, sub, o, s = struct.unpack_from('>HHII', p, 4 + i * 12)
        if (t, sub, o, s) == (0, 0, 0, 0): continue          # 빈 항목
        if o + s > len(p) or o < 4 + n * 12: return None
        out.append((t, sub, o, s))
    return out
def text_block(b):
    cnt, = struct.unpack_from('>H', b, 0)
    offs = list(struct.unpack_from('>%dH' % cnt, b, 2))
    return cnt, offs


def strings(b):
    """블록 → [(표 번호, 오프셋, BE16 단어열(0000 제외))]. 문자열 = 포인터 위치부터 첫 0000 까지(중간 진입 허용)."""
    cnt, offs = text_block(b)
    out = []
    for i, x in enumerate(offs):
        if not x: continue
        j = x
        while j + 1 < len(b) and b[j:j + 2] != b'\0\0': j += 2
        out.append((i, x, struct.unpack('>%dH' % ((j - x) // 2), b[x:j])))
    return out
