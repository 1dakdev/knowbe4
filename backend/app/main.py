from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="K-12 Assessment Platform")

app.include_router(health.router)
