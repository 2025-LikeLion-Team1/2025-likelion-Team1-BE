import google.generativeai as genai
import os
from typing import Tuple

# --------------------------------------------------------------------------
# 1. AI 모델 초기화 및 설정
# --------------------------------------------------------------------------

# .env 파일에서 API 키를 불러옵니다. (main.py가 아닌 여기서 직접 설정)
# 이 파일이 독립적으로 실행될 수도 있기 때문입니다.
try:
    # 이 파일은 app/tasks/ 안에 있으므로, .env 파일은 두 단계 상위 폴더에 있습니다.
    # from dotenv import load_dotenv
    # load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    # 위 방식이 복잡하다면, FastAPI가 시작될 때 이미 로드되므로 그냥 os.getenv만 사용해도 됩니다.
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set.")
    genai.configure(api_key=GOOGLE_API_KEY)
except (ValueError, TypeError) as e:
    raise RuntimeError(f"Failed to configure Google AI: {e}")

# 사용할 Gemini 모델을 초기화합니다.
MODEL = genai.GenerativeModel('gemini-1.5-flash')


async def validate_question_content(content: str) -> Tuple[bool, str]:
    """
    AI를 이용해 질문 내용이 유효한지 검사합니다.
    반환값: (True/False, "이유")
    """
    prompt = f"""
        당신은 QnAHub 커뮤니티의 엄격한 관리자입니다.
        사용자가 제출한 다음 질문이 커뮤니티에 등록될 만한 가치가 있는지 판단해주세요.

        **[판단 기준]**
        아래 중 하나라도 해당되면 '부적합'입니다:
        - 단순한 감정 표현 (예: "좋아요", "심심하다")
        - 커뮤니티와 관련 없는 개인적인 잡담 (예: "오늘 저녁 뭐 먹죠?")
        - 욕설, 비방, 광고 등 부적절한 내용
        - 의미를 알 수 없는 단어나 문장

        **[사용자 질문]**
        "{content}"

        **[판단 결과]**
        먼저 '적합' 또는 '부적합'이라고만 대답해주세요.
        만약 '부적합'이라면, 그 이유를 한 문장으로 간결하게 설명해주세요.
        (예: 부적합. 단순한 감정 표현입니다.)
    """
    try:
        response = await MODEL.generate_content_async(prompt)
        result_text = response.text.strip()

        if result_text.startswith("적합"):
            return True, "적합한 질문입니다."
        elif result_text.startswith("부적합"):
            # "부적합." 이후의 이유 부분을 추출합니다.
            reason = result_text.replace("부적합.", "").strip()
            return False, reason
        else:
            # AI가 예상과 다른 답변을 한 경우, 일단 통과시킵니다. (안전장치)
            return True, "AI 판단 불가"

    except Exception as e:
        print(f"AI Validator Error: {e}")
        # AI 시스템에 문제가 생긴 경우, 일단 통과시켜서 서비스 장애를 막습니다.
        return True, "AI 검증 시스템 오류"