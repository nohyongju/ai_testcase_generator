import streamlit as st
import io
import sys
import json
import os
from typing import List, Dict, Optional
from atlassian import Jira
import re


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


def generate_test_ideas_from_jira(jira_task: Dict) -> List[str]:
    """Jira 태스크를 바탕으로 테스트케이스 아이디어를 생성합니다."""
    task_summary = jira_task['summary']
    task_description = jira_task['description']
    issue_type = jira_task['issue_type']
    
    # 기본 테스트 아이디어
    base_ideas = [
        f"[{jira_task['key']}] {task_summary} - 정상 기능 동작 확인",
        f"[{jira_task['key']}] {task_summary} - 잘못된 입력 데이터 처리",
        f"[{jira_task['key']}] {task_summary} - 경계값 및 임계값 테스트",
        f"[{jira_task['key']}] {task_summary} - 예외 상황 처리 확인",
        f"[{jira_task['key']}] {task_summary} - 성능 및 응답시간 테스트",
        f"[{jira_task['key']}] {task_summary} - 권한 및 보안 검증",
        f"[{jira_task['key']}] {task_summary} - UI/UX 동작 확인",
        f"[{jira_task['key']}] {task_summary} - 데이터 무결성 검증"
    ]
    
    # 이슈 타입별 추가 테스트
    if issue_type.lower() in ['bug', 'defect']:
        base_ideas.extend([
            f"[{jira_task['key']}] 버그 재현 테스트",
            f"[{jira_task['key']}] 버그 수정 후 회귀 테스트"
        ])
    elif issue_type.lower() in ['story', 'feature']:
        base_ideas.extend([
            f"[{jira_task['key']}] 사용자 시나리오 테스트",
            f"[{jira_task['key']}] 비즈니스 로직 검증"
        ])
    
    # 인수 조건 기반 테스트
    if jira_task['acceptance_criteria']:
        base_ideas.append(f"[{jira_task['key']}] 인수 조건 충족 확인")
    
    return base_ideas


def generate_basic_test_ideas(jira_task: Dict) -> List[str]:
    """기본 테스트케이스 아이디어만 생성합니다."""
    task_summary = jira_task['summary']
    
    return [
        f"[{jira_task['key']}] {task_summary} - 정상 기능 동작 확인",
        f"[{jira_task['key']}] {task_summary} - 잘못된 입력 데이터 처리",
        f"[{jira_task['key']}] {task_summary} - 경계값 및 임계값 테스트",
        f"[{jira_task['key']}] {task_summary} - 예외 상황 처리 확인",
        f"[{jira_task['key']}] {task_summary} - 성능 및 응답시간 테스트",
        f"[{jira_task['key']}] {task_summary} - 권한 및 보안 검증",
        f"[{jira_task['key']}] {task_summary} - UI/UX 동작 확인",
        f"[{jira_task['key']}] {task_summary} - 데이터 무결성 검증"
    ]


def generate_issue_type_specific_ideas(jira_task: Dict) -> List[str]:
    """이슈 타입별 특화 테스트케이스 아이디어를 생성합니다."""
    issue_type = jira_task['issue_type']
    ideas = []
    
    if issue_type.lower() in ['bug', 'defect']:
        ideas.extend([
            f"[{jira_task['key']}] 버그 재현 테스트",
            f"[{jira_task['key']}] 버그 수정 후 회귀 테스트",
            f"[{jira_task['key']}] 동일 유형 버그 검증",
            f"[{jira_task['key']}] 수정 영향범위 확인"
        ])
    elif issue_type.lower() in ['story', 'feature']:
        ideas.extend([
            f"[{jira_task['key']}] 사용자 시나리오 테스트",
            f"[{jira_task['key']}] 비즈니스 로직 검증",
            f"[{jira_task['key']}] 사용자 경험(UX) 테스트",
            f"[{jira_task['key']}] 기능 통합 테스트"
        ])
    elif issue_type.lower() in ['task', 'improvement']:
        ideas.extend([
            f"[{jira_task['key']}] 작업 완료 확인",
            f"[{jira_task['key']}] 개선 효과 검증"
        ])
    else:
        ideas.extend([
            f"[{jira_task['key']}] 일반 기능 테스트",
            f"[{jira_task['key']}] 요구사항 충족 확인"
        ])
    
    # 인수 조건이 있으면 추가
    if jira_task['acceptance_criteria']:
        ideas.append(f"[{jira_task['key']}] 인수 조건 충족 확인")
    
    return ideas


def generate_focus_area_tests(jira_task: Dict, focus_areas: List[str]) -> List[str]:
    """집중 테스트 영역별 테스트케이스를 생성합니다."""
    ideas = []
    task_summary = jira_task['summary']
    
    for area in focus_areas:
        if area == "보안":
            ideas.extend([
                f"[{jira_task['key']}] {task_summary} - 인증/인가 보안 테스트",
                f"[{jira_task['key']}] {task_summary} - 데이터 암호화 검증"
            ])
        elif area == "성능":
            ideas.extend([
                f"[{jira_task['key']}] {task_summary} - 응답시간 성능 테스트",
                f"[{jira_task['key']}] {task_summary} - 대용량 부하 테스트"
            ])
        elif area == "사용성":
            ideas.extend([
                f"[{jira_task['key']}] {task_summary} - 사용자 인터페이스 테스트",
                f"[{jira_task['key']}] {task_summary} - 사용자 경험 시나리오"
            ])
        elif area == "호환성":
            ideas.extend([
                f"[{jira_task['key']}] {task_summary} - 브라우저 호환성 테스트",
                f"[{jira_task['key']}] {task_summary} - 디바이스 호환성 검증"
            ])
        elif area == "접근성":
            ideas.extend([
                f"[{jira_task['key']}] {task_summary} - 웹 접근성 표준 준수",
                f"[{jira_task['key']}] {task_summary} - 스크린 리더 호환성"
            ])
        elif area == "데이터 무결성":
            ideas.extend([
                f"[{jira_task['key']}] {task_summary} - 데이터 일관성 검증",
                f"[{jira_task['key']}] {task_summary} - 트랜잭션 무결성 테스트"
            ])
        elif area == "오류 처리":
            ideas.extend([
                f"[{jira_task['key']}] {task_summary} - 예외 상황 처리 테스트",
                f"[{jira_task['key']}] {task_summary} - 오류 메시지 검증"
            ])
        elif area == "통합":
            ideas.extend([
                f"[{jira_task['key']}] {task_summary} - API 통합 테스트",
                f"[{jira_task['key']}] {task_summary} - 시스템 간 연동 검증"
            ])
    
    return ideas


def generate_context_based_tests(jira_task: Dict, context: str) -> List[str]:
    """추가 컨텍스트를 기반으로 테스트케이스를 생성합니다."""
    task_summary = jira_task['summary']
    
    # 컨텍스트에서 키워드 추출 및 테스트케이스 생성
    context_lower = context.lower()
    ideas = []
    
    if "모바일" in context_lower:
        ideas.append(f"[{jira_task['key']}] {task_summary} - 모바일 환경 테스트")
    
    if "대용량" in context_lower or "많은" in context_lower:
        ideas.append(f"[{jira_task['key']}] {task_summary} - 대용량 데이터 처리 테스트")
    
    if "브라우저" in context_lower:
        ideas.append(f"[{jira_task['key']}] {task_summary} - 특정 브라우저 환경 테스트")
    
    if "동시" in context_lower or "병렬" in context_lower:
        ideas.append(f"[{jira_task['key']}] {task_summary} - 동시성/병렬 처리 테스트")
    
    if "오프라인" in context_lower:
        ideas.append(f"[{jira_task['key']}] {task_summary} - 오프라인 상황 테스트")
    
    if "네트워크" in context_lower:
        ideas.append(f"[{jira_task['key']}] {task_summary} - 네트워크 환경 테스트")
    
    # 일반적인 컨텍스트 기반 테스트
    if not ideas:  # 특별한 키워드가 없으면 일반적인 컨텍스트 테스트 추가
        ideas.append(f"[{jira_task['key']}] {task_summary} - 특수 환경 테스트 ({context[:30]}...)")
    
    return ideas


def prioritize_tests(tests: List[str], priority_type: str) -> List[str]:
    """테스트케이스를 우선순위에 따라 정렬합니다."""
    if priority_type == "high":
        # 높은 우선순위: 정상 기능, 보안, 성능 먼저
        high_priority = []
        medium_priority = []
        low_priority = []
        
        for test in tests:
            test_lower = test.lower()
            if any(keyword in test_lower for keyword in ["정상", "기본", "보안", "성능"]):
                high_priority.append(test)
            elif any(keyword in test_lower for keyword in ["예외", "오류", "경계"]):
                medium_priority.append(test)
            else:
                low_priority.append(test)
        
        return high_priority + medium_priority + low_priority
    
    elif priority_type == "basic":
        # 기본 기능 우선
        basic_tests = [test for test in tests if "정상" in test or "기본" in test]
        other_tests = [test for test in tests if test not in basic_tests]
        return basic_tests + other_tests
    
    elif priority_type == "exception":
        # 예외 상황 우선
        exception_tests = [test for test in tests if any(keyword in test.lower() for keyword in ["예외", "오류", "버그", "경계"])]
        other_tests = [test for test in tests if test not in exception_tests]
        return exception_tests + other_tests
    
    else:  # 균등 분배
        return tests


def categorize_tests(tests: List[str]) -> Dict[str, List[str]]:
    """테스트케이스를 카테고리별로 분류합니다."""
    categories = {
        "🎯 기본 기능": [],
        "🔒 보안": [],
        "⚡ 성능": [],
        "🚨 예외 처리": [],
        "💻 UI/UX": [],
        "🔗 통합": [],
        "🐛 버그 관련": [],
        "📱 특수 환경": [],
        "🛠️ 기타": []
    }
    
    for test in tests:
        test_lower = test.lower()
        categorized = False
        
        # 기본 기능
        if any(keyword in test_lower for keyword in ["정상", "기본", "동작 확인"]):
            categories["🎯 기본 기능"].append(test)
            categorized = True
        
        # 보안
        elif any(keyword in test_lower for keyword in ["보안", "인증", "인가", "암호화"]):
            categories["🔒 보안"].append(test)
            categorized = True
        
        # 성능
        elif any(keyword in test_lower for keyword in ["성능", "응답시간", "부하", "대용량"]):
            categories["⚡ 성능"].append(test)
            categorized = True
        
        # 예외 처리
        elif any(keyword in test_lower for keyword in ["예외", "오류", "에러", "경계값", "잘못된"]):
            categories["🚨 예외 처리"].append(test)
            categorized = True
        
        # UI/UX
        elif any(keyword in test_lower for keyword in ["ui", "ux", "사용자", "인터페이스", "접근성"]):
            categories["💻 UI/UX"].append(test)
            categorized = True
        
        # 통합
        elif any(keyword in test_lower for keyword in ["통합", "api", "연동", "시스템"]):
            categories["🔗 통합"].append(test)
            categorized = True
        
        # 버그 관련
        elif any(keyword in test_lower for keyword in ["버그", "재현", "회귀", "수정"]):
            categories["🐛 버그 관련"].append(test)
            categorized = True
        
        # 특수 환경
        elif any(keyword in test_lower for keyword in ["모바일", "브라우저", "오프라인", "네트워크", "호환성"]):
            categories["📱 특수 환경"].append(test)
            categorized = True
        
        # 기타
        if not categorized:
            categories["🛠️ 기타"].append(test)
    
    # 빈 카테고리 제거
    return {k: v for k, v in categories.items() if v}


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
                    st.success("🔄 자동 연결 성공!")
    
    # 도구 선택
    st.sidebar.header("🛠️ 도구 선택")
    tool_choice = st.sidebar.selectbox(
        "생성 도구를 선택하세요:",
        ["Jira 태스크 기반 테스트케이스 아이디어 생성", "Jira 태스크 기반 유닛테스트 템플릿 생성"]
    )
    
    # 기본 테스트 개수 설정
    default_test_count = 5
    if config and 'app' in config:
        default_test_count = config['app'].get('default_test_count', 5)
    
    # 메인 컨텐츠
    if tool_choice == "Jira 태스크 기반 테스트케이스 아이디어 생성":
        st.header("💡 Jira 태스크 기반 테스트케이스 아이디어 생성")
        
        # 입력 섹션
        col1, col2 = st.columns([3, 1])
        
        with col1:
            task_key = st.text_input(
                "Jira 태스크 키를 입력하세요:",
                placeholder="예: PROJ-123, DEV-456, BUG-789"
            )
        
        with col2:
            st.markdown("### 🎯 Jira 태스크 활용 팁")
            st.markdown("""
            - 태스크 키 형식: PROJ-123
            - 태스크 요약과 설명을 분석
            - 인수 조건(AC)을 자동 추출
            - 이슈 타입별 맞춤 테스트 생성
            - 우선순위를 고려한 테스트 계획
            """)
        
        # 1단계: 태스크 읽기
        if st.button("📖 Jira 태스크 읽기", type="primary"):
            if not hasattr(st.session_state, 'jira_connected') or not st.session_state.jira_connected:
                st.error("❌ 먼저 Jira에 연결해주세요!")
            elif task_key.strip():
                with st.spinner("Jira 태스크를 조회 중..."):
                    jira_task = get_jira_task(st.session_state.jira_client, task_key.strip())
                    
                    if jira_task:
                        # 태스크 정보를 세션에 저장
                        st.session_state.current_jira_task = jira_task
                        st.success(f"✅ Jira 태스크 '{task_key}' 조회 성공!")
                    else:
                        if 'current_jira_task' in st.session_state:
                            del st.session_state.current_jira_task
            else:
                st.warning("⚠️ Jira 태스크 키를 입력해주세요!")
        
        # 태스크 정보 표시 (읽기 성공 시)
        if hasattr(st.session_state, 'current_jira_task') and st.session_state.current_jira_task:
            jira_task = st.session_state.current_jira_task
            
            # 태스크 정보를 더 잘 보이게 개선
            st.markdown("### 📋 읽어온 Jira 태스크")
            
            # 메인 정보 (크게 표시)
            st.markdown(f"**🎯 [{jira_task['key']}] {jira_task['summary']}**")
            
            # 메타 정보 (작게 표시)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"📊 상태: **{jira_task['status']}**")
            with col2:
                st.caption(f"⚡ 우선순위: **{jira_task['priority']}**")
            with col3:
                st.caption(f"🏷️ 타입: **{jira_task['issue_type']}**")
            
            # 편집 가능한 설명
            st.markdown("### ✏️ 태스크 설명 편집")
            st.info("💡 아래 설명을 편집하면 테스트케이스 생성 시 편집된 내용이 반영됩니다.")
            
            # 편집 가능한 설명
            edited_description = st.text_area(
                "📄 설명 (편집 가능)",
                value=st.session_state.get('edited_description', jira_task['description']),
                height=200,
                help="이 설명은 테스트케이스 생성에 사용됩니다. 필요시 수정하세요.",
                key="description_editor"
            )
            
            # 편집된 정보를 반영한 태스크 객체 생성
            current_task_for_generation = jira_task.copy()
            current_task_for_generation['description'] = edited_description
            
            # 변경사항 확인
            has_changes = edited_description != jira_task['description']
            
            # 2단계: 테스트케이스 생성 설정
            st.markdown("---")
            st.markdown("### 🧪 테스트케이스 생성 설정")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # 기본 생성 옵션
                generate_type = st.selectbox(
                    "기본 생성 유형:",
                    ["기본 8개 + 이슈타입별", "기본 8개만", "이슈타입별만", "인수조건 포함 전체"]
                )
                
                # 사용자 추가 설정
                st.markdown("#### 🎨 추가 설정")
                
                additional_context = st.text_area(
                    "추가 컨텍스트 (선택사항):",
                    placeholder="특별히 고려해야 할 시나리오나 요구사항을 입력하세요...\n예: 모바일 환경, 대용량 데이터, 특정 브라우저 등",
                    height=80
                )
                
                focus_areas = st.multiselect(
                    "집중 테스트 영역 선택:",
                    ["보안", "성능", "사용성", "호환성", "접근성", "데이터 무결성", "오류 처리", "통합"],
                    default=[]
                )
                
                test_priority = st.selectbox(
                    "테스트 우선순위 기준:",
                    ["높음 우선", "균등 분배", "기본 기능 우선", "예외 상황 우선"]
                )
            
            with col2:
                st.markdown("#### 📊 생성 예상")
                base_count = 8
                if generate_type == "기본 8개 + 이슈타입별":
                    expected_count = base_count + (2 if current_task_for_generation['issue_type'].lower() in ['bug', 'defect', 'story', 'feature'] else 0)
                    if current_task_for_generation['acceptance_criteria']:
                        expected_count += 1
                elif generate_type == "기본 8개만":
                    expected_count = base_count
                elif generate_type == "이슈타입별만":
                    expected_count = 2 if current_task_for_generation['issue_type'].lower() in ['bug', 'defect', 'story', 'feature'] else 0
                else:  # 전체
                    expected_count = base_count + (2 if current_task_for_generation['issue_type'].lower() in ['bug', 'defect', 'story', 'feature'] else 0)
                    if current_task_for_generation['acceptance_criteria']:
                        expected_count += 1
                
                # 추가 설정에 따른 예상 개수 증가
                additional_count = len(focus_areas) + (1 if additional_context.strip() else 0)
                total_expected = expected_count + additional_count
                
                st.metric("기본 테스트케이스", expected_count)
                if additional_count > 0:
                    st.metric("추가 테스트케이스", additional_count)
                st.metric("🎯 총 예상 개수", total_expected)
                
                # 편집 상태 표시
                if has_changes:
                    st.info("ℹ️ 편집된 설명이 반영됩니다")
            
            # 테스트케이스 생성 버튼
            if st.button("🚀 테스트케이스 생성", type="secondary", use_container_width=True):
                with st.spinner("편집된 정보를 바탕으로 맞춤형 테스트케이스를 생성 중..."):
                    # 기본 테스트케이스 생성 (편집된 정보 사용)
                    if generate_type == "기본 8개만":
                        ideas = generate_basic_test_ideas(current_task_for_generation)
                    elif generate_type == "이슈타입별만":
                        ideas = generate_issue_type_specific_ideas(current_task_for_generation)
                    else:
                        ideas = generate_test_ideas_from_jira(current_task_for_generation)
                    
                    # 추가 설정 기반 테스트케이스 생성
                    if focus_areas:
                        additional_ideas = generate_focus_area_tests(current_task_for_generation, focus_areas)
                        ideas.extend(additional_ideas)
                    
                    if additional_context.strip():
                        context_ideas = generate_context_based_tests(current_task_for_generation, additional_context.strip())
                        ideas.extend(context_ideas)
                    
                    # 우선순위에 따른 정렬
                    if test_priority == "높음 우선":
                        ideas = prioritize_tests(ideas, "high")
                    elif test_priority == "기본 기능 우선":
                        ideas = prioritize_tests(ideas, "basic")
                    elif test_priority == "예외 상황 우선":
                        ideas = prioritize_tests(ideas, "exception")
                    
                    st.success(f"✅ {len(ideas)}개의 맞춤형 테스트케이스가 생성되었습니다!")
                    
                    # 편집 정보 표시
                    if has_changes:
                        st.info("ℹ️ 편집된 태스크 설명이 반영되었습니다.")
                    
                    # 결과 출력 (카테고리별로 분류)
                    st.markdown("### 📝 생성된 테스트케이스")
                    
                    # 카테고리별 분류
                    categorized_tests = categorize_tests(ideas)
                    
                    for category, tests in categorized_tests.items():
                        if tests:
                            with st.expander(f"🏷️ {category} ({len(tests)}개)", expanded=True):
                                for i, test in enumerate(tests, 1):
                                    st.markdown(f"**{i}.** {test}")
                    
                    # 사용자 추가/편집 기능
                    st.markdown("---")
                    st.markdown("### ✏️ 테스트케이스 추가/편집")
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        custom_test = st.text_input(
                            "추가 테스트케이스:",
                            placeholder=f"[{current_task_for_generation['key']}] 사용자 정의 테스트케이스..."
                        )
                    with col2:
                        if st.button("➕ 추가") and custom_test.strip():
                            if 'custom_tests' not in st.session_state:
                                st.session_state.custom_tests = []
                            st.session_state.custom_tests.append(custom_test.strip())
                            st.success("추가됨!")
                            st.rerun()
                    
                    # 사용자 추가 테스트케이스 표시
                    if hasattr(st.session_state, 'custom_tests') and st.session_state.custom_tests:
                        st.markdown("#### 👤 사용자 추가 테스트케이스")
                        for i, custom in enumerate(st.session_state.custom_tests):
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.markdown(f"**{len(ideas) + i + 1}.** {custom}")
                            with col2:
                                if st.button("🗑️", key=f"delete_{i}"):
                                    st.session_state.custom_tests.pop(i)
                                    st.rerun()
                    
                    # 전체 다운로드 기능
                    all_ideas = ideas.copy()
                    if hasattr(st.session_state, 'custom_tests'):
                        all_ideas.extend(st.session_state.custom_tests)
                    
                    ideas_text = f"Jira Task: {current_task_for_generation['key']} - {current_task_for_generation['summary']}\\n"
                    ideas_text += f"Generated Type: {generate_type}\\n"
                    ideas_text += f"Focus Areas: {', '.join(focus_areas) if focus_areas else 'None'}\\n"
                    ideas_text += f"Priority: {test_priority}\\n"
                    if has_changes:
                        ideas_text += "✏️ Edited Description Used\\n"
                    if additional_context.strip():
                        ideas_text += f"Additional Context: {additional_context.strip()}\\n"
                    ideas_text += f"Total Count: {len(all_ideas)}\\n\\n"
                    
                    # 카테고리별로 출력
                    for category, tests in categorized_tests.items():
                        if tests:
                            ideas_text += f"\\n=== {category} ===\\n"
                            for i, test in enumerate(tests, 1):
                                ideas_text += f"{i}. {test}\\n"
                    
                    if hasattr(st.session_state, 'custom_tests') and st.session_state.custom_tests:
                        ideas_text += f"\\n=== 사용자 추가 테스트케이스 ===\\n"
                        for i, custom in enumerate(st.session_state.custom_tests, 1):
                            ideas_text += f"{i}. {custom}\\n"
                    
                    st.download_button(
                        label="💾 전체 테스트케이스 다운로드",
                        data=ideas_text,
                        file_name=f"testcase_comprehensive_{current_task_for_generation['key']}.txt",
                        mime="text/plain"
                    )
    
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