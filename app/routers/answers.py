from fastapi import APIRouter, Depends, status, HTTPException
from .. import crud, models, database
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

router = APIRouter(
    prefix="/answers",
    tags=["Answers (Admin)"]
)


# --- 답변 생성 API ---
@router.post("/", response_model=models.Answer, status_code=status.HTTP_201_CREATED, summary="대표 질문에 대한 답변 생성")
async def create_answer(
        answer_data: models.AnswerCreate,
        db: AsyncIOMotorDatabase = Depends(database.get_db)
        # 나중에 여기에 , current_user: User = Depends(get_admin_user) 와 같이 관리자 인증 추가
):
    """
    특정 대표 질문에 대한 공식 답변을 생성합니다. (관리자용)
    답변이 생성되면, 해당 질문의 상태는 'answered'로 변경됩니다.
    """
    # 먼저, 답변하려는 질문이 존재하는지 확인
    question_exists = await crud.get_representative_question_by_id(db, answer_data.representative_question_id)

    # --- 디버깅용 print문 추가 ---
    print("="*50)
    print(f"[API: create_answer] 함수가 호출되었습니다.")
    print(f"[API] 찾으려는 질문 ID (타입: {type(answer_data.representative_question_id)}): {answer_data.representative_question_id}")
    print("="*50)
    # --- 여기까지 ---
    if not question_exists:
        raise HTTPException(status_code=404, detail="답변하려는 질문을 찾을 수 없습니다.")

    # 이미 답변이 달렸는지 확인
    existing_answer = await crud.get_answer_for_question(db, answer_data.representative_question_id)
    if existing_answer:
        raise HTTPException(status_code=400, detail="이미 해당 질문에 대한 답변이 존재합니다.")

    created_answer = await crud.create_answer_for_question(db=db, answer_data=answer_data)
    return created_answer


# --- 특정 질문의 답변 조회 API (질문 정보 포함) ---
@router.get("/by-question/{question_id}",
            # 1. 응답 모델을 QuestionAndAnswer로 변경합니다.
            response_model=models.QuestionAndAnswer,
            summary="특정 질문과 그에 대한 답변 함께 조회")
async def get_answer_by_question_id(
        question_id: models.PyObjectId,
        db: AsyncIOMotorDatabase = Depends(database.get_db)
):
    """주어진 대표 질문 ID에 해당하는 질문과 답변을 함께 조회합니다."""

    # 2. 먼저, 해당 질문에 대한 답변을 찾습니다.
    db_answer = await crud.get_answer_for_question(db=db, question_id=question_id)
    if not db_answer:
        raise HTTPException(status_code=404, detail="해당 질문에 대한 답변을 찾을 수 없습니다.")

    # 3. 그 다음, 질문 자체의 정보를 찾습니다.
    db_question = await crud.get_representative_question_by_id(db=db, question_id=question_id)
    if not db_question:
        # 이 경우는 데이터 정합성이 깨진 상황이지만, 일단 404로 처리합니다.
        raise HTTPException(status_code=404, detail="답변에 연결된 질문을 찾을 수 없습니다.")

    # IDE가 이해할 수 있도록, DB 모델을 응답 모델로 명시적으로 변환합니다.
    response_question = models.RepresentativeQuestion.model_validate(db_question)
    response_answer = models.Answer.model_validate(db_answer)

    # 4. 두 데이터를 QuestionAndAnswer 모델에 담아 반환합니다.
    #    Pydantic이 DB 모델(InDB)을 응답 모델로 알아서 변환해줍니다.
    return models.QuestionAndAnswer(
        question=response_question,
        answer=response_answer
    )

# --- 모든 답변 목록 조회 API (페이지네이션) ---
@router.get("/", response_model=List[models.QuestionAndAnswer], summary="답변된 질문과 답변 목록 조회 (최신순)")
async def get_answered_questions_list(
    skip: int = 0,
    limit: int = 10,
    db: AsyncIOMotorDatabase = Depends(database.get_db)
):
    """
    답변이 완료된 질문과 답변의 목록을 최신순으로 조회합니다.
    메인 페이지의 '최근 올라온 답변' UI에 사용됩니다.
    - **skip**: 건너뛸 문서의 수
    - **limit**: 반환할 최대 문서의 수
    """
    # crud 함수가 반환한 딕셔너리 리스트를 그대로 반환하면,
    # Pydantic이 response_model(QuestionAndAnswer)에 맞춰 자동으로 검증하고 변환해줍니다.
    answered_qas = await crud.get_all_answered_questions(db=db, skip=skip, limit=limit)
    return answered_qas