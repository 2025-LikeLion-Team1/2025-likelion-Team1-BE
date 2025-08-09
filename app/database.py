import motor.motor_asyncio
import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

MONGO_DATABASE_URL = os.getenv("MONGO_DATABASE_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")

# DB 연결 객체 생성
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DATABASE_URL)
database = client[DATABASE_NAME]

def get_db():
    return database
