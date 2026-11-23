from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import create_database_pools
from app.core.redis_client import create_redis_client
from app.modules.calendar.repository import upsert_events
from app.modules.calendar.router import admin_router as calendar_admin_router
from app.modules.calendar.router import router as calendar_router
from app.modules.calendar.service import process_calendar_upload
from app.modules.calendar.vision import OpenAICalendarVision
from app.modules.chat.openai_provider import OpenAISqlGenerator
from app.modules.chat.pipeline import ReadOnlyChatPipeline
from app.modules.chat.router import router as chat_router
from app.modules.reviews.router import router as reviews_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    application.state.pools = await create_database_pools(
        settings.supabase_admin_url,
        settings.supabase_readonly_url,
    )
    application.state.redis = create_redis_client(
        settings.upstash_redis_rest_url,
        settings.upstash_redis_rest_token,
    )
    application.state.chat_pipeline = ReadOnlyChatPipeline(
        application.state.pools.readonly,
        OpenAISqlGenerator(settings.openai_api_key),
    )
    vision = OpenAICalendarVision(settings.openai_api_key)

    async def ingest_upload(image_bytes, queue):
        return await process_calendar_upload(
            image_bytes,
            queue,
            vision,
            lambda events: upsert_events(application.state.pools.admin, events),
        )

    application.state.vision = vision
    application.state.process_calendar_upload = ingest_upload
    try:
        yield
    finally:
        await application.state.pools.close()
        await application.state.redis.close()


app = FastAPI(title="Wolf Ranch Community Calendar", lifespan=lifespan)
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router)
app.include_router(calendar_router)
app.include_router(calendar_admin_router)
app.include_router(reviews_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
