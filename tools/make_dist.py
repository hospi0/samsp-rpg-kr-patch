# -*- coding: utf-8 -*-
r"""진설 사무라이 스피리츠 무사도열전 배포 묶음 — dist/SamSpBushidou_KR_<VER>/ : 트랙 1·2 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat(CP949)
  (대모험 tools/make_dist.py 를 옮김, 2026-11-21) 바뀌는 트랙: 트랙 1(데이터)·트랙 2(트랙 1 이 커져 뒤로 밀림). 트랙 3~6·cue 그대로
  검증: 원본 → xdelta 적용 → md5 = 빌드 md5 (트랙마다)
  python tools/make_dist.py   (먼저 python tools/build.py)"""
import hashlib, os, shutil, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

VER = 'v0.9'
XDELTA = r'C:\claude\utils\xdelta.exe'
ROM = 'Shinsetsu Samurai Spirits - Bushidou Retsuden (Japan)'
SRC = os.path.join('C:' + os.sep, 'claude', 'roms', 'ss', ROM)
OUT = os.path.join(ROOT, 'work', 'build', 'full')
NAME = 'SamSpBushidou_KR_' + VER
TITLE = '진설 사무라이 스피리츠 무사도열전 (세가 새턴 일본판) 한글 패치 ' + VER
TRACKS = (1, 2)


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


README = """{title}
{line}

6개의 트랙으로 이루어진 {rom} 의
트랙 1번과 2번에 패치하시면 됩니다. 트랙 3~6 과 cue 는 원본 그대로 씁니다.

{md5s}

[ 적용 방법 ]

  1) 원본 트랙 1·2 파일을 이 폴더에 복사
       "{bin1}"
       "{bin2}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일 2개가 만들어집니다
  3) 만든 파일 이름을 원본 트랙 1·2 이름으로 바꿔 넣고, 트랙 3~6 과 cue 는 원본 그대로 쓰세요

  직접 적용:
    xdelta.exe -d -s "원본 트랙 1" "{p1}" "결과 트랙 1"
    xdelta.exe -d -s "원본 트랙 2" "{p2}" "결과 트랙 2"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

  - 대사 전체, 메뉴·전투·상점 문구, 아이템·기술·인물·지명, 세이브 화면 장소 이름
  - 그림 글자: 타이틀, 캐릭터·시나리오 선택, 오프닝, 전투 아이콘·팝업, 로딩 화면 등
  - 건물에 드나들 때 뜨던 예/아니오 확인 창을 없앴습니다(바로 출입)


[ 알려진 점 ]

  - 시험판입니다. 전체 플레이 검증을 마치지 않았습니다.
  - 원본 게임으로 저장한 기록은 세이브 화면 장소 이름이 깨져 보입니다. 새로 저장하면 바뀝니다.
  - 엔딩 제작진 명단은 원본 그대로입니다.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin1}" (
  echo   [오류] 원본 트랙 1 파일을 이 폴더에 넣어 주세요 - readme 참고.
  pause & exit /b 1
)
if not exist "%~dp0{bin2}" (
  echo   [오류] 원본 트랙 2 파일을 이 폴더에 넣어 주세요 - readme 참고.
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin1}" "%~dp0{p1}" "%~dp0{k1}"
if errorlevel 1 (
  echo   [오류] 트랙 1 패치 실패 - 원본이 다를 수 있습니다 - readme 의 원본md5 확인.
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin2}" "%~dp0{p2}" "%~dp0{k2}"
if errorlevel 1 (
  echo   [오류] 트랙 2 패치 실패 - 원본이 다를 수 있습니다 - readme 의 원본md5 확인.
  pause & exit /b 1
)
echo   완료: "{k1}"
echo   완료: "{k2}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    names = {}; lines = []
    for n in TRACKS:
        b = '%s (Track %d).bin' % (ROM, n)
        src, out = os.path.join(SRC, b), os.path.join(OUT, b)
        patch = '%s_Track%d.xdelta' % (NAME, n); pp = os.path.join(d, patch)
        subprocess.run([XDELTA, '-e', '-9', '-B', '536870912', '-f', '-s', src, out, pp], check=True)
        chk = os.path.join(d, '_check.bin')
        subprocess.run([XDELTA, '-d', '-f', '-s', src, pp, chk], check=True)
        o, want, got = md5(src), md5(out), md5(chk)
        os.remove(chk)
        assert got == want, ('패치 적용 결과가 빌드와 다름', n, got, want)
        print('트랙 %d 원본md5 %s → 패치md5 %s · %s %d B' % (n, o, want, patch, os.path.getsize(pp)))
        names['bin%d' % n] = b; names['p%d' % n] = patch; names['k%d' % n] = '%s (Track %d) [KR].bin' % (ROM, n)
        lines.append('트랙 %d  원본md5 : %s\n        패치md5 : %s\n' % (n, o, want))
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = README.format(title=TITLE, line='=' * 60, rom=ROM, md5s='\n'.join(lines), **names)
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(BAT.format(**names).replace('\n', '\r\n').encode('cp949'))
    z = os.path.join(ROOT, 'dist', NAME + '.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(d)):
            zf.write(os.path.join(d, f), NAME + '/' + f)
    print('✅', d)
    for f in sorted(os.listdir(d)):
        print('  %-64s %12d' % (f, os.path.getsize(os.path.join(d, f))))
    print('  zip %s %d B · md5 %s' % (os.path.basename(z), os.path.getsize(z), md5(z)))


if __name__ == '__main__':
    main()
