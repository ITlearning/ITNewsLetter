# Vercel Production AdSense Readiness Design

## Goal
- Vercel에서 이 저장소가 production 도메인으로 안정적으로 서빙되게 만든다.
- AdSense 사이트 확인에 필요한 기본 크롤러 접근 파일을 루트에 함께 배포한다.

## Context
- 현재 저장소는 `scripts/build_archive_site.py`가 `site/`를 `dist/`로 복사한 뒤 정적 아카이브를 만든다.
- GitHub Pages 배포 설정은 있지만 Vercel 전용 설정 파일은 없다.
- `ads.txt`는 이미 있고 공개 배포에서도 응답했지만 `robots.txt`는 없다.
- Vercel preview URL은 `401`과 `x-robots-tag: noindex`로 응답해 AdSense 검증에 쓸 수 없다.

## Approaches

### Option 1: Dashboard-only configuration
- Vercel 대시보드에서 `Build Command`, `Install Command`, `Output Directory`를 수동 설정한다.
- 장점: 코드 변경이 거의 없다.
- 단점: 설정이 저장소에 남지 않아 재현성이 낮고 다른 프로젝트/팀원이 보기 어렵다.

### Option 2: Repository-managed Vercel configuration
- 루트에 `vercel.json`을 두고 Vercel 빌드/출력 경로를 코드로 고정한다.
- `site/robots.txt`를 추가해 `dist/` 루트에도 같이 배포되게 만든다.
- 장점: 설정이 저장소에 남고 재배포 시 일관적이다.
- 단점: 대시보드의 deployment protection 같은 외부 설정은 별도로 풀어야 한다.

### Option 3: Full migration to custom build output API
- `.vercel/output`을 직접 생성하는 식으로 Vercel용 산출물을 따로 만든다.
- 장점: Vercel 제어 범위가 넓다.
- 단점: 현재 정적 사이트엔 과하다.

## Decision
- Option 2를 선택한다.
- `vercel.json`으로 `framework`, `installCommand`, `buildCommand`, `outputDirectory`를 명시한다.
- `site/robots.txt`를 추가해 build output 루트에 `robots.txt`가 생기게 한다.
- 테스트는 `dist/robots.txt` 존재와 내용을 검증하도록 보강한다.

## Non-Goals
- Vercel dashboard의 deployment protection 해제까지 코드로 처리하지 않는다.
- 커스텀 도메인 연결이나 AdSense 콘솔 재심사 요청까지 자동화하지 않는다.
- 수동 광고 슬롯 추가는 이번 범위에 포함하지 않는다.

## Files
- `vercel.json`
- `site/robots.txt`
- `tests/test_build_archive_site.py`
