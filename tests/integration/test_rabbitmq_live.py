# tests/integration/test_rabbitmq_live.py

from kombu import Connection

from app.core.config import Settings


def test_project_rabbitmq_vhost_is_available() -> None:
    """Проект должен подключаться к своему shared RabbitMQ vhost."""
    settings = Settings()

    with Connection(
        settings.rabbitmq_url,
        connect_timeout=10,
    ) as connection:
        connection.connect()

        assert (
            connection.connected
            is True
        )
