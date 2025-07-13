# Jira 연동 AI 테스트케이스 생성기

Jira 태스크를 기반으로 테스트케이스를 자동 생성하는 AI 도구입니다.

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 의존성 설치
python -m pip install streamlit atlassian-python-api

# 또는 Poetry 사용 (권장)
python -m poetry install
```

### 2. Jira 연동 설정

#### 방법 1: 설정파일 사용 (권장)
```bash
# 설정파일 생성
cp config.json.example config.json

# config.json 편집
{
  "jira": {
    "server_url": "https://your-domain.atlassian.net",
    "username": "your-email@example.com",
    "api_token": "your-api-token-here",
    "project_key": "PROJ"
  },
  "app": {
    "default_test_count": 5,
    "auto_connect": true,
    "theme": "light"
  }
}
```

#### 방법 2: 웹 UI에서 직접 입력
- 설정파일이 없는 경우 웹 UI에서 입력 가능
- "설정을 config.json에 저장" 체크박스로 자동 저장

### 3. 웹 애플리케이션 실행
```bash
# 간단한 방법
python run_app.py

# 또는 직접 실행
python -m streamlit run ai_testcase_generator/app.py
```

브라우저에서 `http://localhost:8501`에 접속하세요.

## 🔗 Jira 연동 설정

### Jira API 토큰 생성
1. Jira 계정으로 로그인
2. 계정 설정 → 보안 → API 토큰 생성
3. 생성된 토큰을 복사하여 설정파일에 입력

### 설정파일 구조
```json
{
  "jira": {
    "server_url": "https://your-domain.atlassian.net",
    "username": "your-email@example.com",
    "api_token": "your-api-token-here",
    "project_key": "PROJ"
  },
  "app": {
    "default_test_count": 5,
    "auto_connect": true,
    "theme": "light"
  }
}
```

### 보안 주의사항
- `config.json`은 `.gitignore`에 포함되어 Git에 커밋되지 않습니다
- API 토큰은 절대 공개하지 마세요
- 설정파일 권한을 적절히 제한하세요

## 📋 주요 기능

### 1. 🎯 Jira 태스크 기반 테스트케이스 아이디어 생성
- Jira 태스크 키 입력 (예: PROJ-123)
- 태스크 정보 자동 분석
- 인수 조건(AC) 자동 추출
- 이슈 타입별 맞춤 테스트케이스 생성

### 2. 🧪 Jira 연동 유닛테스트 템플릿 생성
- 함수명 + Jira 태스크 연동
- Given-When-Then 패턴 적용
- 추적 가능한 테스트 코드 생성
- 요구사항 연결성 확보

### 3. 📊 스마트 분석 기능
- 태스크 우선순위 기반 테스트 계획
- 이슈 타입별 테스트 시나리오 (Bug, Story, Feature 등)
- 버그 재현 및 회귀 테스트 자동 생성
- 사용자 스토리 기반 테스트케이스

### 4. ⚙️ 편의 기능
- 설정파일 기반 자동 연결
- 기본 테스트 개수 설정
- 설정 저장 및 불러오기
- 직관적인 웹 UI

## 🔧 지원 기능

### 이슈 타입별 테스트
- **Bug/Defect**: 버그 재현, 회귀 테스트
- **Story/Feature**: 사용자 시나리오, 비즈니스 로직 검증
- **Task**: 기능 동작 확인, 성능 테스트

### 자동 추출 정보
- 태스크 요약 및 설명
- 인수 조건 (Acceptance Criteria)
- 우선순위 및 상태
- 이슈 타입별 컨텍스트

## 📁 프로젝트 구조

```
ai_testcase_generator/
├── ai_testcase_generator/
│   ├── __init__.py
│   └── app.py               # Streamlit 웹 애플리케이션
├── config.json.example      # 설정파일 예시
├── config.json             # 실제 설정파일 (gitignore)
├── run_app.py              # 애플리케이션 런처
├── pyproject.toml          # 프로젝트 설정
├── .gitignore             # Git 제외 파일
└── README.md              # 이 파일
```

## 🛠️ 개발 환경

- Python 3.11+
- Streamlit (웹 UI)
- Atlassian Python API (Jira 연동)
- Poetry (의존성 관리)

## 📖 사용 예시

### 1. 설정파일 생성
```bash
cp config.json.example config.json
# config.json 편집 후 실행
```

### 2. 테스트케이스 아이디어 생성
1. 앱 실행 후 자동 연결 확인
2. 태스크 키 입력 (예: DEV-123)
3. 자동 생성된 테스트케이스 확인
4. 결과 다운로드

### 3. 유닛테스트 생성
1. Jira 태스크 키 입력
2. 함수명 입력
3. 테스트케이스 수 선택
4. 완성된 테스트 코드 다운로드

## 🎯 장점

- ✅ **추적 가능성**: Jira 태스크와 테스트케이스 연결
- ✅ **자동화**: 수동 작업 최소화
- ✅ **표준화**: 일관된 테스트케이스 형식
- ✅ **효율성**: 빠른 테스트 계획 수립
- ✅ **편의성**: 설정파일 기반 자동 연결
- ✅ **보안**: 민감 정보 로컬 관리
- ✅ **품질 향상**: 놓치기 쉬운 테스트 시나리오 자동 생성

## 🚨 문제 해결

### 연결 오류
- API 토큰 유효성 확인
- 서버 URL 정확성 확인
- 네트워크 연결 상태 확인

### 설정파일 오류
- `config.json.example` 파일 형식 참고
- JSON 문법 오류 확인
- 필수 필드 누락 확인

## 📄 라이선스

MIT License

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📞 문의

이슈가 있거나 개선사항이 있으시면 GitHub Issues를 이용해 주세요.