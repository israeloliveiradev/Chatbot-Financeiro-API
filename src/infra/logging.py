import logging
import sys
import uuid
from typing import Optional
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger

# Context variable to store the trace ID for the current request/task
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="n/a")

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['trace_id'] = trace_id_var.get()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name

def setup_logging(level=logging.INFO):
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s %(trace_id)s')
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)
    
    # Silence some noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

def get_logger(name: str):
    return logging.getLogger(name)

def set_trace_id(trace_id: Optional[str] = None):
    if not trace_id:
        trace_id = str(uuid.uuid4())
    return trace_id_var.set(trace_id)
