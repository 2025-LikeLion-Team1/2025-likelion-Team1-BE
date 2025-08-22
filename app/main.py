from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .routers import community, questions, answers, likes
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

# FastAPI 앱 객체를 생성하면서, 위에서 정의한 lifespan을 등록합니다.
app = FastAPI(lifespan=lifespan)

# --- CORS 미들웨어 설정 ---
# 허용할 출처(origin) 목록. 로컬 프론트엔드 개발 서버 주소를 넣습니다.
origins = [
    "http://localhost",
    "http://localhost:3000",
    # 나중에 실제 프론트엔드 도메인을 추가합니다.
    # "http://qnahub.xyz",
    # "https://qnahub.xyz",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # 모든 HTTP 메소드 허용
    allow_headers=["*"], # 모든 HTTP 헤더 허용
)

# --- 라우터 등록 (prefix="/api" 추가) ---
# 이제 모든 API 경로는 /api 로 시작됩니다.
app.include_router(community.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(answers.router, prefix="/api")
app.include_router(likes.router, prefix="/api")


# 3. 루트 경로("/")에 대한 기본 API를 정의합니다.
@app.get("/")
def read_root():
    """서버가 정상적으로 작동하는지 확인하는 기본 엔드포인트입니다."""
    return {"message": "Welcome to QnAHub API"}