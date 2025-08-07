from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from .. import crud, models, database
from motor.motor_asyncio import AsyncIOMotorDatabase

# APIRouter 인스턴스 생성
# prefix: 이 파일의 모든 API 경로 앞에 /community가 붙습니다.
# tags: FastAPI 자동 문서(Swagger UI)에서 API들을 'Community' 그룹으로 묶어줍니다.
router = APIRouter(
    prefix="/community",
    tags=["Community"]
)


# --- READ: 모든 게시글 조회 (페이지네이션 적용) ---
@router.get("/posts", response_model=List[models.Post], summary="모든 게시글 목록 조회")
async def get_all_community_posts(skip: int = 0, limit: int = 10, db: AsyncIOMotorDatabase = Depends(database.get_db)):
    """
    모든 커뮤니티 게시글을 페이지네이션하여 조회합니다.
    - **skip**: 건너뛸 문서의 수
    - **limit**: 반환할 최대 문서의 수
    """
    db_posts = await crud.get_all_posts(db=db, skip=skip, limit=limit)

    # 리스트의 각 PostInDB 객체를 순회하며 Post 객체로 직접 변환
    response_posts = [
        models.Post(
            id=str(post.id),
            title=post.title,
            content=post.content,
            author_id=post.author_id,
            likes=post.likes
        )
        for post in db_posts
    ]

    return response_posts

# --- CREATE: 새로운 게시글 생성 ---
@router.post("/posts", response_model=models.Post, status_code=status.HTTP_201_CREATED, summary="새 게시글 생성")
async def create_new_community_post(post_data: models.PostCreate, db: AsyncIOMotorDatabase = Depends(database.get_db)):
    """
    새로운 커뮤니티 게시글을 생성합니다.
    - **title**: 게시글 제목
    - **content**: 게시글 내용
    - **author_id**: 작성자 ID
    """
    # 1. crud 함수를 통해 DB와 상호작용하는 모델(PostInDB)을 받습니다.
    created_post_in_db = await crud.create_post(db=db, post_data=post_data)

    # 2. 응답으로 보낼 모델(Post)을 직접, 수동으로 생성합니다.
    #    이것이 가장 확실하고 버그가 없는 방법입니다.
    response_post = models.Post(
        id=str(created_post_in_db.id),  # ObjectId를 명시적으로 str으로 변환
        title=created_post_in_db.title,
        content=created_post_in_db.content,
        author_id=created_post_in_db.author_id,
        likes=created_post_in_db.likes
    )

    return response_post

# READ: 특정 게시글 조회
@router.get("/posts/{post_id}", response_model=models.Post, summary="특정 게시글 조회")
async def get_single_community_post(post_id: str, db: AsyncIOMotorDatabase = Depends(database.get_db)):
    """
    주어진 ID에 해당하는 특정 게시글 하나를 조회합니다.
    - **post_id**: 조회할 게시글의 고유 ID
    """
    db_post = await crud.get_post_by_id(db=db, post_id=post_id)
    if db_post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    return models.Post(
        id=str(db_post.id),
        title=db_post.title,
        content=db_post.content,
        author_id=db_post.author_id,
        likes=db_post.likes
    )

# UPDATE: 특정 게시글 수정
@router.patch("/posts/{post_id}", response_model=models.Post, summary="특정 게시글 수정")
async def update_single_community_post(post_id: str, post_data: models.PostUpdate, db: AsyncIOMotorDatabase = Depends(database.get_db)):
    """
    주어진 ID에 해당하는 게시글의 정보를 수정합니다. (부분 수정)
    - **post_id**: 수정할 게시글의 고유 ID
    - **title** (선택적): 새로운 제목
    - **content** (선택적): 새로운 내용
    """
    updated_post = await crud.update_post(db=db, post_id=post_id, post_data=post_data)
    if updated_post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    return models.Post(
        id=str(updated_post.id),
        title=updated_post.title,
        content=updated_post.content,
        author_id=updated_post.author_id,
        likes=updated_post.likes
    )

# DELETE: 특정 게시글 삭제
@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, summary="특정 게시글 삭제")
async def delete_single_community_post(post_id: str, db: AsyncIOMotorDatabase = Depends(database.get_db)):
    """
    주어진 ID에 해당하는 게시글을 삭제합니다.
    - **post_id**: 삭제할 게시글의 고유 ID
    """
    success = await crud.delete_post(db=db, post_id=post_id)
    if not success:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없거나 이미 삭제되었습니다.")
    # 성공적으로 삭제되면, 아무 내용도 반환하지 않습니다 (204 No Content).
    return