from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .ai import router as ai_router
from .auth import router as auth_router
from .groups import router as groups_router
from .matching import router as matching_router
from .db import init_db
from .profile import router as profile_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="StudySync API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(groups_router)
app.include_router(matching_router)
app.include_router(profile_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
