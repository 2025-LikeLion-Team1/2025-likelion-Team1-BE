from .. import crud, models
from typing import Optional
from ..utils.ai_client import gemini_client


async def find_most_similar_question(
        new_question_content: str,
        db
) -> Optional[models.RepresentativeQuestion]:  # 이제 단 하나의 객체 또는 None을 반환합니다.
    """
    새로운 질문과 가장 유사한 '단 하나'의 대표 질문을 찾아 반환합니다.
    유사한 질문이 없으면 None을 반환합니다.
    """

    existing_questions = await crud.get_all_rep_questions_for_similarity_check(db, limit=100)
    if not existing_questions:
        return None

    existing_questions_text = "\n".join(
        [f'- (id: "{q.id}") {q.title}' for q in existing_questions]
    )

    # 프롬프트를 '가장 유사한 것 하나만' 찾도록 수정합니다.
    prompt = f"""
        당신은 두 문장 간의 의미적 유사도를 판단하는 전문가입니다.
        아래에 '새로운 질문' 1개와 '기존 질문 목록'이 있습니다.
        '기존 질문 목록' 중에서 '새로운 질문'과 의미적으로 **가장 유사한 질문 딱 하나만** 골라, 그 질문의 'id'를 알려주세요.

        **[판단 기준]**
        - 묻고자 하는 핵심 의도가 거의 동일해야 합니다.
        - 만약 의미적으로 매우 유사한 질문이 없다면, **반드시 "None"** 이라고만 대답해주세요.

        ---
        **[새로운 질문]**
        "{new_question_content}"
        ---
        **[기존 질문 목록]**
        {existing_questions_text}
        ---

        **[가장 유사한 질문의 ID (하나만, 없으면 "None")]**
    """

    try:
        # 이 작업은 정확도가 중요하므로 Pro 모델을 사용하는 것을 권장합니다.
        ai_response_text = await gemini_client.generate_text(prompt, pro_model=True)

        # AI가 "None"을 반환했거나, 빈 문자열을 반환한 경우
        if not ai_response_text or ai_response_text.lower() == "none":
            return None

        # AI가 반환한 ID (문자열)
        most_similar_id = ai_response_text.strip()

        # ID에 해당하는 실제 질문 객체를 찾아서 반환합니다.
        for q in existing_questions:
            if str(q.id) == most_similar_id:
                # DB 모델(InDB)을 응답 모델로 변환하여 반환
                return models.RepresentativeQuestion.model_validate(q)

        # AI가 ID를 반환했지만, 목록에 없는 경우 (예: AI의 환각)
        return None

    except Exception as e:
        print(f"AI Similarity Check Error: {e}")
        return None