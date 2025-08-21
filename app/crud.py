from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from . import models
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone

# 컬렉션 이름 정의
COMMUNITY_COLLECTION = "community_posts"
RAW_QUESTIONS_COLLECTION = "raw_questions"
REPRESENTATIVE_QUESTIONS_COLLECTION = "representative_questions"
ANSWERS_COLLECTION = "answers"

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


async def get_raw_questions_by_status(
    db: AsyncIOMotorDatabase, status: models.RawQuestionStatus, limit: int = 100
) -> List[models.RawQuestionInDB]:
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
    print(f"[DEBUG] 저장하려는 대표 질문 데이터: {representative_questions_data}")
    print(f"[DEBUG] 처리된 Raw 질문들: {[q.model_dump() for q in processed_raw_questions]}")
    
    if not representative_questions_data:
        return

    # 1. 대표 질문들을 DB에 새로 저장합니다.
    new_rep_questions_to_insert = []

    # AI 응답을 순회하며 DB에 저장할 객체를 만듭니다.
    for rep_q_data in representative_questions_data:
        # AI가 직접 ID 리스트를 주지만, 문자열로 오므로 ObjectId로 변환해야 합니다!
        related_raw_ids_str = rep_q_data.get("related_question_ids", [])
        
        # 문자열 ID들을 ObjectId로 변환
        related_raw_ids = []
        for id_str in related_raw_ids_str:
            try:
                related_raw_ids.append(ObjectId(id_str))
            except Exception as e:
                print(f"[WARNING] 유효하지 않은 ObjectId: {id_str}, 에러: {e}")
                continue

        new_rep_question = models.RepresentativeQuestionInDB(
            title=rep_q_data.get("representative_question", "제목 없음"),
            raw_question_ids=related_raw_ids,  # 이제 ObjectId 배열
        )
        
        # Pydantic 모델을 dict로 변환하되, _id 필드는 ObjectId로 유지
        question_dict = new_rep_question.model_dump(by_alias=True)
        # _id 필드가 문자열로 변환되었다면 다시 ObjectId로 변환
        if isinstance(question_dict.get("_id"), str):
            question_dict["_id"] = ObjectId(question_dict["_id"])
        
        new_rep_questions_to_insert.append(question_dict)

    if new_rep_questions_to_insert:
        await db[REPRESENTATIVE_QUESTIONS_COLLECTION].insert_many(new_rep_questions_to_insert)
        print(f"{len(new_rep_questions_to_insert)}개의 대표 질문이 저장되었습니다.")

    # 2. 처리가 완료된 Raw 질문들의 ID 목록을 만듭니다.
    processed_raw_ids = [q.id for q in processed_raw_questions]

    # 3. 해당 Raw 질문들의 status를 'represented'로 일괄 업데이트합니다.
    if processed_raw_ids:
        await db[RAW_QUESTIONS_COLLECTION].update_many(
            {"_id": {"$in": processed_raw_ids}},
            {"$set": {"status": models.RawQuestionStatus.REPRESENTED.value}}
        )
        print(f"{len(processed_raw_ids)}개의 Raw 질문 상태가 'represented'로 업데이트되었습니다.")


# --------------------------------------------------------------------------
# RepresentativeQuestion CRUD 함수 (API 호출용)
# --------------------------------------------------------------------------

async def get_all_representative_questions(db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 10) -> List[
    models.RepresentativeQuestionInDB]:
    """
    모든 대표 질문을 'total_votes'가 높은 순서대로 페이지네이션하여 조회합니다.
    사용자에게 보여주기 위한 API에서 사용됩니다.
    """
    print(f"[DEBUG] DB 이름: {db.name}")
    print(f"[DEBUG] 컬렉션 이름: {REPRESENTATIVE_QUESTIONS_COLLECTION}")
    
    # 컬렉션의 총 문서 수 확인
    total_count = await db[REPRESENTATIVE_QUESTIONS_COLLECTION].count_documents({})
    print(f"[DEBUG] 컬렉션 총 문서 수: {total_count}")
    
    questions = []
    # find({"status": "unanswered"}) -> 아직 답변이 달리지 않은 질문만 필터링
    # sort("total_votes", -1) -> 공감 수가 높은 순서대로 정렬 (내림차순)
    cursor = db[REPRESENTATIVE_QUESTIONS_COLLECTION].find(
        {"status": "unanswered"}
    ).sort("total_votes", -1).skip(skip).limit(limit)

    async for question in cursor:
        print(f"[DEBUG] 찾은 질문: {question}")
        questions.append(models.RepresentativeQuestionInDB(**question))

    print(f"[DEBUG] 반환할 질문 수: {len(questions)}")
    return questions


# --------------------------------------------------------------------------
# Answer CRUD 함수
# --------------------------------------------------------------------------

async def create_answer_for_question(db: AsyncIOMotorDatabase, answer_data: models.AnswerCreate) -> models.AnswerInDB:
    """대표 질문에 대한 새로운 답변을 생성합니다."""

    # 1. 답변(Answer) 문서를 생성합니다.
    answer_dict = answer_data.model_dump()
    answer_dict['created_at'] = datetime.now(timezone.utc)
    
    # representative_question_id가 문자열이면 ObjectId로 변환
    if isinstance(answer_dict['representative_question_id'], str):
        answer_dict['representative_question_id'] = ObjectId(answer_dict['representative_question_id'])
    
    result = await db[ANSWERS_COLLECTION].insert_one(answer_dict)

    # 2. 관련 대표 질문(RepresentativeQuestion)의 상태를 'answered'로 업데이트합니다.
    update_result = await db[REPRESENTATIVE_QUESTIONS_COLLECTION].update_one(
        {"_id": answer_data.representative_question_id},
        {"$set": {"status": "answered"}}
    )
    print(f"[DEBUG] 대표 질문 상태 업데이트 결과: {update_result.modified_count}개 문서 수정됨")

    # 3. 대표 질문에 묶인 모든 Raw 질문들의 상태를 'answered'로 업데이트합니다.
    rep_question = await db[REPRESENTATIVE_QUESTIONS_COLLECTION].find_one(
        {"_id": answer_data.representative_question_id}
    )
    print(f"[DEBUG] 조회된 대표 질문: {rep_question}")
    
    if rep_question and rep_question.get("raw_question_ids"):
        raw_ids_to_update = rep_question["raw_question_ids"]
        print(f"[DEBUG] 업데이트할 Raw 질문 ID들: {raw_ids_to_update}")
        print(f"[DEBUG] Raw ID들의 타입: {[type(rid) for rid in raw_ids_to_update]}")
        
        # Raw 질문들이 실제로 존재하는지 먼저 확인
        existing_raw_questions = await db[RAW_QUESTIONS_COLLECTION].find(
            {"_id": {"$in": raw_ids_to_update}}
        ).to_list(length=None)
        print(f"[DEBUG] ObjectId로 찾은 Raw 질문 수: {len(existing_raw_questions)}")
        
        # ObjectId로 찾은 결과가 없다면 문자열을 ObjectId로 변환해서 시도
        if len(existing_raw_questions) == 0:
            raw_ids_as_str = [str(rid) for rid in raw_ids_to_update]
            print(f"[DEBUG] 문자열로 변환된 ID들: {raw_ids_as_str}")
            existing_raw_questions = await db[RAW_QUESTIONS_COLLECTION].find(
                {"_id": {"$in": raw_ids_as_str}}
            ).to_list(length=None)
            print(f"[DEBUG] 문자열로 찾은 Raw 질문 수: {len(existing_raw_questions)}")
            
            # 문자열로도 찾을 수 없다면 문자열을 ObjectId로 변환해서 시도
            if len(existing_raw_questions) == 0:
                try:
                    raw_ids_as_objectid = [ObjectId(rid) for rid in raw_ids_as_str]
                    print(f"[DEBUG] ObjectId로 변환된 ID들: {raw_ids_as_objectid}")
                    existing_raw_questions = await db[RAW_QUESTIONS_COLLECTION].find(
                        {"_id": {"$in": raw_ids_as_objectid}}
                    ).to_list(length=None)
                    print(f"[DEBUG] ObjectId로 변환 후 찾은 Raw 질문 수: {len(existing_raw_questions)}")
                    
                    if len(existing_raw_questions) > 0:
                        # ObjectId로 업데이트 시도
                        raw_update_result = await db[RAW_QUESTIONS_COLLECTION].update_many(
                            {"_id": {"$in": raw_ids_as_objectid}},
                            {"$set": {"status": models.RawQuestionStatus.ANSWERED.value}}
                        )
                    else:
                        raw_update_result = await db[RAW_QUESTIONS_COLLECTION].update_many(
                            {"_id": {"$in": raw_ids_as_str}},
                            {"$set": {"status": models.RawQuestionStatus.ANSWERED.value}}
                        )
                except Exception as e:
                    print(f"[DEBUG] ObjectId 변환 실패: {e}")
                    # 문자열로 업데이트 시도
                    raw_update_result = await db[RAW_QUESTIONS_COLLECTION].update_many(
                        {"_id": {"$in": raw_ids_as_str}},
                        {"$set": {"status": models.RawQuestionStatus.ANSWERED.value}}
                    )
            else:
                # 문자열로 업데이트 시도
                raw_update_result = await db[RAW_QUESTIONS_COLLECTION].update_many(
                    {"_id": {"$in": raw_ids_as_str}},
                    {"$set": {"status": models.RawQuestionStatus.ANSWERED.value}}
                )
        else:
            # ObjectId로 업데이트 시도
            raw_update_result = await db[RAW_QUESTIONS_COLLECTION].update_many(
                {"_id": {"$in": raw_ids_to_update}},
                {"$set": {"status": models.RawQuestionStatus.ANSWERED.value}}
            )
        
        print(f"[DEBUG] Raw 질문 상태 업데이트 결과: {raw_update_result.modified_count}개 문서 수정됨")
    else:
        print("[DEBUG] raw_question_ids가 없거나 대표 질문을 찾을 수 없습니다.")

    # 4. 생성된 답변 문서를 다시 조회하여 반환합니다.
    created_answer = await db[ANSWERS_COLLECTION].find_one({"_id": result.inserted_id})
    return models.AnswerInDB(**created_answer)


async def get_answer_for_question(db: AsyncIOMotorDatabase, question_id: models.PyObjectId) -> Optional[models.AnswerInDB]:
    """특정 대표 질문에 달린 답변을 조회합니다."""
    answer = await db[ANSWERS_COLLECTION].find_one({"representative_question_id": question_id})
    if answer:
        return models.AnswerInDB(**answer)
    return None

async def get_representative_question_by_id(db: AsyncIOMotorDatabase, question_id: models.PyObjectId) -> Optional[models.RepresentativeQuestionInDB]:
    """ID로 특정 대표 질문 하나를 조회합니다."""
    print(f"[DEBUG] 조회하려는 대표 질문 ID: {question_id}, 타입: {type(question_id)}")
    question = await db[REPRESENTATIVE_QUESTIONS_COLLECTION].find_one({"_id": question_id})
    print(f"[DEBUG] DB 조회 결과: {question}")
    if question:
        return models.RepresentativeQuestionInDB(**question)
    return None


async def get_all_answered_questions(db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 10) -> List[dict]:
    """
    답변이 완료된 모든 질문과 답변 쌍을 최신순으로 조회합니다.
    MongoDB Aggregation Pipeline을 사용합니다.
    """
    print(f"[DEBUG] get_all_answered_questions 호출됨 - skip: {skip}, limit: {limit}")
    
    # 먼저 답변 컬렉션에 데이터가 있는지 확인
    answer_count = await db[ANSWERS_COLLECTION].count_documents({})
    print(f"[DEBUG] 전체 답변 수: {answer_count}")
    
    # 실제 답변 데이터 확인
    sample_answer = await db[ANSWERS_COLLECTION].find_one()
    print(f"[DEBUG] 샘플 답변 데이터: {sample_answer}")
    
    # 대표 질문 데이터 확인
    rep_question_count = await db[REPRESENTATIVE_QUESTIONS_COLLECTION].count_documents({})
    print(f"[DEBUG] 전체 대표 질문 수: {rep_question_count}")
    
    sample_rep_question = await db[REPRESENTATIVE_QUESTIONS_COLLECTION].find_one()
    print(f"[DEBUG] 샘플 대표 질문 데이터: {sample_rep_question}")
    
    # 답변의 representative_question_id로 직접 대표 질문을 찾아보기
    if sample_answer:
        direct_match = await db[REPRESENTATIVE_QUESTIONS_COLLECTION].find_one(
            {"_id": sample_answer["representative_question_id"]}
        )
        print(f"[DEBUG] 직접 매칭 결과: {direct_match}")
        
        # 문자열로 변환해서도 찾아보기
        str_id = str(sample_answer["representative_question_id"])
        string_match = await db[REPRESENTATIVE_QUESTIONS_COLLECTION].find_one(
            {"_id": str_id}
        )
        print(f"[DEBUG] 문자열 매칭 결과: {string_match}")
    
    pipeline = [
        # 1. 답변(answers)을 최신 생성 순서로 정렬합니다.
        {"$sort": {"created_at": -1}},

        # 2. representative_questions 컬렉션과 JOIN 합니다. ($lookup)
        {
            "$lookup": {
                "from": REPRESENTATIVE_QUESTIONS_COLLECTION,  # JOIN할 다른 컬렉션
                "localField": "representative_question_id",  # 현재(answers) 컬렉션의 필드
                "foreignField": "_id",  # JOIN할 컬렉션의 필드
                "as": "question_details"  # JOIN된 결과를 담을 필드 이름
            }
        },

        # 3. JOIN 결과는 배열([..])이므로, 배열을 풀어 객체로 만듭니다. ($unwind)
        {"$unwind": "$question_details"},

        # 4. 페이지네이션을 적용합니다.
        {"$skip": skip},
        {"$limit": limit},

        # 5. 최종 출력 형태를 우리가 만든 QuestionAndAnswer 모델과 유사하게 재구성합니다.
        {
            "$project": {
                "_id": 0,  # 최상위 _id는 필요 없으므로 제외
                "question": "$question_details",
                "answer": {
                    "_id": "$_id",
                    "content": "$content",
                    "author_id": "$author_id",
                    "representative_question_id": "$representative_question_id",
                    "created_at": "$created_at"
                }
            }
        }
    ]

    print(f"[DEBUG] Aggregation pipeline: {pipeline}")

    # answers 컬렉션에 대해 aggregation pipeline을 실행합니다.
    cursor = db[ANSWERS_COLLECTION].aggregate(pipeline)

    # 결과를 리스트로 변환하여 반환합니다.
    results = await cursor.to_list(length=limit)
    print(f"[DEBUG] Aggregation 결과 수: {len(results)}")
    for i, result in enumerate(results):
        print(f"[DEBUG] 결과 {i}: {result}")
    
    return results