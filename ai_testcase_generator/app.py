import streamlit as st
import json
import os
import time
from typing import List, Dict, Optional
from atlassian import Jira
import re
from openai import OpenAI


def load_config() -> Optional[Dict]:
    """설정파일을 로드합니다."""
    config_path = "config.json"
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        except Exception as e:
            st.error(f"설정파일 로드 실패: {str(e)}")
            return None
    return None


def save_config(config: Dict) -> bool:
    """설정파일을 저장합니다."""
    try:
        with open("config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"설정파일 저장 실패: {str(e)}")
        return False


def validate_jira_config(config: Dict) -> bool:
    """Jira 설정을 검증합니다."""
    jira_config = config.get('jira', {})
    required_fields = ['server_url', 'username', 'api_token']
    
    for field in required_fields:
        if not jira_config.get(field):
            return False
    
    return True


def connect_to_jira(server_url: str, username: str, api_token: str) -> Optional[Jira]:
    """Jira 서버에 연결을 시도합니다."""
    try:
        jira = Jira(
            url=server_url,
            username=username,
            password=api_token,
            cloud=True
        )
        # 연결 테스트
        jira.myself()
        return jira
    except Exception as e:
        st.error(f"Jira 연결 실패: {str(e)}")
        return None


def get_jira_task(jira: Jira, task_key: str) -> Optional[Dict]:
    """Jira 태스크 정보를 가져옵니다."""
    try:
        issue = jira.issue(task_key)
        return {
            'key': issue['key'],
            'summary': issue['fields']['summary'],
            'description': issue['fields']['description'] or '설명 없음',
            'status': issue['fields']['status']['name'],
            'priority': issue['fields']['priority']['name'] if issue['fields']['priority'] else 'Medium',
            'issue_type': issue['fields']['issuetype']['name'],
            'acceptance_criteria': extract_acceptance_criteria(issue['fields']['description'] or '')
        }
    except Exception as e:
        st.error(f"Jira 태스크 조회 실패: {str(e)}")
        return None


def extract_acceptance_criteria(description: str) -> str:
    """설명에서 인수 조건을 추출합니다."""
    # 인수 조건 패턴 찾기
    ac_patterns = [
        r'(?i)acceptance\s*criteria?[:\s]*(.*?)(?=\n\n|\Z)',
        r'(?i)ac[:\s]*(.*?)(?=\n\n|\Z)',
        r'(?i)테스트\s*조건[:\s]*(.*?)(?=\n\n|\Z)',
        r'(?i)검증\s*조건[:\s]*(.*?)(?=\n\n|\Z)'
    ]
    
    for pattern in ac_patterns:
        match = re.search(pattern, description, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    return ''


def setup_openai_client(api_key: str) -> OpenAI:
    """OpenAI 클라이언트를 설정합니다."""
    try:
        client = OpenAI(api_key=api_key)
        # 연결 테스트
        client.models.list()
        return client
    except Exception as e:
        st.error(f"OpenAI API 연결 실패: {str(e)}")
        return None


def generate_ai_testcases(client: OpenAI, jira_task: Dict, test_count: int = 5) -> List[Dict]:
    """AI를 사용하여 구조화된 테스트케이스를 생성합니다."""
    
    prompt = f"""
다음 Jira 태스크를 기반으로 상세한 테스트케이스 {test_count}개를 생성해주세요.

=== Jira 태스크 정보 ===
태스크 키: {jira_task['key']}
제목: {jira_task['summary']}
상태: {jira_task['status']}
우선순위: {jira_task['priority']}
이슈 타입: {jira_task['issue_type']}
설명: {jira_task['description']}

=== 테스트케이스 형식 요구사항 ===
각 테스트케이스는 다음 3가지 구성요소로 이루어져야 합니다:
1. Precondition (전제조건): 테스트 실행 전 준비되어야 할 조건들
2. Step (실행단계): 테스트를 위해 수행할 구체적인 단계들 (번호로 구분)
3. Expectation Result (기대결과): 테스트 성공 시 예상되는 결과

=== 응답 형식 ===
JSON 형태로 응답해주세요:
{{
  "testcases": [
    {{
      "title": "테스트케이스 제목",
      "precondition": "전제조건 설명",
      "steps": [
        "1. 첫 번째 실행 단계",
        "2. 두 번째 실행 단계",
        "3. 세 번째 실행 단계"
      ],
      "expectation": "기대되는 결과 설명"
    }}
  ]
}}

다양한 시나리오를 포함하여 {test_count}개의 테스트케이스를 생성해주세요:
- 정상 케이스
- 예외 상황
- 경계값 테스트
- 보안 및 권한 테스트
- 성능 테스트 등
"""
    
    try:
        # config.json에서 OpenAI 설정 로드
        config = load_config()
        openai_config = config.get('openai', {}) if config else {}
        
        response = client.chat.completions.create(
            model=openai_config.get('model', 'gpt-3.5-turbo'),
            messages=[
                {"role": "system", "content": "당신은 경험이 풍부한 QA 엔지니어입니다. 주어진 요구사항을 바탕으로 상세하고 실용적인 테스트케이스를 생성합니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=openai_config.get('max_tokens', 2000),
            temperature=openai_config.get('temperature', 0.7)
        )
        
        # JSON 응답 파싱
        content = response.choices[0].message.content
        
        # JSON 추출 (마크다운 코드 블록이 있을 경우 제거)
        import json
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            json_content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            json_content = content[json_start:json_end].strip()
        else:
            json_content = content.strip()
        
        result = json.loads(json_content)
        return result.get('testcases', [])
        
    except Exception as e:
        st.error(f"AI 테스트케이스 생성 실패: {str(e)}")
        return []


def fallback_generate_structured_testcases(jira_task: Dict, test_count: int = 5) -> List[Dict]:
    """AI 연결 실패 시 사용할 기본 구조화된 테스트케이스 생성"""
    
    task_key = jira_task['key']
    summary = jira_task['summary']
    issue_type = jira_task['issue_type'].lower()
    
    testcases = []
    
    # 기본 테스트케이스 템플릿들
    templates = [
        {
            "title": f"[{task_key}] {summary} - 정상 기능 동작 확인",
            "precondition": "• 시스템이 정상적으로 구동된 상태\n• 필요한 권한을 가진 사용자로 로그인\n• 테스트 데이터가 준비된 상태",
            "steps": [
                "1. 메인 화면에 접속한다",
                "2. 해당 기능 메뉴로 이동한다",
                "3. 정상적인 입력값을 입력한다",
                "4. 실행 버튼을 클릭한다"
            ],
            "expectation": "• 기능이 정상적으로 실행됨\n• 예상된 결과가 화면에 표시됨\n• 오류 메시지가 발생하지 않음"
        },
        {
            "title": f"[{task_key}] {summary} - 잘못된 입력 데이터 처리",
            "precondition": "• 시스템이 정상적으로 구동된 상태\n• 테스트용 잘못된 데이터가 준비된 상태",
            "steps": [
                "1. 해당 기능 화면에 접속한다",
                "2. 잘못된 형식의 데이터를 입력한다",
                "3. 실행 버튼을 클릭한다",
                "4. 표시되는 오류 메시지를 확인한다"
            ],
            "expectation": "• 적절한 오류 메시지가 표시됨\n• 시스템이 비정상 종료되지 않음\n• 사용자가 이해할 수 있는 안내가 제공됨"
        },
        {
            "title": f"[{task_key}] {summary} - 권한 및 보안 검증",
            "precondition": "• 권한이 없는 사용자 계정으로 로그인\n• 보안 테스트 환경이 구성된 상태",
            "steps": [
                "1. 권한이 없는 계정으로 로그인한다",
                "2. 해당 기능에 접근을 시도한다",
                "3. 접근 제한 메시지를 확인한다",
                "4. 우회 접근이 가능한지 확인한다"
            ],
            "expectation": "• 접근이 적절히 차단됨\n• 보안 로그가 기록됨\n• 우회 접근이 불가능함"
        }
    ]
    
    # 이슈 타입별 추가 테스트케이스
    if issue_type in ['bug', 'defect']:
        templates.append({
            "title": f"[{task_key}] {summary} - 버그 재현 및 수정 확인",
            "precondition": "• 버그가 발생했던 동일한 환경 구성\n• 재현 데이터 준비",
            "steps": [
                "1. 버그 발생 조건을 재현한다",
                "2. 이전과 동일한 단계를 수행한다",
                "3. 버그가 수정되었는지 확인한다",
                "4. 관련 기능들의 정상 동작을 확인한다"
            ],
            "expectation": "• 이전 버그가 더 이상 발생하지 않음\n• 관련 기능들이 정상 동작함\n• 새로운 부작용이 발생하지 않음"
        })
    elif issue_type in ['story', 'feature']:
        templates.append({
            "title": f"[{task_key}] {summary} - 사용자 시나리오 테스트",
            "precondition": "• 실제 사용자 환경과 유사한 설정\n• 다양한 사용자 프로필 준비",
            "steps": [
                "1. 실제 사용자 관점에서 기능에 접근한다",
                "2. 일반적인 사용 패턴을 따라 기능을 사용한다",
                "3. 다양한 시나리오로 기능을 테스트한다",
                "4. 사용자 경험을 종합적으로 평가한다"
            ],
            "expectation": "• 사용자가 직관적으로 기능을 사용할 수 있음\n• 예상된 비즈니스 가치가 달성됨\n• 사용자 만족도가 향상됨"
        })
    
    # 성능 테스트 추가
    templates.append({
        "title": f"[{task_key}] {summary} - 성능 및 응답시간 테스트",
        "precondition": "• 성능 측정 도구가 설치된 상태\n• 대용량 테스트 데이터 준비\n• 네트워크 환경이 안정된 상태",
        "steps": [
            "1. 성능 모니터링을 시작한다",
            "2. 기능을 여러 번 반복 실행한다",
            "3. 응답시간을 측정한다",
            "4. 시스템 리소스 사용량을 확인한다"
        ],
        "expectation": "• 응답시간이 요구사항 내에 있음\n• 시스템 리소스가 과도하게 사용되지 않음\n• 동시 사용자 환경에서도 안정적임"
    })
    
    # 요청된 개수만큼 반환
    return templates[:min(test_count, len(templates))]





def generate_unittest_template(function_name: str, test_count: int, jira_task: Optional[Dict] = None) -> str:
    """Jira 태스크 정보를 포함한 테스트케이스 템플릿을 생성합니다."""
    
    jira_info = ""
    if jira_task:
        jira_info = f"""
    Jira Task: {jira_task['key']} - {jira_task['summary']}
    Status: {jira_task['status']}
    Priority: {jira_task['priority']}
    Issue Type: {jira_task['issue_type']}
    """
    
    template = f"""import unittest
from unittest.mock import patch, MagicMock


class Test{function_name.capitalize()}(unittest.TestCase):
    \"\"\"
    {function_name} 함수를 위한 테스트케이스
    AI 테스트케이스 생성기로 생성됨
    {jira_info}
    \"\"\"
    
    def setUp(self):
        \"\"\"각 테스트 실행 전 설정\"\"\"
        pass
    
    def tearDown(self):
        \"\"\"각 테스트 실행 후 정리\"\"\"
        pass

"""
    
    test_templates = [
        "정상_기능_테스트",
        "예외_상황_테스트",
        "경계값_테스트", 
        "잘못된_입력_테스트",
        "성능_테스트",
        "보안_테스트",
        "UI_동작_테스트",
        "데이터_무결성_테스트"
    ]
    
    for i in range(min(test_count, len(test_templates))):
        template += f"""
    def test_{function_name}_{test_templates[i]}(self):
        \"\"\"
        {test_templates[i].replace('_', ' ')} 시나리오
        {'Based on Jira Task: ' + jira_task['key'] if jira_task else ''}
        TODO: 실제 테스트 로직 구현 필요
        \"\"\"
        # Given (준비)
        # 테스트 데이터 준비
        
        # When (실행)
        # result = {function_name}(test_input)
        
        # Then (검증)
        # self.assertEqual(result, expected)
        self.fail("테스트 로직을 구현하세요!")

"""
    
    template += """

if __name__ == '__main__':
    unittest.main()
"""
    
    return template


def render_jira_settings(config: Optional[Dict] = None) -> Dict:
    """Jira 설정 UI를 렌더링합니다."""
    
    # 설정파일에서 기본값 가져오기
    default_server_url = ""
    default_username = ""
    default_api_token = ""
    
    if config and 'jira' in config:
        jira_config = config['jira']
        default_server_url = jira_config.get('server_url', '')
        default_username = jira_config.get('username', '')
        default_api_token = jira_config.get('api_token', '')
    
    # UI 렌더링
    server_url = st.text_input("Jira 서버 URL", value=default_server_url, placeholder="https://your-domain.atlassian.net")
    username = st.text_input("사용자명/이메일", value=default_username, placeholder="user@example.com")
    api_token = st.text_input("API 토큰", value=default_api_token, type="password", placeholder="Your API Token")
    
    # 설정 저장 옵션
    save_config_option = st.checkbox("설정을 config.json에 저장", value=False)
    
    return {
        'server_url': server_url,
        'username': username,
        'api_token': api_token,
        'save_config': save_config_option
    }


def main():
    # 페이지 설정
    st.set_page_config(
        page_title="AI 테스트케이스 생성기",
        page_icon="🧪",
        layout="wide"
    )
    
    # 메인 헤더
    st.title("🧪 AI 테스트케이스 생성기 (Jira 연동)")
    st.markdown("---")
    
    # 설정파일 로드
    config = load_config()
    
    # Jira 연결 설정
    with st.sidebar:
        st.header("🔗 Jira 연결 설정")
        
        # 설정파일 상태 표시
        if config:
            st.success("✅ 설정파일(config.json) 로드됨")
            if validate_jira_config(config):
                st.success("✅ Jira 설정 검증 완료")
            else:
                st.warning("⚠️ Jira 설정 불완전 - 아래에서 수정하세요")
        else:
            st.info("💡 설정파일이 없습니다. 아래에서 입력하세요")
            st.markdown("📝 `config.json.example` 파일을 참고하여 `config.json`을 생성할 수 있습니다")
        
        # Jira 설정 UI
        jira_settings = render_jira_settings(config)
        
        # 연결 테스트 버튼
        if st.button("🔌 Jira 연결 테스트"):
            server_url = jira_settings['server_url']
            username = jira_settings['username']
            api_token = jira_settings['api_token']
            
            if server_url and username and api_token:
                jira = connect_to_jira(server_url, username, api_token)
                if jira:
                    st.success("✅ Jira 연결 성공!")
                    st.session_state.jira_connected = True
                    st.session_state.jira_client = jira
                    
                    # 설정 저장
                    if jira_settings['save_config']:
                        new_config = {
                            "jira": {
                                "server_url": server_url,
                                "username": username,
                                "api_token": api_token,
                                "project_key": "PROJ"
                            },
                            "app": {
                                "default_test_count": 5,
                                "auto_connect": True,
                                "theme": "light"
                            }
                        }
                        if save_config(new_config):
                            st.success("💾 설정이 config.json에 저장되었습니다!")
                else:
                    st.session_state.jira_connected = False
            else:
                st.warning("모든 필드를 입력해주세요.")
        
        # 자동 연결 (설정파일이 있고 유효한 경우)
        if config and validate_jira_config(config) and config.get('app', {}).get('auto_connect', False):
            if 'jira_connected' not in st.session_state:
                jira_config = config['jira']
                jira = connect_to_jira(
                    jira_config['server_url'],
                    jira_config['username'],
                    jira_config['api_token']
                )
                if jira:
                    st.session_state.jira_connected = True
                    st.session_state.jira_client = jira
                    st.success("🔄 Jira 자동 연결 성공!")
        
        # OpenAI API 설정
        st.header("🤖 AI 설정")
        
        # 설정파일에서 OpenAI 설정 로드
        openai_config = config.get('openai', {}) if config else {}
        
        # OpenAI 자동 연결 (설정파일에 키가 있고 auto_connect_ai가 True인 경우)
        if (config and openai_config.get('api_key') and 
            config.get('app', {}).get('auto_connect_ai', False) and 
            'openai_connected' not in st.session_state):
            
            client = setup_openai_client(openai_config['api_key'])
            if client:
                st.session_state.openai_connected = True
                st.session_state.openai_client = client
                st.success("🔄 AI 자동 연결 성공!")
            else:
                st.session_state.openai_connected = False
        
        # OpenAI API 키 입력 (읽기 전용으로 표시)
        if openai_config.get('api_key'):
            masked_key = openai_config['api_key'][:10] + "..." + openai_config['api_key'][-10:]
            st.text_input(
                "OpenAI API 키 (config.json에서 로드됨):",
                value=masked_key,
                disabled=True,
                help="config.json 파일에 설정된 API 키가 자동으로 로드됩니다"
            )
        else:
            openai_api_key = st.text_input(
                "OpenAI API 키:",
                type="password",
                placeholder="sk-...",
                help="테스트케이스 생성을 위한 OpenAI API 키를 입력하세요"
            )
            
            if st.button("🔌 AI 연결 테스트"):
                if openai_api_key:
                    client = setup_openai_client(openai_api_key)
                    if client:
                        st.success("✅ OpenAI API 연결 성공!")
                        st.session_state.openai_connected = True
                        st.session_state.openai_client = client
                    else:
                        st.session_state.openai_connected = False
                else:
                    st.warning("OpenAI API 키를 입력해주세요.")
        
        # AI 연결 상태 표시
        if hasattr(st.session_state, 'openai_connected') and st.session_state.openai_connected:
            st.success("🤖 AI: 연결됨")
            if openai_config.get('model'):
                st.caption(f"모델: {openai_config['model']}")
        else:
            st.info("🤖 AI: 미연결")
    
    # 도구 선택
    st.sidebar.header("🛠️ 도구 선택")
    tool_choice = st.sidebar.selectbox(
        "생성 도구를 선택하세요:",
        ["AI 기반 구조화된 테스트케이스 생성", "Jira 태스크 기반 유닛테스트 템플릿 생성"]
    )
    
    # 기본 테스트 개수 설정
    default_test_count = 5
    if config and 'app' in config:
        default_test_count = config['app'].get('default_test_count', 5)
    
    # 메인 컨텐츠
    if tool_choice == "AI 기반 구조화된 테스트케이스 생성":
        st.header("🤖 AI 기반 구조화된 테스트케이스 생성")
        
        # 진행 단계 초기화
        if 'current_step' not in st.session_state:
            st.session_state.current_step = 1
        
        # 진행 바 표시
        progress_steps = ["태스크 입력", "태스크 정보 확인", "생성 설정", "AI 생성 중", "결과 확인"]
        
        # 진행률 계산
        progress = (st.session_state.current_step - 1) / (len(progress_steps) - 1)
        st.progress(progress)
        
        # 현재 단계 표시
        col1, col2, col3, col4, col5 = st.columns(5)
        for i, step_name in enumerate(progress_steps, 1):
            with [col1, col2, col3, col4, col5][i-1]:
                if i == st.session_state.current_step:
                    st.markdown(f"**🔵 {i}. {step_name}**")
                elif i < st.session_state.current_step:
                    st.markdown(f"✅ {i}. {step_name}")
                else:
                    st.markdown(f"⚪ {i}. {step_name}")
        
        st.markdown("---")
        
        # 연결 상태 체크 (자동)
        jira_connected = hasattr(st.session_state, 'jira_connected') and st.session_state.jira_connected
        ai_connected = hasattr(st.session_state, 'openai_connected') and st.session_state.openai_connected
        
        if not jira_connected:
            st.error("❌ Jira 연결이 필요합니다. 왼쪽 사이드바에서 Jira 연결을 완료해주세요.")
            return
        
        # Step 1: 태스크 입력
        if st.session_state.current_step == 1:
            st.markdown("## 📝 1단계: Jira 태스크 입력")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                task_key = st.text_input(
                    "Jira 태스크 키를 입력하세요:",
                    placeholder="예: PROJ-123, DEV-456, BUG-789",
                    value=st.session_state.get('task_key', '')
                )
            
            with col2:
                st.markdown("### 💡 입력 가이드")
                st.markdown("""
                - 형식: **PROJ-123**
                - 대소문자 구분 없음
                - 하이픈(-) 포함 필수
                """)
            
            if st.button("📖 태스크 읽기", type="primary", disabled=not task_key.strip()):
                if task_key.strip():
                    with st.spinner("Jira 태스크를 조회 중..."):
                        jira_task = get_jira_task(st.session_state.jira_client, task_key.strip())
                        
                        if jira_task:
                            st.session_state.current_jira_task = jira_task
                            st.session_state.task_key = task_key.strip()
                            st.session_state.current_step = 2
                            st.success(f"✅ 태스크 '{task_key}' 조회 성공!")
                            st.rerun()
                        else:
                            st.error("❌ 태스크를 찾을 수 없습니다. 태스크 키를 확인해주세요.")
        
        # Step 2: 태스크 정보 확인
        elif st.session_state.current_step == 2:
            st.markdown("## 📋 2단계: 태스크 정보 확인 및 편집")
            
            if hasattr(st.session_state, 'current_jira_task'):
                jira_task = st.session_state.current_jira_task
                
                # 태스크 정보 표시
                st.markdown(f"### 🎯 [{jira_task['key']}] {jira_task['summary']}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 상태", jira_task['status'])
                with col2:
                    st.metric("⚡ 우선순위", jira_task['priority'])
                with col3:
                    st.metric("🏷️ 타입", jira_task['issue_type'])
                
                st.markdown("---")
                
                # 설명 편집
                st.markdown("### ✏️ 태스크 설명 편집 (선택사항)")
                st.info("💡 필요시 설명을 수정하면 AI가 수정된 내용을 바탕으로 테스트케이스를 생성합니다.")
                
                edited_description = st.text_area(
                    "📄 설명:",
                    value=st.session_state.get('edited_description', jira_task['description']),
                    height=150,
                    key="description_editor"
                )
                
                # 변경사항 저장
                st.session_state.edited_description = edited_description
                has_changes = edited_description != jira_task['description']
                
                if has_changes:
                    st.success("✏️ 설명이 수정되었습니다. 이 내용이 테스트케이스 생성에 반영됩니다.")
                
                # 버튼
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ 이전 단계", type="secondary"):
                        st.session_state.current_step = 1
                        st.rerun()
                
                with col2:
                    if st.button("➡️ 다음 단계: 생성 설정", type="primary"):
                        st.session_state.current_step = 3
                        st.rerun()
        
        # Step 3: 생성 설정
        elif st.session_state.current_step == 3:
            st.markdown("## ⚙️ 3단계: 테스트케이스 생성 설정")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                test_count_ai = st.number_input(
                    "생성할 테스트케이스 개수:",
                    min_value=1,
                    max_value=10,
                    value=st.session_state.get('test_count_ai', 5),
                    help="AI가 생성할 테스트케이스 개수"
                )
                st.session_state.test_count_ai = test_count_ai
            
            with col2:
                st.markdown("### 📊 생성 미리보기")
                st.metric("🧪 생성 예정", f"{test_count_ai}개")
                st.metric("📝 구조", "3단계")
                st.caption("전제조건 → 실행단계 → 기대결과")
            
            # AI 연결 상태 확인
            if ai_connected:
                st.success("🤖 AI로 고품질 테스트케이스를 생성합니다")
            else:
                st.warning("⚠️ AI 미연결: 기본 템플릿으로 생성됩니다")
            
            # 버튼
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ 이전 단계", type="secondary"):
                    st.session_state.current_step = 2
                    st.rerun()
            
            with col2:
                if st.button("🚀 테스트케이스 생성", type="primary"):
                    st.session_state.current_step = 4
                    st.rerun()
        
        # Step 4: AI 생성 중
        elif st.session_state.current_step == 4:
            st.markdown("## 🤖 4단계: AI 테스트케이스 생성 중")
            
            # 생성 상태 표시
            jira_task = st.session_state.current_jira_task
            test_count_ai = st.session_state.get('test_count_ai', 5)
            
            # 생성 정보 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🎯 대상 태스크", jira_task['key'])
            with col2:
                st.metric("🧪 생성 개수", f"{test_count_ai}개")
            with col3:
                if ai_connected:
                    st.metric("🤖 생성 방식", "AI 기반")
                else:
                    st.metric("📝 생성 방식", "기본 템플릿")
            
            st.markdown("---")
            
            # 진행 상황 표시
            if ai_connected:
                st.markdown("### 🧠 AI가 분석하고 있습니다...")
                st.info("🔍 태스크 정보 분석 → 테스트 시나리오 설계 → 구조화된 테스트케이스 생성")
            else:
                st.markdown("### 📝 기본 템플릿으로 생성 중...")
                st.info("📋 이슈 타입 분석 → 기본 시나리오 적용 → 테스트케이스 구조화")
            
            # 자동 생성 실행 (한번만)
            if 'generation_started' not in st.session_state:
                st.session_state.generation_started = True
                
                edited_description = st.session_state.get('edited_description', jira_task['description'])
                current_task_for_generation = jira_task.copy()
                current_task_for_generation['description'] = edited_description
                
                # 진행 바와 함께 생성
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    if ai_connected:
                        status_text.text("🤖 AI 모델에 요청 전송 중...")
                        progress_bar.progress(20)
                        
                        testcases = generate_ai_testcases(
                            st.session_state.openai_client,
                            current_task_for_generation,
                            test_count_ai
                        )
                        
                        progress_bar.progress(80)
                        status_text.text("🔄 응답 처리 중...")
                        
                        if not testcases:
                            status_text.text("⚠️ AI 생성 실패, 기본 템플릿 사용...")
                            testcases = fallback_generate_structured_testcases(current_task_for_generation, test_count_ai)
                    else:
                        status_text.text("📝 기본 템플릿 적용 중...")
                        progress_bar.progress(50)
                        testcases = fallback_generate_structured_testcases(current_task_for_generation, test_count_ai)
                    
                    progress_bar.progress(100)
                    status_text.text("✅ 생성 완료!")
                    
                    if testcases:
                        st.session_state.generated_testcases = testcases
                        # 자동으로 다음 단계로
                        time.sleep(1)  # 완료 메시지 잠시 표시
                        st.session_state.current_step = 5
                        del st.session_state.generation_started  # 초기화
                        st.rerun()
                    else:
                        st.error("❌ 테스트케이스 생성에 실패했습니다.")
                        
                except Exception as e:
                    st.error(f"❌ 생성 중 오류 발생: {str(e)}")
                    status_text.text("❌ 생성 실패")
                    progress_bar.progress(0)
            
            # 수동 취소 버튼 (필요시)
            if st.button("❌ 생성 취소", type="secondary"):
                if 'generation_started' in st.session_state:
                    del st.session_state.generation_started
                st.session_state.current_step = 3
                st.rerun()
        
        # Step 5: 결과 확인
        elif st.session_state.current_step == 5:
            st.markdown("## 📋 5단계: 생성된 테스트케이스 확인")
            
            if hasattr(st.session_state, 'generated_testcases'):
                testcases = st.session_state.generated_testcases
                jira_task = st.session_state.current_jira_task
                
                st.success(f"✅ {len(testcases)}개의 구조화된 테스트케이스가 생성되었습니다!")
                
                # 편집 정보 표시
                if st.session_state.get('edited_description', jira_task['description']) != jira_task['description']:
                    st.info("ℹ️ 편집된 태스크 설명이 반영되었습니다.")
                
                # 테스트케이스 표시
                for i, testcase in enumerate(testcases, 1):
                    with st.expander(f"🧪 테스트케이스 {i}: {testcase.get('title', f'테스트케이스 {i}')}", expanded=(i == 1)):
                        
                        # 제목
                        st.markdown(f"**📌 제목:** {testcase.get('title', f'테스트케이스 {i}')}")
                        
                        # 전제조건
                        st.markdown("**🔧 전제조건 (Precondition):**")
                        st.markdown(testcase.get('precondition', '전제조건 없음'))
                        
                        # 실행단계
                        st.markdown("**▶️ 실행단계 (Steps):**")
                        steps = testcase.get('steps', [])
                        if isinstance(steps, list):
                            for step in steps:
                                st.markdown(f"   {step}")
                        else:
                            st.markdown(steps)
                        
                        # 기대결과
                        st.markdown("**✅ 기대결과 (Expectation):**")
                        st.markdown(testcase.get('expectation', '기대결과 없음'))
                
                # 다운로드 기능
                st.markdown("---")
                
                # 다운로드 파일 생성
                edited_description = st.session_state.get('edited_description', jira_task['description'])
                current_task_for_generation = jira_task.copy()
                current_task_for_generation['description'] = edited_description
                has_changes = edited_description != jira_task['description']
                
                testcase_text = f"Jira Task: {current_task_for_generation['key']} - {current_task_for_generation['summary']}\\n"
                testcase_text += f"Generated by: AI-based Structured Test Cases\\n"
                if has_changes:
                    testcase_text += "✏️ Edited Description Used\\n"
                testcase_text += f"Total Count: {len(testcases)}\\n"
                testcase_text += "=" * 80 + "\\n\\n"
                
                for i, testcase in enumerate(testcases, 1):
                    testcase_text += f"테스트케이스 {i}: {testcase.get('title', f'테스트케이스 {i}')}\\n"
                    testcase_text += "-" * 60 + "\\n"
                    testcase_text += f"전제조건 (Precondition):\\n{testcase.get('precondition', '전제조건 없음')}\\n\\n"
                    testcase_text += f"실행단계 (Steps):\\n"
                    steps = testcase.get('steps', [])
                    if isinstance(steps, list):
                        for step in steps:
                            testcase_text += f"{step}\\n"
                    else:
                        testcase_text += f"{steps}\\n"
                    testcase_text += f"\\n기대결과 (Expectation):\\n{testcase.get('expectation', '기대결과 없음')}\\n"
                    testcase_text += "\\n" + "=" * 80 + "\\n\\n"
                
                # 버튼
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("⬅️ 생성 설정으로", type="secondary"):
                        st.session_state.current_step = 3
                        st.rerun()
                
                with col2:
                    st.download_button(
                        label="💾 테스트케이스 다운로드",
                        data=testcase_text,
                        file_name=f"structured_testcases_{current_task_for_generation['key']}.txt",
                        mime="text/plain"
                    )
                
                with col3:
                    if st.button("🔄 새로 시작", type="primary"):
                        # 세션 초기화
                        for key in ['current_step', 'current_jira_task', 'generated_testcases', 'edited_description', 'task_key', 'test_count_ai', 'generation_started']:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.session_state.current_step = 1
                        st.rerun()
    
    elif tool_choice == "Jira 태스크 기반 유닛테스트 템플릿 생성":
        st.header("🧪 Jira 태스크 기반 유닛테스트 템플릿 생성")
        
        # 입력 섹션
        col1, col2 = st.columns([2, 1])
        
        with col1:
            task_key_unit = st.text_input(
                "Jira 태스크 키를 입력하세요:",
                placeholder="예: PROJ-123, DEV-456, BUG-789",
                key="unit_task_key"
            )
            
            function_name = st.text_input(
                "함수명을 입력하세요:",
                placeholder="예: process_payment, validate_user, send_notification"
            )
        
        with col2:
            st.markdown("### 📋 Jira 연동 장점")
            st.markdown("""
            - ✅ 태스크 정보 자동 포함
            - ✅ 인수 조건 기반 테스트
            - ✅ 이슈 타입별 맞춤 테스트
            - ✅ 추적 가능한 테스트 코드
            - ✅ 요구사항 연결성 확보
            """)
        
        # 1단계: 태스크 읽기
        if st.button("📖 Jira 태스크 읽기", type="primary", key="unit_read_task"):
            if not hasattr(st.session_state, 'jira_connected') or not st.session_state.jira_connected:
                st.error("❌ 먼저 Jira에 연결해주세요!")
            elif task_key_unit.strip():
                with st.spinner("Jira 태스크를 조회 중..."):
                    jira_task = get_jira_task(st.session_state.jira_client, task_key_unit.strip())
                    
                    if jira_task:
                        # 태스크 정보를 세션에 저장 (유닛테스트용)
                        st.session_state.current_jira_task_unit = jira_task
                        st.success(f"✅ Jira 태스트 '{task_key_unit}' 조회 성공!")
                    else:
                        if 'current_jira_task_unit' in st.session_state:
                            del st.session_state.current_jira_task_unit
            else:
                st.warning("⚠️ Jira 태스크 키를 입력해주세요!")
        
        # 태스크 정보 표시 (읽기 성공 시)
        if hasattr(st.session_state, 'current_jira_task_unit') and st.session_state.current_jira_task_unit:
            jira_task = st.session_state.current_jira_task_unit
            
            with st.expander("📋 읽어온 Jira 태스크 정보", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("태스크 키", jira_task['key'])
                    st.metric("상태", jira_task['status'])
                with col2:
                    st.metric("우선순위", jira_task['priority'])
                    st.metric("이슈 타입", jira_task['issue_type'])
                with col3:
                    st.text_area("요약", jira_task['summary'], height=70, disabled=True, key="unit_summary")
                
                st.text_area("설명", jira_task['description'], height=100, disabled=True, key="unit_description")
                
                if jira_task['acceptance_criteria']:
                    st.text_area("인수 조건", jira_task['acceptance_criteria'], height=80, disabled=True, key="unit_ac")
            
            # 2단계: 유닛테스트 생성 설정
            if function_name.strip():
                st.markdown("---")
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("### 🧪 유닛테스트 생성 설정")
                    test_count = st.slider(
                        "생성할 테스트케이스 수:",
                        min_value=1,
                        max_value=8,
                        value=default_test_count
                    )
                    
                    include_jira_info = st.checkbox("Jira 태스크 정보를 테스트 코드에 포함", value=True)
                
                with col2:
                    st.markdown("### 📊 생성 예상")
                    st.metric("테스트 메서드 수", test_count)
                    st.metric("예상 코드 라인", test_count * 15 + 25)
                    st.metric("연결된 Jira", jira_task['key'])
                
                # 유닛테스트 생성 버튼
                if st.button("🚀 유닛테스트 코드 생성", type="secondary", use_container_width=True):
                    with st.spinner("유닛테스트 템플릿을 생성 중..."):
                        template = generate_unittest_template(
                            function_name.strip(), 
                            test_count, 
                            jira_task if include_jira_info else None
                        )
                        
                        st.success(f"✅ '{function_name}' 함수를 위한 Jira 연동 유닛테스트가 생성되었습니다!")
                        
                        # 코드 출력
                        st.markdown("### 🔍 생성된 테스트 코드")
                        st.code(template, language="python")
                        
                        # 다운로드 기능
                        st.download_button(
                            label="💾 테스트 코드 다운로드",
                            data=template,
                            file_name=f"test_{function_name}_{jira_task['key']}.py",
                            mime="text/plain"
                        )
                        
                        # 통계 정보
                        st.markdown("### 📊 생성 통계")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("테스트케이스 수", test_count)
                        with col2:
                            st.metric("코드 라인 수", len(template.split("\\n")))
                        with col3:
                            st.metric("Jira 태스크", jira_task['key'])
                        with col4:
                            st.metric("함수명", function_name)
            else:
                if hasattr(st.session_state, 'current_jira_task_unit'):
                    st.info("💡 함수명을 입력하면 유닛테스트 생성 옵션이 나타납니다.")
    
    # 푸터
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            Made with ❤️ by AI 테스트케이스 생성기 (Jira 연동) | 
            <a href='https://github.com/yjnoh' target='_blank'>GitHub</a>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main() 