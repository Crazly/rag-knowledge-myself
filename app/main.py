from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.database import init_db
from app.api import documents, chat, admin, auth_api, dify
from app.web import pages
from app.auth import AuthMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.scheduler.jobs import start_scheduler
    start_scheduler()
    yield


app = FastAPI(title="Knowledge Base", version="0.2.0", lifespan=lifespan)

# Auth middleware (set ACCESS_TOKEN env var to enable)
app.add_middleware(AuthMiddleware)

app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(auth_api.router, prefix="/api")
app.include_router(dify.router, prefix="/api")
app.include_router(pages.router)
