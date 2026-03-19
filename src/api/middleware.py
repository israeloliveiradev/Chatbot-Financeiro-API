import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from src.infra.logging import set_trace_id, trace_id_var

class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract trace_id from headers or generate a new one
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        
        # Set trace_id in context
        token = set_trace_id(trace_id)
        
        try:
            response = await call_next(request)
            # Return trace_id in response headers
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            # Clean up context
            trace_id_var.reset(token)
