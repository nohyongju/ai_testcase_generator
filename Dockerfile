# Python 3.11 베이스 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 생성 및 의존성 설치
COPY pyproject.toml ./
RUN pip install --upgrade pip

# 의존성 설치 (Poetry 대신 pip 사용)
RUN pip install streamlit atlassian-python-api openai requests click

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 8501

# 환경변수 설정
ENV PYTHONPATH=/app
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501

# 애플리케이션 실행
CMD ["python", "run_app.py"] 