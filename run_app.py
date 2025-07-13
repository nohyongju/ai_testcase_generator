#!/usr/bin/env python3
"""
Streamlit 앱 실행 스크립트
"""
import subprocess
import sys
import os

def main():
    # 현재 디렉토리 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(current_dir, "ai_testcase_generator", "app.py")
    
    # Streamlit 실행
    try:
        print("🚀 Jira 연동 AI 테스트케이스 생성기를 시작합니다...")
        print("📝 브라우저에서 http://localhost:8501 에 접속하세요")
        print("💡 종료하려면 Ctrl+C를 누르세요")
        
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", app_path,
            "--server.address", "0.0.0.0",
            "--server.port", "8501"
        ])
    except KeyboardInterrupt:
        print("\n👋 애플리케이션이 종료되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    main() 