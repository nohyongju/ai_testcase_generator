@echo off
chcp 65001 >nul

echo 🚀 AI 테스트케이스 생성기 압축 파일을 생성합니다...

REM PowerShell을 사용하여 압축 파일 생성
powershell -Command "Compress-Archive -Path 'ai_testcase_generator', 'config.json.example', 'docker-compose.yml', '.dockerignore', 'Dockerfile', 'pyproject.toml', 'run_app.py', 'README.md' -DestinationPath 'ai-testcase-generator.zip' -Force"

if exist ai-testcase-generator.zip (
    echo ✅ 압축 파일이 성공적으로 생성되었습니다!
    echo 📁 파일 위치: %cd%\ai-testcase-generator.zip
    echo 📊 파일 크기:
    dir ai-testcase-generator.zip
) else (
    echo ❌ 압축 파일 생성에 실패했습니다.
)

pause 