# Jira 연동 AI 테스트케이스 생성기

Jira 태스크를 기반으로 테스트케이스를 자동 생성하는 AI 도구입니다.

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 의존성 설치
python -m pip install streamlit atlassian-python-api openai requests

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

## 🔗 연동 설정

### Jira API 토큰 생성
1. Jira 계정으로 로그인
2. 계정 설정 → 보안 → API 토큰 생성
3. 생성된 토큰을 복사하여 설정파일에 입력

### TestRail 인증 설정
1. TestRail 로그인 정보 사용
   - 사용자명: TestRail 로그인 이메일
   - 패스워드: TestRail 로그인 패스워드
2. Basic Authentication 방식 사용 (`username:password`)
3. API 키 대신 일반 패스워드 사용

### 설정파일 구조
```json
{
  "jira": {
    "server_url": "https://your-domain.atlassian.net",
    "username": "your-email@example.com",
    "api_token": "your-api-token-here",
    "project_key": "PROJ"
  },
  "openai": {
    "api_key": "your_openai_api_key_here",
    "model": "gpt-3.5-turbo",
    "max_tokens": 2000,
    "temperature": 0.7
  },
  "testrail": {
    "url": "https://your-domain.testrail.io",
    "username": "your_email@example.com",
    "password": "your_testrail_password_here",
    "default_project_id": 1,
    "default_section_id": 1
  },
  "app": {
    "default_test_count": 5,
    "auto_connect": true,
    "auto_connect_ai": true,
    "auto_connect_testrail": false,
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



### 3. 🧪 TestRail 연동 및 자동 등록
- TestRail 프로젝트/섹션 선택
- 전체 등록 또는 선택적 등록
- 실시간 등록 진행률 표시
- 테스트케이스 메타데이터 자동 설정

### 4. 📊 스마트 분석 기능
- 태스크 우선순위 기반 테스트 계획
- 이슈 타입별 테스트 시나리오 (Bug, Story, Feature 등)
- 버그 재현 및 회귀 테스트 자동 생성
- 사용자 스토리 기반 테스트케이스

### 5. ⚙️ 편의 기능
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

### 2. 테스트케이스 아이디어 생성 (6단계 플로우)
1. **태스크 입력**: Jira 태스크 키 입력 (예: DEV-123)
2. **태스크 정보 확인**: 가져온 태스크 정보 확인 및 수정
3. **생성 설정**: AI 모델 및 테스트케이스 생성 옵션 설정
4. **AI 생성 중**: AI가 테스트케이스를 생성하는 과정
5. **시나리오 확인**: 생성된 테스트케이스 확인 및 편집
6. **TestRail 등록**: TestRail 프로젝트/섹션 선택 후 테스트케이스 등록



## 🎯 장점

- ✅ **추적 가능성**: Jira 태스크와 테스트케이스 연결
- ✅ **자동화**: 수동 작업 최소화
- ✅ **표준화**: 일관된 테스트케이스 형식
- ✅ **효율성**: 빠른 테스트 계획 수립
- ✅ **편의성**: 설정파일 기반 자동 연결
- ✅ **보안**: 민감 정보 로컬 관리
- ✅ **품질 향상**: 놓치기 쉬운 테스트 시나리오 자동 생성
- ✅ **통합 관리**: TestRail 직접 연동으로 완전한 워크플로우 제공

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