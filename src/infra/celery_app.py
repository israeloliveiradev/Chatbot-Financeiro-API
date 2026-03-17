from celery import Celery
from celery.schedules import crontab

from src.infra.config import settings

celery_app = Celery(
    "chatbot_financeiro",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.alerts"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=False,
)

# Agendamento para bater nas metas e disparar alertas via WhatsApp
celery_app.conf.beat_schedule = {
    "check-spending-alerts-every-hour": {
        "task": "src.workers.alerts.check_spending_alerts",
        "schedule": crontab(minute="0"),  # A cada hora fechada
    }
}
