# -*- coding: utf-8 -*-
"""SDP 묶음 = 머리 0x800(BE32 오프셋, BE32 크기) 쌍 256개 + 섹터 정렬 조각. 빈 칸 = (0x800, 0).  (2026-11-19 조사 가설 — 로더 미확인)"""
import struct
def entries(b):
    out = []
    for i in range(256):
        o, s = struct.unpack_from('>II', b, i * 8)
        if s: out.append((i, o, s))
    return out
