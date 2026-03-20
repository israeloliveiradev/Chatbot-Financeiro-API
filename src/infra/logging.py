import logging
import sys
import uuid
from typing import Optional
from contextvars import ContextVar
from loguru import logger
from rich.console import Console
from rich.logging import RichHandler

# Context variable to store the trace ID for the current request/task
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="n/a")

class InterceptHandler(logging.Handler):
    """
    Default handler from python logging to loguru.
    See: https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        try:
            import inspect
            logging_file = inspect.getfile(logging)
        except Exception:
            logging_file = ""

        frame, depth = logging.currentframe(), 2
        while frame and (frame.f_code.co_filename == logging_file or "logging" in frame.f_code.co_filename.lower()):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def setup_logging(level=logging.INFO):
    # Remove all existing handlers
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(level)

    # Remove default loguru handler
    logger.remove()

    # Add custom handler with rich for beautiful logs in console
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> [Trace: {extra[trace_id]}]",
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Silence noisy loggers
    for logger_name in [
        "uvicorn.access",
        "uvicorn.error",
        "httpcore",
        "httpx",
        "sqlalchemy.engine",
        "amqp",
        "celery",
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Extra silence for SQLAlchemy Engine (user request)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)

def get_logger(name: str):
    # Return a loguru logger bound with trace_id
    return logger.bind(trace_id=trace_id_var.get())

def set_trace_id(trace_id: Optional[str] = None):
    if not trace_id:
        trace_id = str(uuid.uuid4())
    token = trace_id_var.set(trace_id)
    # Also bind it to the logger globally for this context
    logger.configure(extra={"trace_id": trace_id})
    return token
