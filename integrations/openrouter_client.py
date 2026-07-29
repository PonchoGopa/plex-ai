import time

import requests

from config.config import OpenRouterConfig, get_openrouter_config


class OpenRouterClient:

    MAX_RETRIES = 3
    RETRY_BACKOFF_SECONDS = 5  # se duplica en cada intento: 5s, 10s, 20s

    def __init__(self, config: OpenRouterConfig = None):
        self._config = config or get_openrouter_config()

    def complete(self, messages: list[dict], json_mode: bool = True) -> str:
        payload = self._build_payload(messages, json_mode)

        for attempt in range(1, self.MAX_RETRIES + 1):
            response = self._post(payload)

            if response.status_code == 400 and json_mode:
                payload = self._build_payload(messages, json_mode=False)
                response = self._post(payload)

            if response.status_code == 429 and attempt < self.MAX_RETRIES:
                wait_seconds = self.RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(
                    f"[OpenRouter] Rate limit upstream (intento {attempt}/{self.MAX_RETRIES}). "
                    f"Reintentando en {wait_seconds}s..."
                )
                time.sleep(wait_seconds)
                continue

            if not response.ok:
                raise requests.exceptions.HTTPError(
                    f"{response.status_code} error de OpenRouter: {response.text}",
                    response=response,
                )

            return response.json()["choices"][0]["message"]["content"]

        raise requests.exceptions.HTTPError(
            f"OpenRouter siguió respondiendo 429 después de {self.MAX_RETRIES} intentos. "
            f"El modelo free está saturado; intenta más tarde o usa otro modelo."
        )

    def _build_payload(self, messages: list[dict], json_mode: bool) -> dict:
        payload = {
            "model": self._config.model,
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