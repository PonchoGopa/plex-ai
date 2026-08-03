import time
import requests
from config.config import OpenRouterConfig


class OpenRouterClient:

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, config: OpenRouterConfig):
        self._config = config
        self._models = [config.model] + config.fallback_models

    def complete(self, messages: list[dict], json_mode: bool = False) -> str:
        """
        Intenta completar con el modelo principal y, si falla,
        prueba cada fallback en orden.
        """
        last_error = None

        for model in self._models:
            try:
                return self._complete_with_model(model, messages, json_mode)
            except _ModelNotFoundError as e:
                # 404: este modelo no existe, pasar al siguiente SIN reintentar
                print(f"[OpenRouter] Modelo '{model}' no encontrado (404). Probando siguiente...")
                last_error = e
            except _RateLimitExhaustedError as e:
                # 429 agotado tras reintentos
                print(f"[OpenRouter] Modelo '{model}' agotó reintentos por rate limit. Probando siguiente...")
                last_error = e
            except Exception as e:
                # Error irrecuperable (401, 500, etc.) — no tiene sentido seguir con otros modelos
                raise

        raise RuntimeError(
            f"Todos los modelos fallaron. Último error: {last_error}"
        )

    def _complete_with_model(
        self, model: str, messages: list[dict], json_mode: bool
    ) -> str:
        """
        Llama a un modelo específico con reintentos solo ante 429.
        """
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/plex-ai",
            "X-Title": "plex-ai",
        }

        body: dict = {
            "model": model,
            "messages": messages,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        delay = self._config.retry_delay

        for attempt in range(1, self._config.max_retries + 1):
            response = requests.post(self.API_URL, headers=headers, json=body, timeout=60)

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]

            if response.status_code == 404:
                raise _ModelNotFoundError(
                    f"Modelo '{model}' no encontrado: {response.text}"
                )

            if response.status_code == 429:
                if attempt < self._config.max_retries:
                    print(
                        f"[OpenRouter] '{model}' rate-limited (intento {attempt}/{self._config.max_retries})."
                        f" Reintentando en {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                    continue
                # Agotó todos los reintentos
                raise _RateLimitExhaustedError(
                    f"'{model}' agotó {self._config.max_retries} reintentos por rate limit."
                )

            # Cualquier otro error HTTP → irrecuperable
            response.raise_for_status()

        # No debería llegar aquí, pero por si acaso
        raise RuntimeError(f"Loop de reintentos terminó inesperadamente para '{model}'")

# ---------------------------------------------------------------------------
# Excepciones internas — no deben salir del módulo; el cliente las captura
# ---------------------------------------------------------------------------

class _ModelNotFoundError(Exception):
    """El endpoint del modelo no existe en OpenRouter (HTTP 404)."""


class _RateLimitExhaustedError(Exception):
    """El modelo agotó todos los reintentos por rate limit (HTTP 429)."""
    