# Policy Pages For AdSense Readiness Design

## Goal
- AdSense 도입 전에 사이트의 브리핑/큐레이션 성격을 더 명확히 보여준다.
- 목록/상세 하단에서 정책 페이지로 쉽게 이동할 수 있게 만든다.

## Decision
- 정책 페이지 4개를 추가한다:
  - `About`
  - `Editorial Policy`
  - `Privacy`
  - `Contact`
- 목록 페이지와 상세 페이지 하단에 공통 footer를 추가한다.
- 목록 페이지 상단 설명에 브리핑/원문 링크 중심 사이트라는 문구를 보강한다.
- 상세 페이지의 기존 "원문을 대체하지 않는 브리핑" 문구는 유지한다.

## Why This Scope
- 정책 페이지만 추가하면 존재는 보이지만 사용자가 실제로 찾기 어렵다.
- 상단 내비게이션에 정책 링크를 올리면 현재 레이아웃이 산만해진다.
- 하단 footer는 콘텐츠 흐름을 방해하지 않으면서 신뢰 정보 접근성을 높인다.

## Content Principles
- 각 정책 페이지는 짧고 직접적으로 쓴다.
- 원문 미러링을 하지 않는다는 점을 명확히 적는다.
- 연락 수단은 GitHub Issues 링크를 사용한다.
- Privacy 문구에는 AdSense 도입 시 쿠키/광고 개인화 가능성을 고지한다.

## Files
- `site/index.html`
- `site/templates/detail.html`
- `site/styles.css`
- `site/detail.css`
- `site/about.html`
- `site/editorial-policy.html`
- `site/privacy.html`
- `site/contact.html`
- `tests/test_build_archive_site.py`
