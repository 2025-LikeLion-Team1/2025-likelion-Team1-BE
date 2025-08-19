import json
from .. import crud, database, models  # DB와 상호작용하기 위해 crud, models 등을 가져옵니다.
from ..utils import ai_validator



# --------------------------------------------------------------------------
# 2. AI 파이프라인 메인 함수
# --------------------------------------------------------------------------

async def run_question_processing_pipeline():
    """
    주기적으로 실행될 AI 질문 처리 파이프라인입니다.
    'pending' 상태의 Raw 질문들을 가져와 그룹핑하고 요약하여 '대표 질문'을 생성합니다.
    """
    print("=" * 50)
    print("[AI Pipeline] 파이프라인 실행을 시작합니다.")

    # 데이터베이스 세션을 가져옵니다.
    db = database.get_db()

    # --- Step 1: 처리 대상 질문 가져오기 ---
    # 이 함수는 crud.py에 새로 만들어야 합니다.
    pending_questions = await crud.get_raw_questions_by_status(db, status=models.RawQuestionStatus.PENDING)

    ''' 테스트를 위한 가짜 질문 데이터
    pending_questions = [
        models.RawQuestionInDB(id=ObjectId(), content="강의 영상 화질이 너무 안 좋아요. 개선 계획 있나요?", author_id="user1",
                           status=models.RawQuestionStatus.PENDING),
        models.RawQuestionInDB(id=ObjectId(), content="VOD 퀄리티가 좀 떨어지는 것 같아요.", author_id="user2",
                           status=models.RawQuestionStatus.PENDING),
        models.RawQuestionInDB(id=ObjectId(), content="인턴십 프로그램 언제쯤 공지되나요?", author_id="user3",
                           status=models.RawQuestionStatus.PENDING),
        models.RawQuestionInDB(id=ObjectId(), content="기업 협력 인턴십 진행 상황이 궁금합니다.", author_id="user4",
                           status=models.RawQuestionStatus.PENDING),
        models.RawQuestionInDB(id=ObjectId(), content="강의 볼 때마다 버퍼링이 너무 심해요.", author_id="user5",
                           status=models.RawQuestionStatus.PENDING),
    ]
    '''

    # --- Step 2: 실행 조건 확인 ---
    # 실제로는 50개 이상일 때 실행하는 로직이 필요합니다.
    if not pending_questions:
        print("[AI Pipeline] 처리할 질문이 없습니다. 파이프라인을 종료합니다.")
        print("=" * 50)
        return

    print(f"[AI Pipeline] {len(pending_questions)}개의 처리 대기 질문을 발견했습니다.")

    # --- Step 3: 질문 요약 및 그룹핑을 위한 프롬프트 생성 ---
    # 모든 질문 내용을 하나의 문자열로 합칩니다.
    all_question_contents = "\n".join([f"- {q.content}" for q in pending_questions])

    # Gemini AI에게 보낼 프롬프트를 정교하게 설계합니다.
    prompt = f"""
        당신은 QnAHub 커뮤니티의 질문들을 분석하는 AI 어시스턴트입니다.
        아래에 사용자들이 남긴 여러 개의 질문 목록이 있습니다.
        이 질문들은 **이미 1차 검증을 통과한 유효한 질문들**입니다.
        이 질문들을 의미적으로 유사한 주제끼리 그룹핑하고, 각 그룹의 핵심 의도를 가장 잘 나타내는 '대표 질문'으로 요약해주세요.

        **[규칙]**
        1. 결과는 반드시 JSON 형식 `[ {{"representative_question": "...", "related_questions": [...]}} ]` 이어야 합니다.
        2. 완전히 다른 주제의 질문은 별개의 그룹으로 묶어주세요.

        **[사용자 질문 목록]**
        {all_question_contents}

        **[JSON 형식 결과]**
    """

    print("[AI Pipeline] Gemini AI에 대표 질문 요약을 요청합니다...")

    # --- Step 4: AI 모델 호출 및 결과 처리 ---
    try:
        # 모델에 프롬프트를 보내고 응답을 생성합니다.
        response = await ai_validator.MODEL.generate_content_async(prompt)
        ai_response_text = response.text
        print(f"[AI Pipeline] AI 응답 수신:\n{ai_response_text}")

        # --- 지금부터 이 코드를 추가합니다 ---

        # 1. AI가 보낸 JSON 형식의 '문자열'을 파이썬 '딕셔너리 리스트'로 변환합니다.
        #    (AI가 가끔 ```json ... ``` 같은 마크다운을 붙여 보낼 수 있으므로, 그것을 제거하는 처리 추가)
        cleaned_json_text = ai_response_text.strip().replace('```json', '').replace('```', '')
        representative_questions_data = json.loads(cleaned_json_text)

        # 2. crud 함수를 호출하여 DB에 저장하고, raw 질문 상태를 업데이트합니다.
        await crud.save_representative_questions_and_update_raw_status(
            db=db,
            representative_questions_data=representative_questions_data,
            processed_raw_questions=pending_questions
        )
        print("[AI Pipeline] 대표 질문 생성 및 저장이 완료되었습니다.")

    except json.JSONDecodeError:
        print("[AI Pipeline] AI 응답이 유효한 JSON 형식이 아닙니다. 저장을 건너뜁니다.")
    except Exception as e:
        # Google API에서 에러가 발생한 경우 처리
        print(f"[AI Pipeline] AI 모델 호출 중 심각한 오류 발생: {e}")

    finally:
        print("[AI Pipeline] 파이프라인 실행을 종료합니다.")
        print("=" * 50)