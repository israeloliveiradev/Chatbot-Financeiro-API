from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.infra.config import settings
from src.infra.logging import setup_logging, get_logger
from src.api.middleware import TraceIDMiddleware
from src.api.routers import webhook

# Initialize structured logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Chatbot Financeiro API",
    description="Backend do assistente financeiro pessoal via WhatsApp.",
    version="1.0.0",
)

# Add Middleware - Order is important (Outermost to Innermost)
from src.api.middleware import TraceIDMiddleware, RequestLoggingMiddleware, RateLimitMiddleware

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(TraceIDMiddleware)

# CORS configuration - Restricted in Production
# Em produção, você deve definir as origens permitidas via variável de ambiente
origins = ["*"] if settings.app_env == "development" else [settings.evolution_server_url]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

from src.domain.exceptions import DomainException

from src.api.routers import clients, goals, spending, webhook

# Include routers
app.include_router(clients.router)
app.include_router(goals.router)
app.include_router(spending.router)
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
async def health_check(request: Request):
    """
    Endpoint de saúde simplificado.
    Detalhes só são exibidos em desenvolvimento ou com chave de API.
    """
    is_admin = request.headers.get("X-API-Key") == settings.internal_api_key
    show_details = settings.app_env == "development" or is_admin

    if not show_details:
        return {"status": "online"}

    health = {
        "status": "online",
        "environment": settings.app_env,
        "database": "down",
        "redis": "down",
        "version": "1.0.0"
    }
    
    # Check DB
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            health["database"] = "up"
    except Exception:
        pass

    # Check Redis
    try:
        redis_session = RedisSession()
        await redis_session.redis.ping()
        health["redis"] = "up"
    except Exception:
        pass

    return health
