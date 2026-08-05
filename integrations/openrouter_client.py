"""
Cliente para OpenRouter API.

Manejo de errores:
- 429: rate limit → reintentar con backoff exponencial
- 404: modelo no existe → saltar al siguiente fallback SIN reintentar
- Otros 4xx/5xx: error irrecuperable → lanzar excepción inmediatamente
"""

import time
import requests
from config.config import OpenRouterConfig


class OpenRouterClient:

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, config: OpenRouterConfig = None):
        self._config = config or OpenRouterConfig()
        self._models = [self._config.model] + self._config.fallback_models

    def complete(self, messages: list[dict], json_mode: bool = False) -> str:
        last_error = None

        for model in self._models:
            try:
                return self._complete_with_model(model, messages, json_mode)
            except _ModelNotFoundError as e:
                print(f"[OpenRouter] Modelo '{model}' no encontrado (404). Probando siguiente...")
                last_error = e
            except _RateLimitExhaustedError as e:
                print(f"[OpenRouter] Modelo '{model}' agotó reintentos por rate limit. Probando siguiente...")
                last_error = e
            except Exception:
                raise

        raise RuntimeError(
            f"Todos los modelos fallaron. Último error: {last_error}"
        )

    def _complete_with_model(
        self, model: str, messages: list[dict], json_mode: bool
    ) -> str:
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
            print(f"[OpenRouter] Llamando a '{model}' (intento {attempt}/{self._config.max_retries})... espera hasta 5 min.")
            response = requests.post(self.API_URL, headers=headers, json=body, timeout=300)

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                print(f"[OpenRouter] Respuesta recibida de '{model}' ({len(content)} chars).")
                return content

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
                raise _RateLimitExhaustedError(
                    f"'{model}' agotó {self._config.max_retries} reintentos por rate limit."
                )

            response.raise_for_status()

        raise RuntimeError(f"Loop de reintentos terminó inesperadamente para '{model}'")


# ---------------------------------------------------------------------------
# Excepciones internas
# ---------------------------------------------------------------------------

class _ModelNotFoundError(Exception):
    """El endpoint del modelo no existe en OpenRouter (HTTP 404)."""


class _RateLimitExhaustedError(Exception):
    """El modelo agotó todos los reintentos por rate limit (HTTP 429)."""