import streamlit as st
import json
import os
import time
import requests
import base64
import re
from typing import List, Dict, Optional
from atlassian import Jira
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


def setup_testrail_client(url: str, username: str, password: str) -> Optional[Dict]:
    """TestRail 클라이언트를 설정합니다."""
    try:
        # 기본 인증 헤더 생성 (username:password)
        auth_string = f"{username}:{password}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json'
        }
        
        # 연결 테스트 (사용자 정보 조회)
        response = requests.get(f"{url}/index.php?/api/v2/get_user_by_email&email={username}", headers=headers)
        
        if response.status_code == 200:
            return {
                'url': url,
                'headers': headers
            }
        else:
            st.error(f"TestRail 연결 실패: {response.status_code} - {response.text if response.text else '인증 정보를 확인해주세요'}")
            return None
            
    except Exception as e:
        st.error(f"TestRail 연결 실패: {str(e)}")
        return None


def get_testrail_projects(client: Dict) -> List[Dict]:
    """TestRail 프로젝트 목록을 가져옵니다."""
    try:
        response = requests.get(f"{client['url']}/index.php?/api/v2/get_projects", headers=client['headers'])
        
        if response.status_code == 200:
            data = response.json()
            
            # 디버깅 정보 (필요시에만 표시)
            if st.session_state.get('show_testrail_debug', False):
                st.write("🔍 TestRail 프로젝트 API 응답:", data)
            
            # 다양한 응답 형태 처리
            if isinstance(data, list):
                # 리스트 형태의 응답
                projects = []
                for item in data:
                    if isinstance(item, dict):
                        # 정상적인 딕셔너리 형태
                        projects.append({
                            'id': item.get('id', 0),
                            'name': item.get('name', 'Unknown Project'),
                            'is_completed': item.get('is_completed', False)
                        })
                    else:
                        st.warning(f"⚠️ 예상치 못한 프로젝트 데이터 형태: {type(item)} - {item}")
                return projects
            elif isinstance(data, dict):
                # 딕셔너리 형태의 응답 (예: {'projects': [...]} 또는 단일 프로젝트)
                if 'projects' in data:
                    return get_testrail_projects_from_list(data['projects'])
                else:
                    # 단일 프로젝트인 경우
                    return [{
                        'id': data.get('id', 0),
                        'name': data.get('name', 'Unknown Project'),
                        'is_completed': data.get('is_completed', False)
                    }]
            else:
                st.error(f"❌ 예상치 못한 API 응답 형태: {type(data)}")
                return []
                
        else:
            st.error(f"프로젝트 목록 조회 실패: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        st.error(f"프로젝트 목록 조회 실패: {str(e)}")
        return []


def get_testrail_projects_from_list(projects_data: List) -> List[Dict]:
    """프로젝트 리스트 데이터를 정규화합니다."""
    projects = []
    for item in projects_data:
        if isinstance(item, dict):
            projects.append({
                'id': item.get('id', 0),
                'name': item.get('name', 'Unknown Project'),
                'is_completed': item.get('is_completed', False)
            })
        else:
            st.warning(f"⚠️ 예상치 못한 프로젝트 데이터: {item}")
    return projects


def get_testrail_suites(client: Dict, project_id: int) -> List[Dict]:
    """TestRail 스위트 목록을 가져옵니다."""
    try:
        response = requests.get(f"{client['url']}/index.php?/api/v2/get_suites/{project_id}", headers=client['headers'])
        
        if response.status_code == 200:
            data = response.json()
            
            # 디버깅 정보 (필요시에만 표시)
            if st.session_state.get('show_testrail_debug', False):
                st.write("🔍 TestRail 스위트 API 응답:", data)
            
            # 다양한 응답 형태 처리
            if isinstance(data, list):
                # 리스트 형태의 응답
                suites = []
                for item in data:
                    if isinstance(item, dict):
                        suites.append({
                            'id': item.get('id', 0),
                            'name': item.get('name', 'Unknown Suite'),
                            'description': item.get('description', ''),
                            'project_id': item.get('project_id', project_id),
                            'is_master': item.get('is_master', False),
                            'is_baseline': item.get('is_baseline', False),
                            'is_completed': item.get('is_completed', False)
                        })
                    else:
                        st.warning(f"⚠️ 예상치 못한 스위트 데이터 형태: {type(item)} - {item}")
                return suites
            elif isinstance(data, dict):
                # 딕셔너리 형태의 응답
                if 'suites' in data:
                    return get_testrail_suites_from_list(data['suites'])
                else:
                    # 단일 스위트인 경우
                    return [{
                        'id': data.get('id', 0),
                        'name': data.get('name', 'Unknown Suite'),
                        'description': data.get('description', ''),
                        'project_id': data.get('project_id', project_id),
                        'is_master': data.get('is_master', False),
                        'is_baseline': data.get('is_baseline', False),
                        'is_completed': data.get('is_completed', False)
                    }]
            else:
                st.error(f"❌ 예상치 못한 스위트 API 응답 형태: {type(data)}")
                return []
                
        else:
            st.error(f"스위트 목록 조회 실패: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        st.error(f"스위트 목록 조회 실패: {str(e)}")
        return []


def get_testrail_suites_from_list(suites_data: List) -> List[Dict]:
    """스위트 리스트 데이터를 정규화합니다."""
    suites = []
    for item in suites_data:
        if isinstance(item, dict):
            suites.append({
                'id': item.get('id', 0),
                'name': item.get('name', 'Unknown Suite'),
                'description': item.get('description', ''),
                'project_id': item.get('project_id', 0),
                'is_master': item.get('is_master', False),
                'is_baseline': item.get('is_baseline', False),
                'is_completed': item.get('is_completed', False)
            })
        else:
            st.warning(f"⚠️ 예상치 못한 스위트 데이터: {item}")
    return suites


def get_testrail_sections(client: Dict, project_id: int, suite_id: int = None) -> List[Dict]:
    """TestRail 섹션 목록을 가져옵니다."""
    try:
        # suite_id가 있으면 해당 스위트의 섹션만 가져오기
        if suite_id:
            url = f"{client['url']}/index.php?/api/v2/get_sections/{project_id}&suite_id={suite_id}"
        else:
            url = f"{client['url']}/index.php?/api/v2/get_sections/{project_id}"
            
        response = requests.get(url, headers=client['headers'])
        
        if response.status_code == 200:
            data = response.json()
            
            # 디버깅 정보 (필요시에만 표시)
            if st.session_state.get('show_testrail_debug', False):
                st.write("🔍 TestRail 섹션 API 응답:", data)
            
            # 다양한 응답 형태 처리
            if isinstance(data, list):
                # 리스트 형태의 응답
                sections = []
                for item in data:
                    if isinstance(item, dict):
                        sections.append({
                            'id': item.get('id', 0),
                            'name': item.get('name', 'Unknown Section'),
                            'suite_id': item.get('suite_id', 0),
                            'parent_id': item.get('parent_id', None)
                        })
                    else:
                        st.warning(f"⚠️ 예상치 못한 섹션 데이터 형태: {type(item)} - {item}")
                return sections
            elif isinstance(data, dict):
                # 딕셔너리 형태의 응답
                if 'sections' in data:
                    return get_testrail_sections_from_list(data['sections'])
                else:
                    # 단일 섹션인 경우
                    return [{
                        'id': data.get('id', 0),
                        'name': data.get('name', 'Unknown Section'),
                        'suite_id': data.get('suite_id', 0),
                        'parent_id': data.get('parent_id', None)
                    }]
            else:
                st.error(f"❌ 예상치 못한 섹션 API 응답 형태: {type(data)}")
                return []
                
        else:
            st.error(f"섹션 목록 조회 실패: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        st.error(f"섹션 목록 조회 실패: {str(e)}")
        return []


def get_testrail_sections_from_list(sections_data: List) -> List[Dict]:
    """섹션 리스트 데이터를 정규화합니다."""
    sections = []
    for item in sections_data:
        if isinstance(item, dict):
            sections.append({
                'id': item.get('id', 0),
                'name': item.get('name', 'Unknown Section'),
                'suite_id': item.get('suite_id', 0),
                'parent_id': item.get('parent_id', None)
            })
        else:
            st.warning(f"⚠️ 예상치 못한 섹션 데이터: {item}")
    return sections


def create_testrail_testcase(client: Dict, section_id: int, testcase: Dict) -> bool:
    """TestRail에 테스트케이스를 생성합니다."""
    try:
        # 실행단계를 문자열로 변환
        steps = testcase.get('steps', [])
        if isinstance(steps, list):
            steps_text = '\n'.join(steps)
        else:
            steps_text = str(steps)
        
        # TestRail 테스트케이스 데이터
        data = {
            'title': testcase.get('title', '제목 없음'),
            'custom_preconds': testcase.get('precondition', ''),
            'custom_steps': steps_text,
            'custom_expected': testcase.get('expectation', ''),
            'custom_quality_model': 1,
            'type_id': 1,  # Test Case (Other)
            'priority_id': 3,  # Medium
        }
        
        response = requests.post(
            f"{client['url']}/index.php?/api/v2/add_case/{section_id}",
            headers=client['headers'],
            json=data
        )
        
        if response.status_code == 200:
            return True
        else:
            st.error(f"테스트케이스 생성 실패: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        st.error(f"테스트케이스 생성 실패: {str(e)}")
        return False


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
        # config.json 및 오버라이드 설정 로드
        config = load_config()
        openai_config = config.get('openai', {}) if config else {}
        
        # 세션의 오버라이드 설정이 있으면 우선 사용
        if hasattr(st.session_state, 'override_openai_config'):
            openai_config.update(st.session_state.override_openai_config)
        
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
    
    # 연결 상태 표시
    with st.sidebar:
        st.header("🔗 연결 상태")
        
        # 설정파일 상태
        if config:
            st.success("✅ 설정파일 로드됨")
        else:
            st.warning("⚠️ 설정파일 없음")
        
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
        
        # OpenAI 자동 연결
        openai_config = config.get('openai', {}) if config else {}
        if (config and openai_config.get('api_key') and 
            config.get('app', {}).get('auto_connect_ai', False) and 
            'openai_connected' not in st.session_state):
            
            client = setup_openai_client(openai_config['api_key'])
            if client:
                st.session_state.openai_connected = True
                st.session_state.openai_client = client
        
        # TestRail 자동 연결
        testrail_config = config.get('testrail', {}) if config else {}
        if (config and testrail_config.get('url') and testrail_config.get('username') and 
            testrail_config.get('password') and config.get('app', {}).get('auto_connect_testrail', False) and 
            'testrail_connected' not in st.session_state):
            
            client = setup_testrail_client(
                testrail_config['url'],
                testrail_config['username'],
                testrail_config['password']
            )
            if client:
                st.session_state.testrail_connected = True
                st.session_state.testrail_client = client
        

        

    
    # 기본 테스트 개수 설정
    default_test_count = 5
    if config and 'app' in config:
        default_test_count = config['app'].get('default_test_count', 5)
    
    # 메인 컨텐츠
        st.header("🤖 AI 기반 구조화된 테스트케이스 생성")
        
        # 진행 단계 초기화
        if 'current_step' not in st.session_state:
            st.session_state.current_step = 1
        
        # 진행 바 표시
        progress_steps = ["태스크 입력", "태스크 정보 확인", "생성 설정", "AI 생성 중", "시나리오 확인", "TestRail 등록"]
        
        # 진행률 계산
        progress = (st.session_state.current_step - 1) / (len(progress_steps) - 1)
        st.progress(progress)
        
        # 현재 단계 표시
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        for i, step_name in enumerate(progress_steps, 1):
            with [col1, col2, col3, col4, col5, col6][i-1]:
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
        
        # Step 1: 태스크 입력
        if st.session_state.current_step == 1:
            st.markdown("## 📝 1단계: 태스크 정보 입력")
            
            # 입력 방식 선택
            input_method = st.radio(
                "태스크 정보 입력 방식을 선택하세요:",
                ["🔗 Jira에서 태스크 가져오기", "🎨 Figma에서 요구사항 선택", "✏️ 직접 태스크 정보 입력"],
                horizontal=True
            )
            
            if input_method == "🔗 Jira에서 태스크 가져오기":
                if not jira_connected:
                    st.error("❌ Jira 연결이 필요합니다. 왼쪽 사이드바에서 Jira 연결을 완료해주세요.")
                    return
                
                st.markdown("### 🔗 Jira 태스크 조회")
                
                def handle_jira_task_input():
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
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    task_key = st.text_input(
                        "Jira 태스크 키를 입력하세요:",
                        placeholder="예: PROJ-123, DEV-456, BUG-789",
                        value=st.session_state.get('task_key', ''),
                        key="jira_task_key_input"
                    )
                
                with col2:
                    st.markdown("### 💡 입력 가이드")
                    st.markdown("""
                    - 형식: **PROJ-123**
                    - 대소문자 구분 없음
                    - 하이픈(-) 포함 필수
                    """)
                
                if st.button("📖 Jira 태스크 읽기", type="primary", disabled=not task_key.strip()):
                    # 새로운 태스크를 읽을 때 기존 테스트케이스 초기화
                    if 'generated_testcases' in st.session_state:
                        del st.session_state.generated_testcases
                    if 'editable_testcases' in st.session_state:
                        del st.session_state.editable_testcases
                    if 'generation_started' in st.session_state:
                        del st.session_state.generation_started
                    if 'edited_description' in st.session_state:
                        del st.session_state.edited_description
                    handle_jira_task_input()
            
            elif input_method == "🎨 Figma에서 요구사항 선택":
                tab1, tab2 = st.tabs(["🔗 링크 기반 바로 생성", "🗂️ 단계별 선택"])
                with tab1:
                    st.markdown("#### Figma 링크를 입력하면 바로 테스트 생성!")
                    figma_config = config.get('figma', {}) if config else {}
                    api_key = figma_config.get('api_key', '')
                    figma_url = st.text_input("Figma 링크 입력", value=st.session_state.get('figma_url_input_direct', ''), key="figma_url_input_direct", placeholder="https://www.figma.com/file/FILEKEY/...?node-id=6-253")
                    file_key = ""
                    node_id = ""
                    if figma_url:
                        m = re.search(r'figma.com/(file|design)/([\w\d]+)', figma_url)
                        if m:
                            file_key = m.group(2)
                        m2 = re.search(r'node-id=([\w-]+)', figma_url)
                        if m2:
                            node_id = m2.group(1).replace('-', ':')  # 하이픈을 콜론으로 변환
                    if api_key and file_key and node_id:
                        st.markdown("**텍스트 추출 API URL**")
                        st.code(f"https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}", language="text")
                        if st.button("🚀 바로 테스트 생성 시작", type="primary"):
                            try:
                                with st.spinner(f"Figma 노드 전체 텍스트 추출 중... (fileKey: {file_key}, nodeId: {node_id})"):
                                    headers = {"X-Figma-Token": api_key}
                                    url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}"
                                    resp = requests.get(url, headers=headers)
                                    if resp.status_code == 200:
                                        data = resp.json()
                                        if node_id not in data['nodes']:
                                            st.error(f"이 node-id({node_id})는 Figma API에서 지원하지 않거나, 존재하지 않습니다.")
                                            return
                                        node = data['nodes'][node_id]['document']
                                        descs = []
                                        def extract_text(n):
                                            if n['type'] == 'TEXT' and 'characters' in n:
                                                descs.append(n['characters'])
                                            for c in n.get('children', []):
                                                extract_text(c)
                                        extract_text(node)
                                        desc = "\n".join(descs)
                                        figma_task = {
                                            'key': f'FIGMA-{node_id}',
                                            'summary': f"Figma 노드 {node_id}",
                                            'description': desc or f"Figma 노드 전체 텍스트 없음",
                                            'acceptance_criteria': '',
                                            'status': 'Figma',
                                            'priority': 'Medium',
                                            'issue_type': 'Figma 요구사항'
                                        }
                                        st.session_state.current_jira_task = figma_task
                                        st.session_state.task_key = figma_task['key']
                                        st.session_state.current_step = 2
                                        st.success("✅ Figma 요구사항이 선택되었습니다!")
                                        st.rerun()
                                    else:
                                        st.error(f"Figma 노드 조회 실패: {resp.status_code} - {resp.text}")
                            except Exception as e:
                                st.error(f"Figma 노드 전체 텍스트 추출 오류: {str(e)}")
                with tab2:
                    # 단계별 선택: 페이지/레이어 선택 방식 복구
                    figma_config = config.get('figma', {}) if config else {}
                    api_key = figma_config.get('api_key', '')
                    figma_url = st.text_input("Figma 링크를 입력하세요", value=st.session_state.get('figma_url_input_step', ''), key="figma_url_input_step", placeholder="https://www.figma.com/file/FILEKEY/...?node-id=6-253")
                    file_key = ""
                    node_id = ""
                    if figma_url:
                        m = re.search(r'figma.com/(file|design)/([\w\d]+)', figma_url)
                        if m:
                            file_key = m.group(2)
                        m2 = re.search(r'node-id=([\w-]+)', figma_url)
                        if m2:
                            node_id = m2.group(1)
                    # 1. 페이지(children) 목록 조회
                    pages = []
                    page_id_map = {}
                    page_api_data = None
                    selected_page = None
                    selected_layer = None
                    if api_key and file_key:
                        try:
                            with st.spinner(f"Figma에서 페이지 목록 불러오는 중... (fileKey: {file_key})"):
                                headers = {"X-Figma-Token": api_key}
                                url = f"https://api.figma.com/v1/files/{file_key}"
                                resp = requests.get(url, headers=headers)
                                if resp.status_code == 200:
                                    data = resp.json()
                                    page_api_data = data
                                    for page in data['document']['children']:
                                        pages.append(page['name'])
                                        page_id_map[page['name']] = page['id']
                                else:
                                    st.error(f"Figma 파일 조회 실패: {resp.status_code} - {resp.text}")
                        except Exception as e:
                            st.error(f"Figma API 오류: {str(e)}")
                    if api_key and file_key and not pages:
                        st.warning("⚠️ 페이지 목록이 비어 있습니다. 링크와 API Key를 확인하세요.")
                        if page_api_data:
                            st.write("Figma API 응답:", page_api_data)
                    # node-id가 있으면 해당 페이지 자동 선택
                    if node_id and page_id_map:
                        for name, pid in page_id_map.items():
                            if pid == node_id:
                                selected_page = name
                                break
                    col_page1, col_page2 = st.columns([3, 2])
                    with col_page1:
                        selected_page = st.selectbox("페이지를 선택하세요", options=pages, key="figma_page_select_step", index=pages.index(selected_page) if selected_page in pages else 0) if pages else None
                    with col_page2:
                        if file_key:
                            st.markdown("**페이지 목록 API URL**")
                            st.code(f"https://api.figma.com/v1/files/{file_key}", language="text")
                    # 2. 해당 페이지의 children(프레임/컴포넌트 등) 목록 조회
                    layers = []
                    layer_id_map = {}
                    layer_api_data = None
                    if api_key and file_key and selected_page:
                        try:
                            with st.spinner(f"Figma에서 하위 요소(프레임/컴포넌트 등) 목록 불러오는 중... (fileKey: {file_key}, page: {selected_page})"):
                                headers = {"X-Figma-Token": api_key}
                                url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={page_id_map[selected_page]}"
                                resp = requests.get(url, headers=headers)
                                if resp.status_code == 200:
                                    data = resp.json()
                                    layer_api_data = data
                                    page_node = data['nodes'][page_id_map[selected_page]]['document']
                                    for child in page_node.get('children', []):
                                        label = f"{child.get('name', '[이름없음]')} ({child.get('type', '-')})"
                                        layers.append(label)
                                        layer_id_map[label] = child['id']
                                else:
                                    st.error(f"Figma 페이지 children 조회 실패: {resp.status_code} - {resp.text}")
                        except Exception as e:
                            st.error(f"Figma API 오류: {str(e)}")
                    if api_key and file_key and selected_page and not layers:
                        st.warning("⚠️ 하위 요소 목록이 비어 있습니다. 페이지 구조를 확인하세요.")
                        if layer_api_data:
                            st.write("Figma API 응답:", layer_api_data)
                    col_layer1, col_layer2 = st.columns([3, 2])
                    with col_layer1:
                        selected_layer = st.selectbox("하위 요소(프레임/컴포넌트 등)를 선택하세요", options=layers, key="figma_layer_select_step", index=layers.index(selected_layer) if selected_layer in layers else 0) if layers else None
                    with col_layer2:
                        if file_key and selected_page:
                            st.markdown("**하위요소(children) API URL**")
                            st.code(f"https://api.figma.com/v1/files/{file_key}/nodes?ids={page_id_map[selected_page]}", language="text")
                    # 3. 선택된 레이어의 텍스트 추출
                    if selected_layer:
                        col_btn, col_url = st.columns([2, 3])
                        with col_btn:
                            if st.button("✅ 이 요구사항으로 테스트 생성 시작", type="primary"):
                                try:
                                    with st.spinner(f"Figma 레이어 텍스트 추출 중... (fileKey: {file_key}, nodeId: {layer_id_map[selected_layer]})"):
                                        headers = {"X-Figma-Token": api_key}
                                        url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={layer_id_map[selected_layer]}"
                                        resp = requests.get(url, headers=headers)
                                        if resp.status_code == 200:
                                            node = resp.json()['nodes'][layer_id_map[selected_layer]]['document']
                                            descs = []
                                            def extract_text(n):
                                                if n['type'] == 'TEXT' and 'characters' in n:
                                                    descs.append(n['characters'])
                                                for c in n.get('children', []):
                                                    extract_text(c)
                                            extract_text(node)
                                            desc = "\n".join(descs)
                                            figma_task = {
                                                'key': f'FIGMA-{layer_id_map[selected_layer]}',
                                                'summary': f"{selected_page} - {selected_layer}",
                                                'description': desc or f"Figma 레이어: {selected_layer}",
                                                'acceptance_criteria': '',
                                                'status': 'Figma',
                                                'priority': 'Medium',
                                                'issue_type': 'Figma 요구사항'
                                            }
                                            st.session_state.current_jira_task = figma_task
                                            st.session_state.task_key = figma_task['key']
                                            st.session_state.current_step = 2
                                            st.success("✅ Figma 요구사항이 선택되었습니다!")
                                            st.rerun()
                                        else:
                                            st.error(f"Figma 노드 조회 실패: {resp.status_code} - {resp.text}")
                                except Exception as e:
                                    st.error(f"Figma 레이어 텍스트 추출 오류: {str(e)}")
                        with col_url:
                            if file_key and selected_layer:
                                st.markdown("**텍스트 추출 API URL**")
                                st.code(f"https://api.figma.com/v1/files/{file_key}/nodes?ids={layer_id_map[selected_layer]}", language="text")
            else:  # 직접 입력
                st.markdown("### ✏️ 직접 태스크 정보 입력")
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    # 핵심 정보만 입력
                    task_title = st.text_input(
                        "테스트 대상 제목:",
                        placeholder="예: 사용자 로그인 기능, 결제 프로세스, 데이터 검증",
                        value=st.session_state.get('task_title', ''),
                        key="manual_task_title"
                    )
                
                with col2:
                    st.markdown("### 💡 입력 팁")
                    st.markdown("""
                    - **제목**: 테스트할 기능이나 수정사항
                    - **설명**: 상세한 요구사항이나 동작 방식
                    """)
                
                # 상세 정보 입력
                task_description = st.text_area(
                    "상세 설명:",
                    placeholder="테스트할 기능의 상세한 내용, 동작 방식, 요구사항을 입력하세요",
                    value=st.session_state.get('task_description', ''),
                    height=300,
                    key="manual_task_description"
                )
                
                # 입력 완료 버튼
                if st.button("✅ 테스트 정보 저장", type="primary", disabled=not task_title.strip()):
                    # 새로운 태스크를 입력할 때 기존 테스트케이스 초기화
                    if 'generated_testcases' in st.session_state:
                        del st.session_state.generated_testcases
                    if 'editable_testcases' in st.session_state:
                        del st.session_state.editable_testcases
                    if 'generation_started' in st.session_state:
                        del st.session_state.generation_started
                    if 'edited_description' in st.session_state:
                        del st.session_state.edited_description
                    
                    # 수동 입력된 정보로 태스크 객체 생성
                    manual_task = {
                        'key': f'TEST-{int(time.time())}',
                        'summary': task_title,
                        'description': task_description,
                        'acceptance_criteria': '',
                        'status': 'To Do',
                        'priority': 'Medium',
                        'issue_type': '기능 테스트'
                    }
                    
                    st.session_state.current_jira_task = manual_task
                    st.session_state.task_key = manual_task['key']
                    st.session_state.current_step = 2
                    st.success("✅ 테스트 정보가 저장되었습니다!")
                    st.rerun()
        

        
        # Step 2: 태스크 정보 확인
        elif st.session_state.current_step == 2:
            st.markdown("## 📋 2단계: 태스크 정보 확인 및 편집")
            
            if hasattr(st.session_state, 'current_jira_task'):
                jira_task = st.session_state.current_jira_task
                
                # 태스크 정보 표시
                st.markdown(f"### 🎯 [{jira_task['key']}] {jira_task['summary']}")
                
                # 메타 정보를 작게 표시
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.caption(f"📊 상태: **{jira_task['status']}**")
                with col2:
                    st.caption(f"⚡ 우선순위: **{jira_task['priority']}**")
                with col3:
                    st.caption(f"🏷️ 타입: **{jira_task['issue_type']}**")
                
                st.markdown("---")
                
                # 설명 편집 (크게 표시)
                st.markdown("### 📄 태스크 설명")
                st.info("💡 필요시 설명을 수정하면 AI가 수정된 내용을 바탕으로 테스트케이스를 생성합니다.")
                
                edited_description = st.text_area(
                    "설명 편집:",
                    value=st.session_state.get('edited_description', jira_task['description']),
                    height=250,
                    key="description_editor",
                    help="이 설명이 AI 테스트케이스 생성에 사용됩니다"
                )
                
                # 변경사항 저장
                st.session_state.edited_description = edited_description
                has_changes = edited_description != jira_task['description']
                
                if has_changes:
                    st.success("✏️ 설명이 수정되었습니다. 이 내용이 테스트케이스 생성에 반영됩니다.")
                    # 태스크 설명이 변경되면 기존 테스트케이스 초기화
                    if 'generated_testcases' in st.session_state:
                        del st.session_state.generated_testcases
                    if 'generation_started' in st.session_state:
                        del st.session_state.generation_started
                
                # 버튼
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ 이전 단계", type="secondary"):
                        # 이전 단계로 갈 때 태스크 정보가 변경되었으면 초기화
                        if has_changes:
                            if 'generated_testcases' in st.session_state:
                                del st.session_state.generated_testcases
                            if 'editable_testcases' in st.session_state:
                                del st.session_state.editable_testcases
                            if 'generation_started' in st.session_state:
                                del st.session_state.generation_started
                        st.session_state.current_step = 1
                        st.rerun()
                
                with col2:
                    if st.button("➡️ 다음 단계: 생성 설정", type="primary"):
                        # 태스크 설명이 변경되었는지 확인
                        original_description = jira_task['description']
                        current_description = st.session_state.get('edited_description', original_description)
                        
                        if current_description != original_description:
                            # 설명이 변경되었으면 테스트케이스 초기화
                            if 'generated_testcases' in st.session_state:
                                del st.session_state.generated_testcases
                            if 'generation_started' in st.session_state:
                                del st.session_state.generation_started
                            st.success("🔄 태스크 설명이 변경되어 테스트케이스가 새로 생성됩니다.")
                        
                        st.session_state.current_step = 3
                        st.rerun()
        
        # Step 3: 생성 설정
        elif st.session_state.current_step == 3:
            st.markdown("## ⚙️ 3단계: 테스트케이스 생성 설정")
            
            # 테스트 개수 선택을 위한 컬럼 레이아웃
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown("**생성할 테스트케이스 개수:**")
                current_count = st.session_state.get('test_count_ai', 5)

                # 3개 컬럼으로 레이아웃: 숫자박스 | 감소버튼 | 증가버튼
                input_col1, input_col2, input_col3 = st.columns([3, 1, 1])
                
                with input_col1:
                    st.markdown(f"<div style='text-align: center; font-size: 18px; font-weight: bold; padding: 8px; background-color: #f0f2f6; border-radius: 5px;'>{current_count}</div>", unsafe_allow_html=True)
                
                with input_col2:
                    if st.button("🔽", help="개수 감소", disabled=current_count <= 1, key="decrease_btn"):
                        st.session_state.test_count_ai = current_count - 1
                        st.rerun()
                
                with input_col3:
                    if st.button("🔼", help="개수 증가", disabled=current_count >= 10, key="increase_btn"):
                        st.session_state.test_count_ai = current_count + 1
                        st.rerun()
                
                st.caption("💡 감소/증가 버튼으로 개수를 조절하세요")
            

            
            st.markdown("---")
            
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
                    # 태스크 설명이 변경되었는지 확인
                    jira_task = st.session_state.current_jira_task
                    original_description = jira_task['description']
                    current_description = st.session_state.get('edited_description', original_description)
                    
                    # 태스크 설명이 변경되었는지 확인
                    if current_description != original_description:
                        # 설명이 변경되었으면 테스트케이스 초기화
                        if 'generated_testcases' in st.session_state:
                            del st.session_state.generated_testcases
                        if 'editable_testcases' in st.session_state:
                            del st.session_state.editable_testcases
                        if 'generation_started' in st.session_state:
                            del st.session_state.generation_started
                        st.success("🔄 태스크 설명이 변경되어 테스트케이스가 새로 생성됩니다.")
                    
                    # 테스트 개수 업데이트 (초기화하지 않음)
                    current_test_count = st.session_state.get('test_count_ai', 5)
                    st.session_state.previous_test_count = current_test_count
                    
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
        
        # Step 5: 시나리오 확인
        elif st.session_state.current_step == 5:
            st.markdown("## 📋 5단계: 시나리오 확인 및 편집")
            
            if hasattr(st.session_state, 'generated_testcases'):
                # 편집 가능한 테스트케이스 복사본 생성 (한번만)
                if 'editable_testcases' not in st.session_state:
                    st.session_state.editable_testcases = st.session_state.generated_testcases.copy()
                
                testcases = st.session_state.editable_testcases
                jira_task = st.session_state.current_jira_task
                
                st.success(f"✅ {len(testcases)}개의 테스트케이스를 편집할 수 있습니다!")
                
                # 편집 정보 표시
                if st.session_state.get('edited_description', jira_task['description']) != jira_task['description']:
                    st.info("ℹ️ 편집된 태스크 설명이 반영되었습니다.")
                
                # 새 테스트케이스 추가 버튼
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown("### ✏️ 테스트케이스 편집")
                with col2:
                    if st.button("➕ 새 테스트케이스 추가", type="secondary"):
                        new_testcase = {
                            "title": f"[{jira_task['key']}] 새 테스트케이스",
                            "precondition": "• 전제조건을 입력하세요",
                            "steps": ["1. 첫 번째 단계를 입력하세요", "2. 두 번째 단계를 입력하세요"],
                            "expectation": "• 기대결과를 입력하세요"
                        }
                        st.session_state.editable_testcases.append(new_testcase)
                        st.rerun()
                
                # 편집 가능한 테스트케이스 표시
                for i, testcase in enumerate(testcases):
                    with st.expander(f"🧪 테스트케이스 {i+1}: {testcase.get('title', f'테스트케이스 {i+1}')}", expanded=(i == 0)):
                        
                        # 삭제 버튼 (상단 우측)
                        col1, col2 = st.columns([4, 1])
                        with col2:
                            if st.button("🗑️ 삭제", key=f"delete_tc_{i}", type="secondary", help="이 테스트케이스를 삭제합니다"):
                                st.session_state.editable_testcases.pop(i)
                                st.rerun()
                        
                        # 제목 편집
                        with col1:
                            new_title = st.text_input(
                                "📌 제목:",
                                value=testcase.get('title', f'테스트케이스 {i+1}'),
                                key=f"title_{i}"
                            )
                            testcase['title'] = new_title
                        
                        # 전제조건 편집
                        new_precondition = st.text_area(
                            "🔧 전제조건 (Precondition):",
                            value=testcase.get('precondition', '전제조건 없음'),
                            height=100,
                            key=f"precondition_{i}",
                            help="테스트 실행 전 준비되어야 할 조건들을 입력하세요"
                        )
                        testcase['precondition'] = new_precondition
                        
                        # 실행단계 편집
                        st.markdown("**▶️ 실행단계 (Steps):**")
                        steps = testcase.get('steps', [])
                        if isinstance(steps, list):
                            steps_text = '\n'.join(steps)
                        else:
                            steps_text = str(steps)
                        
                        new_steps_text = st.text_area(
                            "실행단계 (한 줄에 하나씩):",
                            value=steps_text,
                            height=120,
                            key=f"steps_{i}",
                            help="각 단계를 한 줄씩 입력하세요. 번호는 자동으로 추가됩니다."
                        )
                        
                        # 단계를 리스트로 변환
                        if new_steps_text.strip():
                            new_steps = [step.strip() for step in new_steps_text.split('\n') if step.strip()]
                            # 번호 자동 추가 (이미 번호가 있으면 제거 후 재추가)
                            formatted_steps = []
                            for j, step in enumerate(new_steps, 1):
                                # step이 None이거나 문자열이 아니면 빈 문자열로 처리, 아니면 str 변환
                                if step is None:
                                    step_str = ''
                                elif not isinstance(step, str):
                                    step_str = str(step)
                                else:
                                    step_str = step
                                try:
                                    step_clean = re.sub(r'^\d+\.\s*', '', step_str)
                                except Exception as e:
                                    st.warning(f"[디버그] step 변환 오류: type={type(step_str)}, 값={step_str}, 에러={e}")
                                    step_clean = step_str if isinstance(step_str, str) else ''
                                formatted_steps.append(f"{j}. {step_clean}")
                            testcase['steps'] = formatted_steps
                        else:
                            testcase['steps'] = []
                        
                        # 기대결과 편집
                        new_expectation = st.text_area(
                            "✅ 기대결과 (Expectation):",
                            value=testcase.get('expectation', '기대결과 없음'),
                            height=100,
                            key=f"expectation_{i}",
                            help="테스트 성공 시 예상되는 결과를 입력하세요"
                        )
                        testcase['expectation'] = new_expectation
                
                # 다운로드 기능
                st.markdown("---")
                st.markdown("### 💾 내보내기 및 관리")
                
                # 편집된 테스트케이스 수 표시
                st.info(f"📊 현재 **{len(testcases)}개**의 테스트케이스가 있습니다. 편집 내용이 자동으로 저장됩니다.")
                
                # 다운로드 파일 생성 (편집된 내용 사용)
                edited_description = st.session_state.get('edited_description', jira_task['description'])
                current_task_for_generation = jira_task.copy()
                current_task_for_generation['description'] = edited_description
                has_changes = edited_description != jira_task['description']
                
                testcase_text = f"Jira Task: {current_task_for_generation['key']} - {current_task_for_generation['summary']}\\n"
                testcase_text += f"Generated & Edited: AI-based Structured Test Cases\\n"
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
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button("⬅️ 생성 설정으로", type="secondary"):
                        # 편집된 테스트케이스 유지
                        st.session_state.current_step = 3
                        st.rerun()
                
                with col2:
                    st.download_button(
                        label="💾 편집된 테스트케이스 다운로드",
                        data=testcase_text,
                        file_name=f"edited_testcases_{current_task_for_generation['key']}.txt",
                        mime="text/plain",
                        help="편집한 모든 내용이 포함된 파일을 다운로드합니다"
                    )
                
                with col3:
                    if st.button("➡️ TestRail 등록", type="primary", disabled=len(testcases) == 0):
                        st.session_state.current_step = 6
                        st.rerun()
                
                with col4:
                    if st.button("🔄 새로 시작", type="secondary"):
                        # 세션 초기화
                        for key in ['current_step', 'current_jira_task', 'generated_testcases', 'editable_testcases', 'edited_description', 'task_key', 'test_count_ai', 'generation_started']:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.session_state.current_step = 1
                        st.rerun()
        
        # Step 6: TestRail 등록
        elif st.session_state.current_step == 6:
            st.markdown("## 🧪 6단계: TestRail 등록")
            
            if hasattr(st.session_state, 'editable_testcases'):
                testcases = st.session_state.editable_testcases
                jira_task = st.session_state.current_jira_task
                
                # TestRail 연결 확인
                testrail_connected = hasattr(st.session_state, 'testrail_connected') and st.session_state.testrail_connected
                
                if not testrail_connected:
                    st.error("❌ TestRail 연결이 필요합니다. 왼쪽 사이드바에서 TestRail 연결을 완료해주세요.")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("⬅️ 이전 단계", type="secondary"):
                            st.session_state.current_step = 5
                            st.rerun()
                    return
                
                st.success(f"✅ {len(testcases)}개의 테스트케이스를 TestRail에 등록할 준비가 되었습니다!")
                
                # 프로젝트 및 섹션 선택
                client = st.session_state.testrail_client
                
                # 프로젝트 목록 로드
                if 'testrail_projects' not in st.session_state:
                    with st.spinner("TestRail 프로젝트 목록을 가져오는 중..."):
                        projects = get_testrail_projects(client)
                        st.session_state.testrail_projects = projects
                
                projects = st.session_state.get('testrail_projects', [])
                
                if not projects:
                    st.error("❌ TestRail 프로젝트를 가져올 수 없습니다.")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("⬅️ 이전 단계", type="secondary"):
                            st.session_state.current_step = 5
                            st.rerun()
                    return
                
                # 프로젝트 목록이 있는지 확인
                if len(projects) == 0:
                    st.warning("⚠️ 사용 가능한 프로젝트가 없습니다.")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("⬅️ 이전 단계", type="secondary"):
                            st.session_state.current_step = 5
                            st.rerun()
                    return
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # 프로젝트 선택 - 안전한 처리
                    try:
                        project_options = {}
                        for p in projects:
                            if isinstance(p, dict) and 'id' in p and 'name' in p:
                                project_key = f"{p['name']} (ID: {p['id']})"
                                project_options[project_key] = p['id']
                            else:
                                st.warning(f"⚠️ 잘못된 프로젝트 데이터: {p}")
                        
                        if not project_options:
                            st.error("❌ 유효한 프로젝트가 없습니다.")
                            return
                        
                        selected_project_name = st.selectbox(
                            "📁 TestRail 프로젝트:",
                            options=list(project_options.keys()),
                            help="테스트케이스를 등록할 TestRail 프로젝트를 선택하세요"
                        )
                        selected_project_id = project_options[selected_project_name]
                        
                    except Exception as e:
                        st.error(f"❌ 프로젝트 선택 오류: {str(e)}")
                        
                        # 디버깅 토글
                        if st.button("🔍 디버깅 정보 보기", key="show_project_debug"):
                            st.session_state.show_testrail_debug = True
                            st.write("🔍 프로젝트 데이터:", projects)
                        return
                
                with col2:
                    # 스위트 목록 로드 (프로젝트 변경 시)
                    if ('selected_project_id' not in st.session_state or 
                        st.session_state.selected_project_id != selected_project_id):
                        
                        st.session_state.selected_project_id = selected_project_id
                        with st.spinner("스위트 목록을 가져오는 중..."):
                            suites = get_testrail_suites(client, selected_project_id)
                            st.session_state.testrail_suites = suites
                    
                    suites = st.session_state.get('testrail_suites', [])
                    
                    if suites:
                        try:
                            suite_options = {}
                            for s in suites:
                                if isinstance(s, dict) and 'id' in s and 'name' in s:
                                    # 완료된 스위트는 표시하지 않음
                                    if not s.get('is_completed', False):
                                        suite_key = f"{s['name']} (ID: {s['id']})"
                                        suite_options[suite_key] = s['id']
                                else:
                                    st.warning(f"⚠️ 잘못된 스위트 데이터: {s}")
                            
                            if suite_options:
                                selected_suite_name = st.selectbox(
                                    "📦 TestRail 스위트:",
                                    options=list(suite_options.keys()),
                                    help="테스트케이스를 등록할 스위트를 선택하세요"
                                )
                                selected_suite_id = suite_options[selected_suite_name]
                            else:
                                st.warning("⚠️ 사용 가능한 스위트가 없습니다.")
                                selected_suite_id = None
                                
                        except Exception as e:
                            st.error(f"❌ 스위트 선택 오류: {str(e)}")
                            
                            # 디버깅 토글
                            if st.button("🔍 디버깅 정보 보기", key="show_suite_debug"):
                                st.session_state.show_testrail_debug = True
                                st.write("🔍 스위트 데이터:", suites)
                            selected_suite_id = None
                    else:
                        st.warning("⚠️ 선택한 프로젝트에 스위트가 없습니다.")
                        selected_suite_id = None
                
                with col3:
                    # 섹션 목록 로드 (스위트 변경 시)
                    if (selected_suite_id and 
                        ('selected_suite_id' not in st.session_state or 
                         st.session_state.selected_suite_id != selected_suite_id)):
                        
                        st.session_state.selected_suite_id = selected_suite_id
                        with st.spinner("섹션 목록을 가져오는 중..."):
                            sections = get_testrail_sections(client, selected_project_id, selected_suite_id)
                            st.session_state.testrail_sections = sections
                    
                    sections = st.session_state.get('testrail_sections', [])
                    
                    if selected_suite_id and sections:
                        try:
                            section_options = {}
                            for s in sections:
                                if isinstance(s, dict) and 'id' in s and 'name' in s:
                                    section_key = f"{s['name']} (ID: {s['id']})"
                                    section_options[section_key] = s['id']
                                else:
                                    st.warning(f"⚠️ 잘못된 섹션 데이터: {s}")
                            
                            if section_options:
                                selected_section_name = st.selectbox(
                                    "📄 TestRail 섹션:",
                                    options=list(section_options.keys()),
                                    help="테스트케이스를 등록할 섹션을 선택하세요"
                                )
                                selected_section_id = section_options[selected_section_name]
                            else:
                                st.warning("⚠️ 유효한 섹션이 없습니다.")
                                selected_section_id = None
                                
                        except Exception as e:
                            st.error(f"❌ 섹션 선택 오류: {str(e)}")
                            
                            # 디버깅 토글
                            if st.button("🔍 디버깅 정보 보기", key="show_section_debug"):
                                st.session_state.show_testrail_debug = True
                                st.write("🔍 섹션 데이터:", sections)
                            selected_section_id = None
                    elif selected_suite_id:
                        st.info("⏳ 스위트를 선택하면 섹션 목록이 표시됩니다.")
                        selected_section_id = None
                    else:
                        st.info("💡 먼저 스위트를 선택해주세요.")
                        selected_section_id = None
                
                st.markdown("---")
                
                # 등록 옵션
                st.markdown("### 📋 등록 옵션")
                
                registration_mode = st.radio(
                    "등록 방식 선택:",
                    ["🔄 전체 등록", "☑️ 선택 등록"],
                    help="전체 등록: 모든 테스트케이스 등록, 선택 등록: 원하는 테스트케이스만 선택하여 등록"
                )
                
                # 선택 등록인 경우 체크박스 표시
                selected_testcases = []
                if registration_mode == "☑️ 선택 등록":
                    st.markdown("#### ☑️ 등록할 테스트케이스 선택:")
                    for i, testcase in enumerate(testcases):
                        if st.checkbox(
                            f"🧪 {testcase.get('title', f'테스트케이스 {i+1}')}",
                            key=f"select_tc_{i}",
                            value=True  # 기본값은 모두 선택
                        ):
                            selected_testcases.append((i, testcase))
                else:
                    selected_testcases = [(i, tc) for i, tc in enumerate(testcases)]
                
                # 등록 실행
                st.markdown("---")
                
                if selected_section_id and selected_testcases:
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        if st.button("⬅️ 이전 단계", type="secondary"):
                            st.session_state.current_step = 5
                            st.rerun()
                    
                    with col2:
                        if st.button(f"🚀 TestRail에 {len(selected_testcases)}개 등록", type="primary"):
                            success_count = 0
                            failure_count = 0
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            for i, (tc_index, testcase) in enumerate(selected_testcases):
                                status_text.text(f"등록 중: {testcase.get('title', f'테스트케이스 {tc_index+1}')}")
                                
                                if create_testrail_testcase(client, selected_section_id, testcase):
                                    success_count += 1
                                else:
                                    failure_count += 1
                                
                                progress_bar.progress((i + 1) / len(selected_testcases))
                            
                            progress_bar.progress(1.0)
                            
                            if failure_count == 0:
                                st.success(f"🎉 {success_count}개의 테스트케이스가 TestRail에 성공적으로 등록되었습니다!")
                                status_text.text("✅ 등록 완료!")
                            else:
                                st.warning(f"⚠️ {success_count}개 성공, {failure_count}개 실패")
                                status_text.text(f"⚠️ 일부 등록 실패: {failure_count}개")
                    
                    with col3:
                        if st.button("🔄 새로 시작", type="secondary"):
                            # 세션 초기화
                            for key in ['current_step', 'current_jira_task', 'generated_testcases', 'editable_testcases', 'edited_description', 'task_key', 'test_count_ai', 'generation_started', 'testrail_projects', 'testrail_suites', 'testrail_sections', 'selected_project_id', 'selected_suite_id']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.session_state.current_step = 1
                            st.rerun()
                else:
                    st.info("💡 등록할 섹션과 테스트케이스를 선택해주세요.")
    

    
    # 푸터
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            Made with ❤️ by AI 테스트케이스 생성기
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main() 