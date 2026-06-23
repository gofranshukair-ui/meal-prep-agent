from __future__ import annotations

import base64
import re
import zlib
from typing import Any

from app.config import settings


def _normalize_whitespace(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def _remove_repeated_lines(text: str) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines)


def _reduce_long_lists(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if "," in line and len(line) > 120:
            items = [item.strip() for item in line.split(",") if item.strip()]
            if len(items) > 5:
                lines.append(f"{items[0]}, {items[1]}, ... and {len(items) - 2} more items")
                continue
        lines.append(line)
    return "\n".join(lines)


def _summarize_text(text: str, max_length: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary: list[str] = []
    for sentence in sentences:
        candidate = " ".join(summary + [sentence]).strip()
        if len(candidate) > max_length:
            break
        summary.append(sentence.strip())
    output = " ".join(summary).strip()
    if not output:
        output = text[: max_length - 3].rstrip() + "..."
    return output


def compress_text(text: str, max_length: int | None = None) -> str:
    if max_length is None:
        max_length = settings.context_compression_threshold
    text = _normalize_whitespace(text)
    text = _remove_repeated_lines(text)
    text = _reduce_long_lists(text)
    if len(text) <= max_length:
        return text
    return _summarize_text(text, max_length)


def encode_compressed_context(text: str) -> str:
    compressed = zlib.compress(text.encode("utf-8"), level=9)
    return base64.b64encode(compressed).decode("ascii")


def decode_compressed_context(encoded: str) -> str:
    try:
        decoded = base64.b64decode(encoded.encode("ascii"))
        return zlib.decompress(decoded).decode("utf-8")
    except Exception:
        return encoded


def build_compressed_context(preferences: dict[str, Any], meal_plan: str, shopping_list: str | None = None) -> str:
    pieces: list[str] = ["Workflow context summary:", f"Preferences: {preferences}"]
    if meal_plan:
        pieces.append("Compressed meal plan summary:")
        pieces.append(compress_text(meal_plan, int(settings.context_compression_threshold * 0.8)))
    if shopping_list:
        pieces.append("Shopping list preview:")
        pieces.append(compress_text(shopping_list, int(settings.context_compression_threshold * 0.4)))
    return compress_text("\n".join(pieces), settings.context_compression_threshold)
