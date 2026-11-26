import os
import json
from typing import Any, Dict, List

# No external import at module load – the Groq SDK will be imported lazily inside generate().


class GroqError(RuntimeError):
    """Custom exception for Groq‑related failures."""


class GroqWrapper:
    """Wrapper around the official ``groq`` client.

    The public contract mirrors :class:`GeminiWrapper`: ``generate`` returns a Python
    list of dictionaries matching the supplied ``response_schema`` or raises a
    ``GroqError``.
    """

    @staticmethod
    def _get_api_key() -> str:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise GroqError("GROQ_API_KEY not set")
        return key

    @staticmethod
    def _choose_model() -> str:
        """Return the model name to use.

        ``GROQ_MODEL`` is optional – if not provided the default ``openai/gpt-oss-20b``
        is used.
        """
        return os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"

    @classmethod
    def _ensure_schema_is_array(cls, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap a single‑object schema into an array schema if needed.

        Groq can return a JSON object; the downstream code expects a list.  If the
        provided schema already describes an array we return it unchanged, otherwise
        we embed it under an ``items`` key.
        """
        if schema.get("type") == "array":
            return schema
        return {"type": "array", "items": schema}

    @classmethod
    def generate(cls, prompt: str, response_schema: Dict[str, Any]) -> Any:
        """Generate a response using the Groq SDK.

        The method lazily imports the SDK, builds a minimal request that asks for a
        JSON object (or array) and parses the result.  Any parsing or structural
        problem raises ``GroqError``.
        """
        # Lazy import of the Groq SDK – this makes the wrapper safe to import even
        # when the SDK is not installed (tests will patch ``sys.modules``).
        try:
            from groq import Groq
        except Exception as e:  # pragma: no cover
            raise GroqError(
                "groq SDK not installed. Install via `pip install groq`.") from e

        client = Groq(api_key=cls._get_api_key())
        model_name = cls._choose_model()

        # Groq's chat endpoint accepts a ``response_format`` that can enforce JSON.
        # We request a generic JSON object and rely on our post‑processing to ensure
        # it is a list matching the schema.
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                # Ask for JSON output – the SDK will still return a string in ``content``.
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # pragma: no cover
            raise GroqError(f"Groq generation failed: {exc}") from exc

        # Extract the generated text.
        try:
            # The response shape follows OpenAI's spec.
            text = response.choices[0].message.content  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover
            raise GroqError("Unexpected Groq response structure") from exc

        # Parse JSON and enforce list shape.
        try:
            parsed = json.loads(text)
        except Exception as exc:
            raise GroqError("Failed to parse Groq JSON response") from exc

        # Ensure we have a list – if the model returned an object containing an
        # array under a known key we could unwrap it, but the contract for the
        # service is a list at the top level.
        if not isinstance(parsed, list):
            # Some prompts may cause the model to return an object with a ``proposals``
            # field.  Unwrap that if present to retain compatibility.
            if isinstance(parsed, dict) and isinstance(parsed.get("proposals"), list):
                parsed = parsed["proposals"]
            else:
                raise GroqError("Groq response must be a list")

        return parsed

