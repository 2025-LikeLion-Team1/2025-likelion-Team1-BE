from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from .. import models, crud
from ..database import get_db
from pydantic import BaseModel
import uuid
import hashlib

# 좋아요 관련 라우터
router = APIRouter(
    prefix="/likes",
    tags=["likes"]
)


def get_or_create_session_id(request: Request, response: Response) -> str:
    """쿠키에서 세션 ID를 가져오거나 새로 생성합니다."""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        # 새로운 세션 ID 생성 (UUID + IP 해시 조합)
        ip_address = request.client.host
        unique_string = f"{uuid.uuid4()}-{ip_address}"
        session_id = hashlib.md5(unique_string.encode()).hexdigest()
        
        # 쿠키에 세션 ID 설정 (30일 유효)
        response.set_cookie(
            key="session_id", 
            value=session_id, 
            max_age=30 * 24 * 60 * 60,  # 30일
            httponly=True,  # XSS 방지
            secure=False,   # HTTPS에서만 전송 (개발 시에는 False)
            samesite="lax"  # CSRF 방지
        )
    
    return session_id


class LikeResponse(BaseModel):
    """좋아요 응답 모델"""
    question_id: models.PyObjectId
    total_votes: int
    message: str
    user_liked: bool  # 사용자가 좋아요를 눌렀는지 여부


class VoteStatusResponse(BaseModel):
    """좋아요 상태 응답 모델"""
    question_id: str
    total_votes: int
    question_content: str
    user_liked: bool


class AnswerVoteStatusResponse(BaseModel):
    """답변 좋아요 상태 응답 모델"""
    answer_id: str
    total_votes: int
    answer_content: str
    user_liked: bool


@router.put("/questions/{question_id}/like")
async def like_representative_question(
    question_id: str,
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> LikeResponse:
    """
    대표 질문에 좋아요를 누르는 API (쿠키/세션 기반 중복 방지)
    """
    print(f"[DEBUG] 좋아요 요청 - question_id: {question_id}")
    print(f"[DEBUG] 클라이언트 IP: {request.client.host}")
    print(f"[DEBUG] 현재 쿠키: {request.cookies}")
    
    try:
        # 문자열 ID를 PyObjectId로 변환
        obj_id = models.PyObjectId(question_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 question_id입니다."
        )
    
    # 세션 ID 가져오기 또는 생성
    session_id = get_or_create_session_id(request, response)
    ip_address = request.client.host
    
    print(f"[DEBUG] 세션 ID: {session_id}")
    print(f"[DEBUG] IP 주소: {ip_address}")
    
    # 먼저 해당 질문이 존재하는지 확인
    existing_question = await crud.get_representative_question_by_id(db, obj_id)
    if not existing_question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 ID의 대표 질문을 찾을 수 없습니다."
        )
    
    # 중복 좋아요 체크하고 안전하게 좋아요 수 증가
    print(f"[DEBUG] 중복 체크 시작 - session_id: {session_id}, obj_id: {obj_id}")
    updated_question = await crud.safe_increment_votes_with_like_check(
        db, session_id, obj_id, ip_address
    )
    
    print(f"[DEBUG] 중복 체크 결과: {updated_question is not None}")
    
    if not updated_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 좋아요를 누르셨습니다."
        )
    
    return LikeResponse(
        question_id=updated_question.id,
        total_votes=updated_question.total_votes,
        message="좋아요가 추가되었습니다.",
        user_liked=True
    )


@router.put("/questions/{question_id}/unlike")
async def unlike_representative_question(
    question_id: str,
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> LikeResponse:
    """
    대표 질문의 좋아요를 취소하는 API (쿠키/세션 기반)
    """
    try:
        # 문자열 ID를 PyObjectId로 변환
        obj_id = models.PyObjectId(question_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 question_id입니다."
        )
    
    # 세션 ID 가져오기
    session_id = get_or_create_session_id(request, response)
    
    # 먼저 해당 질문이 존재하는지 확인
    existing_question = await crud.get_representative_question_by_id(db, obj_id)
    if not existing_question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 ID의 대표 질문을 찾을 수 없습니다."
        )
    
    # 좋아요 기록 확인 후 안전하게 좋아요 수 감소
    updated_question = await crud.safe_decrement_votes_with_like_check(
        db, session_id, obj_id
    )
    
    if not updated_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="좋아요를 누르지 않았거나 이미 취소되었습니다."
        )
    
    return LikeResponse(
        question_id=updated_question.id,
        total_votes=updated_question.total_votes,
        message="좋아요가 취소되었습니다.",
        user_liked=False
    )


@router.get("/questions/{question_id}/votes")
async def get_representative_question_votes(
    question_id: str,
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> VoteStatusResponse:
    """
    대표 질문의 좋아요 수를 조회하는 API (사용자의 좋아요 상태 포함)
    """
    try:
        # 문자열 ID를 PyObjectId로 변환
        obj_id = models.PyObjectId(question_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 question_id입니다."
        )
    
    # 해당 질문 조회
    question = await crud.get_representative_question_by_id(db, obj_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 ID의 대표 질문을 찾을 수 없습니다."
        )
    
    # 세션 ID 가져오기
    session_id = get_or_create_session_id(request, response)
    
    # 사용자가 좋아요를 눌렀는지 확인
    try:
        user_liked = await crud.check_user_already_liked(db, session_id, obj_id, "question")
    except Exception as e:
        # 에러가 나면 False로 기본값 설정
        user_liked = False
    
    return VoteStatusResponse(
        question_id=str(question.id),
        total_votes=question.total_votes,
        question_content=question.title,
        user_liked=user_liked
    )


# --- 답변 좋아요 API ---
@router.put("/answers/{answer_id}/like")
async def like_answer(
    answer_id: str,
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> LikeResponse:
    """
    답변에 좋아요를 누르는 API (쿠키/세션 기반 중복 방지)
    """
    try:
        obj_id = models.PyObjectId(answer_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 answer_id입니다."
        )
    
    session_id = get_or_create_session_id(request, response)
    ip_address = request.client.host
    
    # 답변 존재 확인
    existing_answer = await crud.get_answer_by_id(db, obj_id)
    if not existing_answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 ID의 답변을 찾을 수 없습니다."
        )
    
    # 중복 좋아요 체크 후 좋아요 수 증가
    updated_answer = await crud.safe_increment_answer_votes_with_like_check(
        db, session_id, obj_id, ip_address
    )
    
    if not updated_answer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 좋아요를 누르셨습니다."
        )
    
    return LikeResponse(
        question_id=updated_answer.id,  # answer_id를 반환
        total_votes=updated_answer.total_votes,
        message="답변에 좋아요가 추가되었습니다.",
        user_liked=True
    )


@router.put("/answers/{answer_id}/unlike")
async def unlike_answer(
    answer_id: str,
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> LikeResponse:
    """
    답변의 좋아요를 취소하는 API (쿠키/세션 기반)
    """
    try:
        obj_id = models.PyObjectId(answer_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 answer_id입니다."
        )
    
    session_id = get_or_create_session_id(request, response)
    
    # 답변 존재 확인
    existing_answer = await crud.get_answer_by_id(db, obj_id)
    if not existing_answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 ID의 답변을 찾을 수 없습니다."
        )
    
    # 좋아요 기록 확인 후 좋아요 수 감소
    updated_answer = await crud.safe_decrement_answer_votes_with_like_check(
        db, session_id, obj_id
    )
    
    if not updated_answer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="좋아요를 누르지 않았거나 이미 취소되었습니다."
        )
    
    return LikeResponse(
        question_id=updated_answer.id,  # answer_id를 반환
        total_votes=updated_answer.total_votes,
        message="답변 좋아요가 취소되었습니다.",
        user_liked=False
    )


@router.get("/answers/{answer_id}/votes")
async def get_answer_votes(
    answer_id: str,
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> AnswerVoteStatusResponse:
    """
    답변의 좋아요 수를 조회하는 API (사용자의 좋아요 상태 포함)
    """
    try:
        obj_id = models.PyObjectId(answer_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 answer_id입니다."
        )
    
    # 답변 조회
    answer = await crud.get_answer_by_id(db, obj_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 ID의 답변을 찾을 수 없습니다."
        )
    
    session_id = get_or_create_session_id(request, response)
    
    # 사용자가 좋아요를 눌렀는지 확인
    user_liked = await crud.check_user_already_liked(db, session_id, obj_id, "answer")
    
    return AnswerVoteStatusResponse(
        answer_id=str(answer.id),
        total_votes=answer.total_votes,
        answer_content=answer.content[:100] + "..." if len(answer.content) > 100 else answer.content,
        user_liked=user_liked
    )
