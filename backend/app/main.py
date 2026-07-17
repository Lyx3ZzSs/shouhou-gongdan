from fastapi import FastAPI

from app.routers.lock import router as lock_router

app = FastAPI()

app.include_router(lock_router)
