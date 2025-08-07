from pydantic import BaseModel, Field, AfterValidator
from typing import Optional, List, Annotated
from bson import ObjectId


# --- 새로운 ObjectId 타입 정의 ---
# Pydantic v2 스타일: Annotated 타입을 사용하여 검증 로직을 추가합니다.
def check_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError(f"'{value}' is not a valid ObjectId")
    return ObjectId(value)


# PyObjectId 타입을 Annotated로 정의
# str 타입으로 받아서 check_object_id 함수로 검증한 뒤 ObjectId 타입으로 변환
PyObjectId = Annotated[str, AfterValidator(check_object_id)]


# --- Community Post 모델 ---

# 데이터베이스에 저장될 때의 모델 (DB 스키마)
class PostInDB(BaseModel):
    # 이제 id 필드를 그냥 ObjectId 타입으로 선언할 수 있습니다.
    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    title: str
    content: str
    author_id: str
    likes: int = 0

    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True
        populate_by_name = True  # _id를 id로 자동 매핑
        arbitrary_types_allowed = True

# 게시글을 생성할 때 클라이언트로부터 받을 데이터 모델
class PostCreate(BaseModel):
    title: str
    content: str
    author_id: str

# 게시글 목록이나 상세 정보를 클라이언트에게 보여줄 때의 모델
class Post(BaseModel):
    # alias를 사용했기 때문에, PostInDB의 _id 필드가 자동으로 'id' 필드로 매핑됩니다.
    # 타입은 str로 유지합니다 (JSON 응답 시 문자열로 나가야 하므로).
    id: str
    title: str
    content: str
    author_id: str
    likes: int

    class Config:
        from_attributes = True
        populate_by_name = True

# 게시글을 수정할 때 받을 데이터 모델
# 모든 필드가 선택적(Optional)이므로, 사용자는 바꾸고 싶은 필드만 보낼 수 있습니다.
class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


