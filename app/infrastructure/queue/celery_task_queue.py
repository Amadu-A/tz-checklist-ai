# app/infrastructure/queue/celery_task_queue.py

from uuid import UUID

from celery import Celery

from app.domain.enums import ChecklistCode


class CeleryTaskQueue:
    """Adapter постановки анализа в shared RabbitMQ через Celery."""

    TASK_NAME = (
        "tz_checklist.process_analysis"
    )

    def __init__(
        self,
        *,
        broker_url: str,
        queue_name: str,
    ) -> None:
        self._queue_name = (
            queue_name
        )

        self._client = Celery(
            "tz_checklist_api_client",
            broker=broker_url,
        )

    def enqueue_analysis(
        self,
        job_id: UUID,
        checklist_code: ChecklistCode,
    ) -> None:
        """Отправить только маленькую команду.

        Сам PDF через RabbitMQ никогда не передаётся.
        """
        self._client.send_task(
            self.TASK_NAME,
            args=[
                str(job_id),
                checklist_code.value,
            ],
            queue=self._queue_name,
        )
