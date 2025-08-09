from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from . import models
from bson import ObjectId
from bson.errors import InvalidId

# 컬렉션 이름 정의
COMMUNITY_COLLECTION = "community_posts"

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
