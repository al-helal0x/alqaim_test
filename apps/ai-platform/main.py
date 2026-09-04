"""نقطة دخول ai-platform — REST داخلي + Worker entrypoint (القسم 7.10)."""
from fastapi import FastAPI

from platform_core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


from presentation.routes.documents_router import router as documents_router
from presentation.routes.entities_router import router as entities_router

app.include_router(documents_router, prefix="/ai", tags=["ai-documents"])
app.include_router(entities_router, prefix="/ai/entities", tags=["ai-entities"])
