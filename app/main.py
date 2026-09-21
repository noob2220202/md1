from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401
from .config import AVATARS_DIR, BASE_DIR
from .database import Base, SessionLocal, engine
from .models import Category
from .routers import accounts, categories, pages

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        if not db.query(Category).filter_by(name="스팸").first():
            db.add(Category(name="스팸", color="#f87171", is_system=True))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="TeleOps - Telegram 계정 관리", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR)), name="avatars")

app.include_router(pages.router)
app.include_router(accounts.router)
app.include_router(categories.router)
