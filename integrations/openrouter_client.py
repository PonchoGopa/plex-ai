import requests

from config.config import OpenRouterConfig, get_openrouter_config


class OpenRouterClient:
    """
    Cliente delgado para la API de OpenRouter (compatible con el
    formato de chat completions de OpenAI). No conoce nada del
    dominio de Plex; solo sabe mandar mensajes y devolver el texto
    de la respuesta.
    """

    def __init__(self, config: OpenRouterConfig = None):
        self._config = config or get_openrouter_config()

    def complete(self, messages: list[dict], json_mode: bool = True) -> str:
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._config.model,
            "messages": messages,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            f"{self._config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]