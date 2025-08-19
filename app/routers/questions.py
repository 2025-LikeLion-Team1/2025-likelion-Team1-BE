from fastapi import APIRouter, Depends, status, HTTPException
from typing import List
from .. import crud, models, database
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..utils import ai_validator

# --- 라우터 설정 ---
router = APIRouter(
    prefix="/questions",
    tags=["Questions"]
)


# --------------------------------------------------------------------------
# 1. Raw 질문 제출 API
# --------------------------------------------------------------------------
@router.post("/raw",
             # 이제 응답 모델도 RawQuestionInDB를 그대로 사용해도,
             # PyObjectId가 알아서 id를 str으로 변환해줍니다.
             response_model=models.RawQuestionInDB,
             status_code=status.HTTP_201_CREATED,
             summary="사용자의 Raw 질문 제출")
async def submit_raw_question(
        question_data: models.RawQuestionCreate,
        db: AsyncIOMotorDatabase = Depends(database.get_db)
):
    """
    사용자의 질문을 제출받아, AI로 1차 필터링 후 저장합니다.
    """
    # --- 1. AI 실시간 유효성 검사 ---
    is_valid, reason = await ai_validator.validate_question_content(question_data.content)

    if not is_valid:
        # 유효하지 않은 질문이면, 400 Bad Request 에러를 반환하며 왜 거절되었는지 알려줌
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 질문입니다. 이유: {reason}"
        )

    # --- 2. (선택적) 실시간 유사 질문 검색 ---
    # 이제 질문이 유효하다는 것을 알았으니, 유사 질문을 찾아 사용자에게 보여줄 수 있습니다.
    # similar_questions = await ai_utils.find_similar_questions(question_data.content)

    # --- 3. 유효한 질문만 DB에 저장 ---
    # 이제 crud.create_raw_question은 무조건 'pending' 상태로 저장하면 됩니다.
    created_question = await crud.create_raw_question(db=db, question_data=question_data)

    # 프론트엔드에는 생성된 질문 객체와 함께, 유사 질문 목록을 함께 보내줄 수 있습니다.
    return created_question


# --------------------------------------------------------------------------
# 2. 대표 질문 조회 API
# --------------------------------------------------------------------------
@router.get("/representative",
            # 응답 모델 타입도 List[models.RepresentativeQuestionInDB]로 바꿔도 무방합니다.
            # 하지만 역할 분리를 위해 RepresentativeQuestion을 그대로 사용하는 것이 더 명확합니다.
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
    # crud 함수가 반환한 DB 모델 객체 리스트를 그냥 그대로 반환하면 끝입니다.
    # FastAPI와 Pydantic이 리스트의 각 항목을 알아서 RepresentativeQuestion 모델로 변환하고,
    # PyObjectId가 id를 str으로 변환해줍니다.
    return await crud.get_all_representative_questions(db=db, skip=skip, limit=limit)