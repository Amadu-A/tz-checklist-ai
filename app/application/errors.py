# app/application/errors.py


class WorkflowError(Exception):
    """Базовая ожидаемая ошибка lifecycle пользовательского задания."""


class InvalidPdfError(WorkflowError):
    """Полученный файл не похож на PDF."""


class UploadTooLargeError(WorkflowError):
    """Пользовательский PDF превышает разрешённый размер."""


class JobNotFoundError(WorkflowError):
    """Задание с указанным request_id не существует."""


class InvalidJobStateError(WorkflowError):
    """Операция несовместима с текущим состоянием задания."""


class ResultNotReadyError(WorkflowError):
    """PDF-результат ещё не сформирован."""


class QueueSubmissionError(WorkflowError):
    """Не удалось надёжно передать задание RabbitMQ."""
    