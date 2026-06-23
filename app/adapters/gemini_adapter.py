from __future__ import annotations

import time
from typing import Any

from google.genai import Client
from google.genai.errors import ClientError, ServerError
from google.genai.types import GenerateContentResponse

from app.config import settings
from app.domain.ports import AIClient
from app.metrics import metrics


def _extract_text(response: GenerateContentResponse) -> str:
    if response is None:
        return ""

    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    if getattr(response, "candidates", None):
        output_parts: list[str] = []
        for candidate in response.candidates or []:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            for part in getattr(content, "parts", []) or []:
                text = getattr(part, "text", None)
                if text:
                    output_parts.append(text)
        if output_parts:
            return "".join(output_parts).strip()

    output_items = getattr(response, "output", None)
    if output_items is not None:
        output_parts = []
        for item in output_items or []:
            if isinstance(item, str):
                output_parts.append(item)
                continue
            content = getattr(item, "content", None)
            if content is None:
                continue
            for part in getattr(content, []) or []:
                text = getattr(part, "text", None)
                if text:
                    output_parts.append(text)
        if output_parts:
            return "".join(output_parts).strip()

    return ""


def _extract_usage(response: GenerateContentResponse) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = 0
    output_tokens = 0
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        total_tokens = getattr(usage, "total_token_count", 0) or 0
        if total_tokens and prompt_tokens:
            output_tokens = max(0, total_tokens - prompt_tokens)
        elif total_tokens:
            output_tokens = total_tokens
    if output_tokens == 0 and getattr(response, "candidates", None):
        candidate_token_total = 0
        for candidate in response.candidates or []:
            candidate_token_total += getattr(candidate, "token_count", 0) or 0
        output_tokens = candidate_token_total
    return prompt_tokens, output_tokens


class GeminiAI(AIClient):
    def __init__(
        self,
        api_key: str = settings.gemini_api_key,
        model_name: str = settings.gemini_model_name,
    ) -> None:
        self.client = Client(api_key=api_key)
        self.model_name = model_name
        self.fallback_model_names = settings.gemini_fallback_model_names

    def _generate_with_model(
        self,
        model_name: str,
        prompt: str,
        max_output_tokens: int,
        temperature: float,
        response_json_schema: dict[str, Any] | None = None,
    ) -> GenerateContentResponse:
        config: dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }
        if response_json_schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_json_schema"] = response_json_schema

        return self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

    def _generate(
        self,
        prompt: str,
        max_output_tokens: int,
        temperature: float,
        request_id: str | None,
        operation_name: str | None,
        response_json_schema: dict[str, Any] | None = None,
    ) -> str:
        start_time = time.time()
        response = None
        first_error: Exception | None = None
        model_names = [self.model_name] + [m for m in self.fallback_model_names if m != self.model_name]

        for candidate_model in model_names:
            try:
                response = self._generate_with_model(
                    model_name=candidate_model,
                    prompt=prompt,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    response_json_schema=response_json_schema,
                )
                self.model_name = candidate_model
                break
            except ServerError as exc:
                first_error = exc
                if exc.code in {429, 500, 503, 504}:
                    continue
                break
            except ClientError as exc:
                first_error = exc
                if exc.code in {404, 429}:
                    continue
                break
            except Exception as exc:
                first_error = exc
                break

        if response is None:
            tried = ", ".join(model_names)
            raise RuntimeError(
                f"Failed to generate text. Tried: {tried}. "
                "Ensure GEMINI_MODEL_NAME is available for your API key. "
                "Use list_models() or update GEMINI_MODEL_NAME in .env."
            ) from first_error

        latency_ms = round((time.time() - start_time) * 1000, 2)
        prompt_tokens, output_tokens = _extract_usage(response)
        cost_usd = round(
            prompt_tokens * settings.gemini_cost_per_prompt_token
            + output_tokens * settings.gemini_cost_per_output_token,
            6,
        )
        summary_prompt = prompt if len(prompt) <= 250 else prompt[:247] + "..."
        if request_id and operation_name:
            metrics.record_agent_call(
                request_id=request_id,
                operation_name=operation_name,
                model_name=self.model_name,
                prompt_tokens=prompt_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                prompt_summary=summary_prompt,
            )

        return _extract_text(response)

    def generate_text(
        self,
        prompt: str,
        max_output_tokens: int = 900,
        temperature: float = 0.3,
        request_id: str | None = None,
        operation_name: str | None = None,
    ) -> str:
        return self._generate(
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            request_id=request_id,
            operation_name=operation_name,
        )

    def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_output_tokens: int = 900,
        temperature: float = 0.3,
        request_id: str | None = None,
        operation_name: str | None = None,
    ) -> str:
        return self._generate(
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            request_id=request_id,
            operation_name=operation_name,
            response_json_schema=schema,
        )
