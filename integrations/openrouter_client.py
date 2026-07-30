import time

import requests

from config.config import OpenRouterConfig, get_openrouter_config


class OpenRouterClient:
    """
    Cliente para la API de OpenRouter con reintentos por rate-limit
    y, si el modelo principal sigue saturado, cambio automático a
    modelos de respaldo (OPENROUTER_FALLBACK_MODELS).
    """

    MAX_RETRIES_PER_MODEL = 3
    RETRY_BACKOFF_SECONDS = 8  # 8s, 16s, 32s por modelo

    def __init__(self, config: OpenRouterConfig = None):
        self._config = config or get_openrouter_config()

    def complete(self, messages: list[dict], json_mode: bool = True) -> str:
        models_to_try = [self._config.model, *self._config.fallback_models]
        last_error = None

        for model in models_to_try:
            try:
                return self._complete_with_model(model, messages, json_mode)
            except requests.exceptions.HTTPError as error:
                last_error = error
                print(f"[OpenRouter] Modelo '{model}' agotó sus reintentos. "
                      f"Probando siguiente modelo de respaldo (si hay)...")
                continue

        raise last_error

    def _complete_with_model(self, model: str, messages: list[dict], json_mode: bool) -> str:
        payload = self._build_payload(model, messages, json_mode)

        for attempt in range(1, self.MAX_RETRIES_PER_MODEL + 1):
            response = self._post(payload)

            if response.status_code == 400 and json_mode:
                payload = self._build_payload(model, messages, json_mode=False)
                response = self._post(payload)

            if response.status_code == 429 and attempt < self.MAX_RETRIES_PER_MODEL:
                wait_seconds = self.RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(
                    f"[OpenRouter] '{model}' rate-limited upstream "
                    f"(intento {attempt}/{self.MAX_RETRIES_PER_MODEL}). "
                    f"Reintentando en {wait_seconds}s..."
                )
                time.sleep(wait_seconds)
                continue

            if not response.ok:
                raise requests.exceptions.HTTPError(
                    f"{response.status_code} error de OpenRouter ('{model}'): {response.text}",
                    response=response,
                )

            return response.json()["choices"][0]["message"]["content"]

        raise requests.exceptions.HTTPError(
            f"'{model}' siguió respondiendo 429 tras {self.MAX_RETRIES_PER_MODEL} intentos."
        )

    def _build_payload(self, model: str, messages: list[dict], json_mode: bool) -> dict:
        payload = {
            "model": model,
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _post(self, payload: dict):
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        return requests.post(
            f"{self._config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )