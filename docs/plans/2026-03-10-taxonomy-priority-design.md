# Taxonomy 기반 뉴스 우선순위 설계

## 배경
- 기존 선별 로직은 `technical/general` 2분법과 소스별 `priority_boost`를 조합해 점수를 계산했다.
- 이 방식은 구현형 기술 글에는 잘 맞지만, GeekNews의 전략/인사이트형 글이나 산업/비즈니스형 글을 안정적으로 평가하기 어렵다.
- 특히 GeekNews는 실무 기술, 도구/에이전트, 전략/인사이트가 섞여 나오므로 단순 `tech_hits` 기준만으로는 고가치 글을 놓칠 수 있다.

## 목표
- 모든 소스에 공용으로 적용되는 `4슬롯 taxonomy`를 도입한다.
- GeekNews는 공용 taxonomy 위에 source-specific overlay를 얹는다.
- GeekNews만 개수 규칙을 별도로 가져가고, 나머지 소스는 같은 공식으로 평가한다.
- taxonomy를 코드 상수에서 분리해 자주 업데이트 가능한 구조로 만든다.

## 비목표
- LLM 기반 분류기를 이번 범위에 도입하지 않는다.
- Discord 메시지 포맷 자체를 taxonomy 라벨 중심으로 바꾸지 않는다.
- 개별 소스마다 완전히 다른 분류 공식을 만들지 않는다.

## 공용 4슬롯
1. `practical_tech`
   - 구현, 성능, 인프라, 아키텍처, 언어, 데이터, 보안
2. `tools_agents`
   - AI coding tool, IDE, CLI, agent workflow, sandbox, automation
3. `strategy_insight`
   - AI 시대의 일하는 방식, 코드 리뷰, 판단, 학습, 적응
4. `industry_business`
   - 출시, 투자, 실적, 규제, 파트너십, 시장/기업 변화

## 점수 구조
- 슬롯별 점수 계산:
  - `strong_terms`
  - `support_terms`
  - `negative_terms`
  - `phrase_rules`
  - `domain_hints`
- 기본식:
  - `slot_score = strong*5 + support*2 - negative*4 + phrase*6 + domain*3 + source_slot_boost`
- 최종 점수:
  - `final_score = source_boost + max_slot_score`
  - 모든 슬롯 신호가 약하면 `no_signal_penalty`를 적용한다.
- 대표 슬롯:
  - 가장 높은 `slot_score`를 가진 슬롯
  - 동점이면 taxonomy 순서 기준
  - 여전히 신호가 없으면 source default slot 사용

## GeekNews overlay
- GeekNews는 공용 taxonomy 위에 추가 신호를 올린다.
- 강화 슬롯:
  - `tools_agents`
  - `strategy_insight`
- 이유:
  - GeekNews는 AI coding / workflow / playbook / MCP 계열 글이 자주 나온다.
  - 동시에 `다가올 10년`, `Minimum Lovable Product`, `AI 시대 코드 리뷰` 같은 인사이트형 글이 중요하다.

## 선택 규칙
- 공용 공식은 전 소스 동일
- GeekNews만 개수 cap 별도
  - 환경변수 기본 `GEEKNEWS_MAX_PER_RUN=3`
  - 실제 배치가 5개 이하이면 최대 2개
  - 실제 배치가 6~7개면 최대 3개
- GeekNews 내부 선발은 슬롯 다양성을 우선한다.
- 비-GeekNews는 기존 `technical_quota`를 유지하되, taxonomy 기준으로 `practical_tech + tools_agents`를 technical bucket으로 본다.

## 확장성
- taxonomy 정의 파일:
  - `config/taxonomy.yaml`
- 회귀 검증용 예시셋:
  - `config/taxonomy_examples.yaml`
- 런타임 로그:
  - `primary_slot`
  - `slot_scores`
  - `slot_matches`
  - `matched_terms`
- taxonomy는 주기적으로 업데이트한다.
  - 신규 표현 추가
  - 과매칭 term 제거
  - slot overlay 조정

## Multi-Agent Review
### Skeptic / Challenger
- objection: 슬롯 경계가 애매하고 drift가 생길 수 있다.
- resolution: multi-slot scoring 후 대표 슬롯 1개만 부여하고, example set으로 회귀 점검한다.

### Constraint Guardian
- objection: 로직이 비대해지면 유지보수 비용이 커진다.
- resolution: 공용 taxonomy + source overlay만 허용하고, LLM 분류기는 제외한다.

### User Advocate
- objection: 사용자는 분류 자체보다 결과 품질을 체감한다.
- resolution: 라벨 노출보다 selection diversity와 explainable logging을 우선한다.

### Integrator / Arbiter
- disposition: `APPROVED`
- rationale:
  - GeekNews 고유 패턴을 살리면서도 전 소스 일관성을 확보한다.
  - taxonomy를 파일로 분리해 지속 업데이트 요구를 수용한다.
  - 범위가 과도하게 커지지 않는다.

## Decision Log
- 결정: `technical/general` 2분법을 공용 4슬롯 taxonomy로 대체
- 결정: GeekNews는 공용 taxonomy + overlay + 개수 cap
- 대안: cap만 상향, GeekNews 전용만 개선, LLM 분류기
- 기각 이유:
  - cap 상향만으로는 다각화가 안 됨
  - GeekNews만 정교하면 전체 일관성이 무너짐
  - LLM 분류기는 지금 단계에서 운영 복잡도가 높음
