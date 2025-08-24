from fastapi import APIRouter, Depends, status, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum
from .. import crud, models, database
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..utils import ai_validator, ai_similarity_checker

# --- 라우터 설정 ---
router = APIRouter(
    prefix="/questions",
    tags=["Questions"]
)


# --- 새로운 응답 모델 및 Enum 정의 ---
class QuestionSubmissionStatus(str, Enum):
    NEW_QUESTION_SUBMITTED = "new_question_submitted"
    SIMILAR_QUESTION_FOUND = "similar_question_found"

class SubmitQuestionResponse(BaseModel):
    status: QuestionSubmissionStatus
    message: str
    submitted_question: Optional[models.RawQuestionInDB] = None
    similar_question: Optional[models.RepresentativeQuestion] = None


# --------------------------------------------------------------------------
# 1. Raw 질문 제출 API (업그레이드 버전)
# --------------------------------------------------------------------------
@router.post("/raw",
             response_model=SubmitQuestionResponse,
             status_code=status.HTTP_200_OK,  # 이제는 선택지를 제공하므로 200 OK가 더 적합
             summary="사용자 질문 예비 검토 및 옵션 제공")
async def submit_or_check_raw_question(
        question_data: models.RawQuestionCreate,
        # 'force' 쿼리 파라미터를 추가하여 사용자가 강제 등록을 원할 때를 처리합니다.
        force: bool = Query(False, description="유사 질문 경고를 무시하고 강제로 새 질문을 등록합니다."),
        db: AsyncIOMotorDatabase = Depends(database.get_db)
):
    """
    사용자의 질문을 제출받아 유효성을 검사하고, 유사 질문을 찾습니다.
    - 유사 질문이 없거나 `force=true`이면, 새 질문을 등록합니다.
    - 유사 질문이 있으면, 사용자에게 선택지를 제공합니다.
    """
    # --- 1. AI 유효성 검사 ---
    is_valid, reason = await ai_validator.validate_question_content(question_data.content)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 질문입니다. 이유: {reason}"
        )

    # --- 2. 'force' 옵션이 없는 경우에만 유사 질문 검색 ---
    if not force:
        similar_question = await ai_similarity_checker.find_most_similar_question(
            new_question_content=question_data.content,
            db=db
        )

        # 유사 질문을 찾았다면, DB에 저장하지 않고 선택지를 반환
        if similar_question:
            return SubmitQuestionResponse(
                status=QuestionSubmissionStatus.SIMILAR_QUESTION_FOUND,
                message="매우 유사한 질문이 이미 존재합니다. 기존 질문에 공감하시거나, 새로운 질문으로 등록해주세요.",
                similar_question=similar_question
            )

    # --- 3. 유사 질문이 없거나, 사용자가 강제 등록을 원할 경우 ---

    # DB에 저장할 최종 데이터 객체를 만듭니다.
    # 사용자가 보낸 데이터에, 서버에서 결정한 force_submitted 값을 추가합니다.
    final_question_data = models.RawQuestionCreate(
        content=question_data.content,
        author_id=question_data.author_id,
        force_submitted=force  # <- 바로 이 부분!
    )

    created_question = await crud.create_raw_question(db=db, question_data=final_question_data)

    return SubmitQuestionResponse(
        status=QuestionSubmissionStatus.NEW_QUESTION_SUBMITTED,
        message="새로운 질문으로 정상 접수되었습니다.",
        submitted_question=created_question
    )


# --------------------------------------------------------------------------
# 2. 대표 질문 조회 API (기존과 동일)
# --------------------------------------------------------------------------
@router.get("/representative",
            response_model=List[models.RepresentativeQuestion],
            summary="대표 질문 목록 조회")
async def get_representative_questions(
        skip: int = 0,
        limit: int = 10,
        db: AsyncIOMotorDatabase = Depends(database.get_db)
):
    """
    AI에 의해 생성된 '대표 질문' 목록을 조회합니다.
    '뜨고 있는 질문' UI에 사용됩니다.
    - **skip**: 건너뛸 질문 수
    - **limit**: 가져올 최대 질문 수
    """
    return await crud.get_all_representative_questions(db=db, skip=skip, limit=limit)