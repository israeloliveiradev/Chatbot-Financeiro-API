from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.infra.config import settings
from src.infra.logging import setup_logging, get_logger
from src.api.middleware import TraceIDMiddleware
from src.api.routers import internal, webhook

# Initialize structured logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Chatbot Financeiro API",
    description="Backend do assistente financeiro pessoal via WhatsApp.",
    version="1.0.0",
)

# Add Middleware
app.add_middleware(TraceIDMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.domain.exceptions import DomainException

# Include routers
app.include_router(internal.router)
app.include_router(webhook.router)

@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    status_code = 400
    if exc.code == "NOT_FOUND":
        status_code = 404
    elif exc.code == "UNAUTHORIZED":
        status_code = 401
        
    logger.warning(f"Domain exception: {exc.message}", extra={"code": exc.code})
    
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "code": "INTERNAL_ERROR"}
    )

from src.infra.database.session import engine
from src.adapters.cache.redis_session import RedisSession

@app.get("/health", tags=["Health"])
async def health_check():
    health = {
        "status": "online",
        "environment": settings.app_env,
        "database": "down",
        "redis": "down"
    }
    
    # Check DB
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            health["database"] = "up"
    except Exception as e:
        logger.error(f"Health Check DB Error: {e}")

    # Check Redis
    try:
        redis_session = RedisSession()
        # Redis PING
        await redis_session.redis.ping()
        health["redis"] = "up"
    except Exception as e:
        logger.error(f"Health Check Redis Error: {e}")

    return health
