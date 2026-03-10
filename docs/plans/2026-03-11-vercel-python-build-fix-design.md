# Vercel Python Build Fix Design

## Goal
- Vercel production build가 Python 패키지 설치 단계에서 실패하지 않게 만든다.

## Problem
- 현재 `vercel.json`은 `python3 -m pip install -r requirements.txt`를 직접 실행한다.
- Vercel build 로그에서 Python 환경이 `externally managed`로 표시되며 PEP 668 에러로 설치가 중단된다.

## Options

### Option 1: `--break-system-packages` 추가
- 장점: 수정이 가장 작다.
- 단점: 관리형 Python 환경을 강제로 깨는 방식이라 보수적으로 좋지 않다.

### Option 2: repo-local virtualenv 사용
- 장점: 시스템 Python을 건드리지 않고 설치/빌드를 분리할 수 있다.
- 단점: 설치/빌드 명령을 둘 다 맞춰야 한다.

## Decision
- Option 2를 사용한다.
- `installCommand`는 `.vercel-venv`를 만들고 그 안에 의존성을 설치한다.
- `buildCommand`는 `.vercel-venv/bin/python`으로 `scripts/build_archive_site.py`를 실행한다.

## Files
- `vercel.json`
