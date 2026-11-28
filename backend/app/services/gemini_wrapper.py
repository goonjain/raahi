import os
import json
from typing import Any, Dict, List

# No legacy import; all modern SDK work is performed lazily inside generate().


class GeminiError(RuntimeError):
    """Custom exception for Gemini‑related failures."""


class GeminiWrapper:
    """Wrapper around the modern `google.genai` client API.

    - Reads API key from ``GEMINI_API_KEY``.
    - Model name is configurable via ``GEMINI_MODEL``; if not set the wrapper
      queries the account for available Gemini models and selects the first
      non‑preview model.
    - Generates a **JSON array** response using the supplied ``response_schema``.
    """

    @staticmethod
    def _get_api_key() -> str:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise GeminiError("GEMINI_API_KEY not set")
        return key

    @staticmethod
    def _choose_model(client) -> str:
        """Return the model name to use.

        The GEMINI_MODEL environment variable is mandatory. If it is not set, raise GeminiError.
        """
        env_name = os.getenv("GEMINI_MODEL")
        if env_name:
            return env_name
        raise GeminiError("GEMINI_MODEL not set")


        """Return the model name to use.

        If the ``GEMINI_MODEL`` env var is present, use it directly.
        Otherwise list the models from the client and pick the first that contains
        "gemini" and does not contain the obsolete preview tag "preview-0409".
        """
        env_name = os.getenv("GEMINI_MODEL")
        if env_name:
            return env_name
        try:
            models = client.models.list()
            if not models:
                raise GeminiError("No Gemini models available for this account")
            for m in models:
                name = getattr(m, "name", str(m))
                if "gemini" in name.lower() and "preview-0409" not in name.lower():
                    return name
            # Fallback to the first model name if none match the filter.
            return getattr(models[0], "name", str(models[0]))
        except Exception as exc:  # pragma: no cover
            raise GeminiError(f"Unable to retrieve models: {exc}") from exc

    @classmethod
    def _ensure_schema_is_array(cls, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap a single‑object schema into an array schema if needed."""
        if schema.get("type") == "array":
            return schema
        return {"type": "array", "items": schema}

    @classmethod
    def generate(cls, prompt: str, response_schema: Dict[str, Any]) -> Any:
        """Generate a response using the modern ``genai.Client`` API.

        1. Lazily import ``google.genai``.
        2. Initialise ``genai.Client`` with the API key.
        3. Choose a model name via ``_choose_model``.
        4. Build a ``GenerateContentConfig`` requesting JSON output with an array
           schema.
        5. Call ``client.models.generate_content`` with ``model``, ``contents``
           (the prompt string) and ``config``.
        6. Parse and return the JSON payload (a list of proposals).
        """
        # Lazy import of the modern SDK.
        try:
            from google import genai as new_genai
        except Exception as e:  # pragma: no cover
            raise GeminiError(
                "google‑genai SDK not installed. Install via `pip install google‑genai`."
            ) from e

        client = new_genai.Client(api_key=cls._get_api_key())
        model_name = cls._choose_model(client)

        # Build the generation config using the SDK's types.
        try:
            config_cls = new_genai.types.GenerateContentConfig
        except Exception as e:  # pragma: no cover
            raise GeminiError("Unable to access GenerateContentConfig type from SDK") from e

        generation_config = config_cls(
            response_mime_type="application/json",
            response_schema=cls._ensure_schema_is_array(response_schema),
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=generation_config,
            )
        except Exception as exc:  # pragma: no cover
            raise GeminiError(f"Gemini generation failed: {exc}") from exc

        try:
            parsed = json.loads(response.text)
        except Exception as exc:  # pragma: no cover
            raise GeminiError("Failed to parse Gemini JSON response") from exc
        if not isinstance(parsed, list):
            raise GeminiError("Gemini response must be a list")
        return parsed
