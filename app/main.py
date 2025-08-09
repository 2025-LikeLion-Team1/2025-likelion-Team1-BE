from fastapi import FastAPI
from .routers import community

app = FastAPI()
app.include_router(community.router)

@app.get("/")
def read_root():
    return {"Hello": "QnAHub"}
