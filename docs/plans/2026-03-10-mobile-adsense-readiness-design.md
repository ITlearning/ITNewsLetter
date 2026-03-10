# Mobile And AdSense Readiness Design

## Goal
- 목록, 상세, 정책 페이지를 모바일 화면에서 더 안정적으로 보이게 만든다.
- 제공된 AdSense publisher ID로 사이트 전체에 Auto Ads/검증용 공통 스크립트를 넣고 `ads.txt`를 준비한다.

## Decision
- AdSense는 우선 Auto Ads 기준으로 연결한다.
- 수동 광고 슬롯은 나중에 별도로 붙인다.
- 모바일 대응은 목록/상세/정책 페이지 공통 요소를 중심으로 정리한다:
  - sticky 완화
  - 버튼/링크 폭 조정
  - 카드/메타/푸터 재배치
  - 좁은 화면에서 타이포와 간격 보정

## Why This Scope
- 사용자가 아직 slot ID를 주지 않았으므로 수동 ad unit까지 바로 고정하는 것은 이르다.
- Auto Ads는 제공된 `ca-pub` 스크립트만으로 검증과 초기 수익화 준비가 가능하다.
- 모바일 문제는 CSS 중심 수정으로 해결 가능하다.

## Files
- `site/index.html`
- `site/templates/detail.html`
- `site/about.html`
- `site/editorial-policy.html`
- `site/privacy.html`
- `site/contact.html`
- `site/styles.css`
- `site/detail.css`
- `site/ads.txt`
- `tests/test_build_archive_site.py`
