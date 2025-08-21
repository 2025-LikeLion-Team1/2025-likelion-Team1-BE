from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .routers import community, questions, answers
from .tasks import ai_pipeline

# --------------------------------------------------------------------------
# FastAPI 수명 주기(Lifecycle) 이벤트 핸들러
# --------------------------------------------------------------------------
# 이 부분은 '서버가 켜질 때'와 '서버가 꺼질 때' 특정 작업을 수행하도록 설정하는 곳입니다.
# 우리는 이 기능을 이용해 AI 파이프라인 스케줄러를 관리합니다.
# --------------------------------------------------------------------------

# 1. 스케줄러 객체를 생성합니다.
scheduler = AsyncIOScheduler()


# 2. lifespan 컨텍스트 매니저를 정의합니다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 앱이 시작될 때 실행될 코드 ---
    print("=" * 50)
    print("QnAHub 서버가 시작됩니다.")
    print("AI 파이프라인 스케줄러를 1분 간격으로 실행합니다.")
    print("=" * 50)

    # 1분(minutes=1)마다 ai_pipeline.run_question_processing_pipeline 함수를 실행하도록 작업을 추가합니다.
    scheduler.add_job(ai_pipeline.run_question_processing_pipeline, 'interval', minutes=1)

    # 스케줄러를 시작합니다.
    scheduler.start()

    # 'yield'는 앱이 실행되는 동안 잠시 멈춰있는 지점입니다.
    yield

    # --- 앱이 종료될 때 (예: Ctrl+C) 실행될 코드 ---
    print("=" * 50)
    print("QnAHub 서버가 종료됩니다.")
    print("AI 파이프라인 스케줄러를 안전하게 종료합니다.")
    print("=" * 50)

    # 실행 중인 스케줄러를 안전하게 종료합니다.
    scheduler.shutdown()


# --------------------------------------------------------------------------
# FastAPI 애플리케이션 생성 및 설정
# --------------------------------------------------------------------------

# 1. FastAPI 앱 객체를 생성하면서, 위에서 정의한 lifespan을 등록합니다.
app = FastAPI(lifespan=lifespan)

# 2. 각 기능별로 만든 라우터들을 앱에 포함시킵니다.
app.include_router(community.router)
app.include_router(questions.router)
app.include_router(answers.router)


# 3. 루트 경로("/")에 대한 기본 API를 정의합니다.
@app.get("/")
def read_root():
    """서버가 정상적으로 작동하는지 확인하는 기본 엔드포인트입니다."""
    return {"message": "Welcome to QnAHub API"}