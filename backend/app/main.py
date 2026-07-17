from fastapi import FastAPI

from app.routers import lock, review

app = FastAPI()

app.include_router(lock.router)
app.include_router(review.router)
