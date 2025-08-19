from pydantic import BaseModel, Field, GetJsonSchemaHandler
from pydantic_core import core_schema
from typing import Optional, List, Any
from bson import ObjectId
from datetime import datetime, timezone
from enum import Enum


# --------------------------------------------------------------------------
# ObjectId를 Pydantic v2에서 완벽하게 처리하기 위한 커스텀 타입 (최종 버전)
# --------------------------------------------------------------------------
# 이 클래스 하나로 ObjectId 관련 모든 문제를 해결합니다.
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
            cls, source_type: Any, handler: Any
    ) -> core_schema.CoreSchema:
        """
        Pydantic이 이 타입을 어떻게 처리해야 하는지 알려줍니다.
        1. 유효성 검사: 입력값이 ObjectId로 변환 가능한지 확인합니다.
        2. JSON 스키마: 이 타입을 'string' 형식(format: objectid)으로 문서화하도록 합니다.
        3. 직렬화(Serialization): Python 객체를 JSON으로 변환할 때, ObjectId를 str으로 바꿉니다.
        """

        def validate(v: Any) -> ObjectId:
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid ObjectId")
            return ObjectId(v)

        # ObjectId -> str 변환 로직
        def to_str(v: ObjectId) -> str:
            return str(v)

        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(
                min_length=24, max_length=24, pattern="^[0-9a-fA-F]{24}$"
            ),
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [core_schema.str_schema(), core_schema.no_info_plain_validator_function(validate)])
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(to_str)
        )


# --------------------------------------------------------------------------
# Community Post 모델
# --------------------------------------------------------------------------
class PostBase(BaseModel):
    title: str
    content: str
    author_id: str
    likes: int = 0


class PostCreate(PostBase):
    pass  # PostBase와 동일한 필드를 사용


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class PostInDB(PostBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        from_attributes = True
        populate_by_name = True


class Post(PostBase):
    id: PyObjectId = Field(alias="_id")

    class Config:
        from_attributes = True
        populate_by_name = True


# --------------------------------------------------------------------------
# Raw Question (사용자의 날것 질문) 모델
# --------------------------------------------------------------------------
class RawQuestionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    REJECTED = "rejected"


class RawQuestionBase(BaseModel):
    content: str
    author_id: str
    status: RawQuestionStatus = RawQuestionStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RawQuestionCreate(RawQuestionBase):
    pass # RawQuestionBase 상속


class RawQuestionInDB(RawQuestionBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        from_attributes = True
        populate_by_name = True


# --------------------------------------------------------------------------
# Representative Question (AI가 생성한 대표 질문) 모델
# --------------------------------------------------------------------------
class RepresentativeQuestionBase(BaseModel):
    title: str
    total_votes: int = 0
    status: str = "unanswered"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RepresentativeQuestionInDB(RepresentativeQuestionBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    raw_question_ids: List[PyObjectId] = []

    class Config:
        from_attributes = True
        populate_by_name = True


class RepresentativeQuestion(RepresentativeQuestionBase):
    id: PyObjectId = Field(alias="_id")

    class Config:
        from_attributes = True
        populate_by_name = True