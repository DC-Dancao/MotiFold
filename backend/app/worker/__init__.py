from celery import Celery
from app.core.config import settings

celery_app = Celery("motifold")
celery_app.conf.broker_url = settings.REDIS_URL
celery_app.conf.result_backend = settings.REDIS_URL

# Auto-discover tasks from all task modules
celery_app.conf.imports = [
    "app.worker.chat_tasks",
    "app.worker.matrix_tasks",
    "app.worker.blackboard_tasks",
]
