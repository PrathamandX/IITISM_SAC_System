"""IIT (ISM) SAC Hostel Management System - entry point. Run with: fastapi dev main.py"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

import backend.models  # noqa: F401  (registers all tables)
from backend.auth import hash_password
from backend.config import ADMIN_PASSWORD, ADMIN_USERNAME, CORS_ORIGINS
from backend.database import Base, SessionLocal, engine
from backend.models import Role, User
from backend.routers import auth, billing, complaints, finance, hostels, pages, staff, students


def create_first_admin() -> None:
    """Create the SAC chairman account from .env if no users exist yet."""
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)) or not (ADMIN_USERNAME and ADMIN_PASSWORD):
            return
        db.add(User(username=ADMIN_USERNAME, full_name="SAC Chairman", role=Role.chairman,
                    password_hash=hash_password(ADMIN_PASSWORD)))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    create_first_admin()
    yield


app = FastAPI(title="IIT (ISM) SAC Hostel Management System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "frontend" / "static"), name="static")

for module in (auth, hostels, students, billing, complaints, staff, finance, pages):
    app.include_router(module.router)


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok"}
