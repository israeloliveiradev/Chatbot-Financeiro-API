import time
import uuid
import logging
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from src.infra.logging import set_trace_id, trace_id_var, get_logger
from src.adapters.cache.redis_session import RedisSession
from src.infra.config import settings

logger = get_logger(__name__)

class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract trace_id from headers or generate a new one
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        
        # Set trace_id in context
        token = trace_id_var.set(trace_id)
        
        try:
            response = await call_next(request)
            # Return trace_id in response headers
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            # Clean up context
            trace_id_var.reset(token)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Adiciona o trace_id atual
        logger.info(f"Incoming request: {method} {path}")
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            
            logger.info(
                f"Completed request: {method} {path} - "
                f"Status: {response.status_code} - "
                f"Duration: {process_time:.2f}ms"
            )
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Failed request: {method} {path} - "
                f"Error: {str(e)} - "
                f"Duration: {process_time:.2f}ms"
            )
            raise e

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simples Rate Limiter por IP usando Redis.
    Configurável via env (pode ser expandido para diferentes limites por rota).
    """
    async def dispatch(self, request: Request, call_next):
        if settings.app_env == "development":
            return await call_next(request)

        client_ip = request.client.host
        key = f"ratelimit:{client_ip}"
        
        try:
            redis_session = RedisSession()
            # Incrementa o contador e define expiração de 1 minuto
            current_hits = await redis_session.redis.incr(key)
            if current_hits == 1:
                await redis_session.redis.expire(key, 60)
            
            # Limite padrão de 100 requisições por minuto
            if current_hits > 100:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return Response(
                    content="Rate limit exceeded. Please try again later.",
                    status_code=429
                )
        except Exception as e:
            # Se o Redis falhar, deixamos passar para não derrubar a API (fail-open)
            logger.error(f"Rate Limit Error (Redis): {e}")
        
        return await call_next(request)
