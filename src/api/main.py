from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.infra.config import settings
from src.api.routers import internal, webhook

app = FastAPI(
    title="Chatbot Financeiro API",
    description="Backend do assistente financeiro pessoal via WhatsApp.",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(internal.router)
app.include_router(webhook.router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "online",
        "environment": settings.app_env
    }
