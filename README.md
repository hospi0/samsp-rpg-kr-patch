# 진설 사무라이 스피리츠 무사도열전 (세가 새턴 일본판) 한글 패치

- 원본: `Shinsetsu Samurai Spirits - Bushidou Retsuden (Japan)` (6트랙, 트랙 1·2 에 패치, 트랙 3~6·cue 그대로)
- 배포 파일은 릴리즈의 zip(xdelta 2개 + 적용 bat + readme)을 쓰세요.
- 도구: `tools/extract.py`·`tools/extract_place.py`(추출) → `tools/review_fix.py`(번역 검수·자동 수정) → `tools/build.py`(대사·글꼴·그림·디스크) → `tools/make_dist.py`(배포 묶음)
- 번역 표: `my files/tsv/samsp_*.tsv`(대사 dlg · 실행 파일 exe · 세이브 장소 place), 수동 수정 `work/review/manual.tsv`, 용어 `work/glossary.tsv`
- 조사·결정 기록: `docs/00_초기조사.md`
