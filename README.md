# AI 테스트케이스 생성기

AI를 활용한 간단한 테스트케이스 생성 도구입니다.

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# Poetry를 사용하여 가상환경 설정
python -m poetry install

# 가상환경 활성화
python -m poetry shell
```

### 2. 사용법

#### 📝 테스트케이스 아이디어 생성
```bash
# 기능 설명을 입력받아 테스트케이스 아이디어 생성
testgen generate-simple "로그인 기능"
```

#### 🧪 유닛테스트 파일 생성
```bash
# 함수명을 입력받아 유닛테스트 템플릿 생성
testgen generate-unittest -f "함수명" -o "출력파일명.py" -c 5
```

### 3. 예시

#### 간단한 아이디어 생성
```bash
python -m poetry run testgen generate-simple "사용자 인증"
```

#### 테스트케이스 파일 생성
```bash
python -m poetry run testgen generate-unittest -f "calculate_sum" -o "test_calculate_sum.py" -c 5
```

## 📋 주요 기능

- ✅ 간단한 CLI 인터페이스
- ✅ 테스트케이스 아이디어 자동 생성
- ✅ 유닛테스트 템플릿 생성
- ✅ Given-When-Then 패턴 적용
- ✅ 다양한 테스트 시나리오 (정상, 예외, 경계값 등)

## 🔧 개발 환경

- Python 3.11+
- Poetry (의존성 관리)
- Click (CLI 프레임워크)

## 📁 프로젝트 구조

```
ai_testcase_generator/
├── ai_testcase_generator/
│   ├── __init__.py
│   └── main.py          # CLI 메인 로직
├── pyproject.toml       # 프로젝트 설정
├── poetry.lock          # 의존성 락 파일
└── README.md           # 이 파일
```

## 🎯 앞으로의 개선점

- [ ] 실제 코드 파일 분석 기능
- [ ] 더 지능적인 테스트케이스 생성
- [ ] 다양한 테스트 프레임워크 지원 (pytest, etc.)
- [ ] 웹 인터페이스 추가
- [ ] AI 모델 통합 (OpenAI, 로컬 LLM 등)

## �� 라이선스

MIT License