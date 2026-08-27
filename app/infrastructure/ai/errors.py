# app/infrastructure/ai/errors.py


class OllamaRequestTimeoutError(RuntimeError):
    """Ollama не завершил один AI-запрос за допустимое время."""
