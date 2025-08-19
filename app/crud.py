from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from . import models
from bson import ObjectId
from bson.errors import InvalidId

# 컬렉션 이름 정의
COMMUNITY_COLLECTION = "community_posts"
RAW_QUESTIONS_COLLECTION = "raw_questions"
REPRESENTATIVE_QUESTIONS_COLLECTION = "representative_questions"

# --- CREATE (생성) ---
async def create_post(db: AsyncIOMotorDatabase, post_data: models.PostCreate) -> models.PostInDB:
    """새로운 게시글을 데이터베이스에 생성합니다."""

    # Pydantic 모델을 딕셔너리로 변환합니다. DB에 저장할 것이므로 mode='python'이 적합합니다.
    # (기본값이 'python'이므로 생략 가능)
    post_dict = post_data.model_dump()

    post_dict['likes'] = 0

    result = await db[COMMUNITY_COLLECTION].insert_one(post_dict)

    created_post = await db[COMMUNITY_COLLECTION].find_one({"_id": result.inserted_id})

    return models.PostInDB(**created_post)

# --- READ (읽기) ---
async def get_all_posts(db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 10) -> List[models.PostInDB]:
    """모든 게시글을 페이지네이션하여 조회합니다."""

    posts = []
    # .sort("_id", -1) -> 최신 글 순서로 정렬 (내림차순)
    # .skip(skip) -> 특정 개수만큼 건너뛰기 (페이지네이션)
    # .limit(limit) -> 최대 개수 제한 (페이지네이션)
    cursor = db[COMMUNITY_COLLECTION].find().sort("_id", -1).skip(skip).limit(limit)

    async for post in cursor:
        posts.append(models.PostInDB(**post))

    return posts


async def get_post_by_id(db: AsyncIOMotorDatabase, post_id: str) -> Optional[models.PostInDB]:
    """ID로 특정 게시글 하나를 조회합니다."""
    try:
        # 이 부분에서 InvalidId 예외가 발생할 수 있습니다.
        oid = ObjectId(post_id)
        post = await db[COMMUNITY_COLLECTION].find_one({"_id": oid})
        if post:
            return models.PostInDB(**post)
        return None  # 게시글이 없으면 None을 반환
    except InvalidId:
        # ObjectId 형식 자체가 잘못된 경우, 게시글이 없는 것과 동일하게 취급합니다.
        return None


# ---UPDATE (수정)---
async def update_post(db: AsyncIOMotorDatabase, post_id: str, post_data: models.PostUpdate) -> Optional[models.PostInDB]:
    """ID로 특정 게시글을 수정합니다."""

    # model_dump(exclude_unset=True) 옵션을 사용하면,
    # 사용자가 명시적으로 설정하지 않은 필드(기본값=None)를 알아서 제외해 줍니다.
    # 이전의 복잡한 딕셔너리 컴프리헨션보다 훨씬 깔끔하고 의도가 명확합니다.
    update_data = post_data.model_dump(exclude_unset=True)

    if len(update_data) >= 1:
        # $set 연산자를 사용하여 지정된 필드만 업데이트합니다.
        await db[COMMUNITY_COLLECTION].update_one(
            {"_id": ObjectId(post_id)},
            {"$set": update_data}
        )

    # 수정된 최신 문서를 다시 찾아서 반환합니다.
    # 'None'을 반환할 수 있으므로, 라우터에서 예외 처리를 해야 합니다.
    updated_post = await get_post_by_id(db, post_id)
    return updated_post


# DELETE 삭제
async def delete_post(db: AsyncIOMotorDatabase, post_id: str) -> bool:
    """ID로 특정 게시글을 삭제합니다."""

    result = await db[COMMUNITY_COLLECTION].delete_one({"_id": ObjectId(post_id)})

    # result.deleted_count가 1이면 성공적으로 삭제된 것입니다.
    return result.deleted_count == 1

# ------------------------------------


# --------------------------------------------------------------------------
# RawQuestion CRUD 함수
# --------------------------------------------------------------------------

async def create_raw_question(db: AsyncIOMotorDatabase,
                              question_data: models.RawQuestionCreate) -> models.RawQuestionInDB:
    """새로운 Raw 질문을 데이터베이스에 생성합니다."""
    question_dict = question_data.model_dump()
    result = await db[RAW_QUESTIONS_COLLECTION].insert_one(question_dict)
    created_question = await db[RAW_QUESTIONS_COLLECTION].find_one({"_id": result.inserted_id})
    return models.RawQuestionInDB(**created_question)


async def get_raw_questions_by_status(db: AsyncIOMotorDatabase, status: models.RawQuestionStatus, limit: int = 100) -> \
List[models.RawQuestionInDB]:
    """특정 상태의 Raw 질문들을 조회합니다."""
    questions = []
    cursor = db[RAW_QUESTIONS_COLLECTION].find({"status": status.value}).limit(limit)
    async for question in cursor:
        questions.append(models.RawQuestionInDB(**question))
    return questions


# --------------------------------------------------------------------------
# RepresentativeQuestion 및 파이프라인 관련 함수
# --------------------------------------------------------------------------

async def save_representative_questions_and_update_raw_status(
        db: AsyncIOMotorDatabase,
        representative_questions_data: List[dict],  # AI가 생성한 JSON 데이터 리스트
        processed_raw_questions: List[models.RawQuestionInDB]  # 처리에 사용된 원본 질문 리스트
):
    """
    AI가 생성한 대표 질문들을 저장하고,
    관련된 Raw 질문들의 상태를 'processed'로 업데이트합니다.
    """
    if not representative_questions_data:
        return

    # 1. 대표 질문들을 DB에 새로 저장합니다.
    new_rep_questions_to_insert = []

    # AI 응답을 순회하며 DB에 저장할 객체를 만듭니다.
    for rep_q_data in representative_questions_data:
        # AI가 알려준 관련 질문 content와 원본 RawQuestion 객체를 매핑하여 ID를 찾습니다.
        related_raw_ids = []
        for content in rep_q_data.get("related_questions", []):
            for raw_q in processed_raw_questions:
                if raw_q.content == content:
                    related_raw_ids.append(raw_q.id)
                    break  # 찾았으면 중단

        new_rep_question = models.RepresentativeQuestionInDB(
            title=rep_q_data.get("representative_question", "제목 없음"),
            raw_question_ids=related_raw_ids,
            # total_votes는 나중에 업데이트 로직 추가
        )
        new_rep_questions_to_insert.append(new_rep_question.model_dump(by_alias=True))

    if new_rep_questions_to_insert:
        await db[REPRESENTATIVE_QUESTIONS_COLLECTION].insert_many(new_rep_questions_to_insert)
        print(f"{len(new_rep_questions_to_insert)}개의 대표 질문이 저장되었습니다.")

    # 2. 처리가 완료된 Raw 질문들의 ID 목록을 만듭니다.
    processed_raw_ids = [q.id for q in processed_raw_questions]

    # 3. 해당 Raw 질문들의 status를 'processed'로 일괄 업데이트합니다.
    if processed_raw_ids:
        await db[RAW_QUESTIONS_COLLECTION].update_many(
            {"_id": {"$in": processed_raw_ids}},
            {"$set": {"status": models.RawQuestionStatus.PROCESSED.value}}
        )
        print(f"{len(processed_raw_ids)}개의 Raw 질문 상태가 'processed'로 업데이트되었습니다.")


# --------------------------------------------------------------------------
# RepresentativeQuestion CRUD 함수 (API 호출용)
# --------------------------------------------------------------------------

async def get_all_representative_questions(db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 10) -> List[
    models.RepresentativeQuestionInDB]:
    """
    모든 대표 질문을 'total_votes'가 높은 순서대로 페이지네이션하여 조회합니다.
    사용자에게 보여주기 위한 API에서 사용됩니다.
    """
    questions = []
    # find({"status": "unanswered"}) -> 아직 답변이 달리지 않은 질문만 필터링
    # sort("total_votes", -1) -> 공감 수가 높은 순서대로 정렬 (내림차순)
    cursor = db[REPRESENTATIVE_QUESTIONS_COLLECTION].find(
        {"status": "unanswered"}
    ).sort("total_votes", -1).skip(skip).limit(limit)

    async for question in cursor:
        questions.append(models.RepresentativeQuestionInDB(**question))

    return questions