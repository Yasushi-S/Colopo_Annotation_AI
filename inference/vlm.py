import base64
import io
import json
import logging
import os
from typing import Any

from PIL import Image

from inference.base import AbstractAnnotationInference
from inference.prompts import ANALYSIS_PROMPT, SYSTEM_PROMPT
from models.annotation import AnnotationCandidate, AnnotationResult

logger = logging.getLogger(__name__)

_VALID_LABELS = {
    "LSIL_like",
    "HSIL_suspicious",
    "cancer_suspicious",
    "inflammation_like",
    "metaplasia_like",
}


def _image_to_base64(image: Image.Image) -> str:
    rgb_image = image.convert("RGB")
    buffer = io.BytesIO()
    rgb_image.save(buffer, format="JPEG", quality=92)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _extract_json(text: str) -> dict[str, Any]:
    logger.debug("VLM raw response: %s", text)

    if "```json" in text:
        start = text.find("```json") + len("```json")
        end = text.find("```", start)
        if end != -1:
            candidate = text[start:end].strip()
            if candidate:
                return json.loads(candidate)

    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end != -1:
            candidate = text[start:end].strip()
            if candidate.startswith("{"):
                return json.loads(candidate)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    return json.loads(text.strip())


def _clamp_ratio(value: float, default: float = 0.5) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, v))


def _dict_to_result(data: dict[str, Any]) -> AnnotationResult:
    candidates = []
    for item in data.get("candidates") or []:
        label = str(item.get("label", "LSIL_like"))
        if label not in _VALID_LABELS:
            label = "HSIL_suspicious"
        rank = item.get("rank")
        if rank is not None:
            try:
                rank = int(rank)
                if rank not in (1, 2, 3):
                    rank = None
            except (TypeError, ValueError):
                rank = None
        findings = item.get("findings") or []
        if not isinstance(findings, list):
            findings = []
        findings = [str(f) for f in findings]
        confidence = item.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = None
        radius = _clamp_ratio(item.get("radius_ratio", 0.05), 0.05)
        radius = max(0.02, min(0.3, radius))
        candidates.append(
            AnnotationCandidate(
                rank=rank,
                x_ratio=_clamp_ratio(item.get("x_ratio", 0.5)),
                y_ratio=_clamp_ratio(item.get("y_ratio", 0.5)),
                radius_ratio=radius,
                label=label,
                findings=findings,
                confidence=confidence,
                reason=str(item.get("reason", "")),
            )
        )
    return AnnotationResult(
        candidates=candidates,
        overall_comment=str(data.get("overall_comment", "")),
    )


class OpenAIAnnotationInference(AbstractAnnotationInference):
    def __init__(self) -> None:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY が設定されていません")
        self.client = OpenAI(api_key=api_key)

    def analyze(self, image: Image.Image) -> AnnotationResult:
        image_b64 = _image_to_base64(image)
        response = self.client.chat.completions.create(
            model="gpt-4o",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                    ],
                },
            ],
        )
        text = response.choices[0].message.content or ""
        logger.info("OpenAI response (first 200chars): %s", text[:200])
        data = _extract_json(text)
        return _dict_to_result(data)


class AnthropicAnnotationInference(AbstractAnnotationInference):
    def __init__(self) -> None:
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY が設定されていません")
        self.client = Anthropic(api_key=api_key)

    def analyze(self, image: Image.Image) -> AnnotationResult:
        image_b64 = _image_to_base64(image)
        response = self.client.messages.create(
            model="claude-opus-4-6",
            system=SYSTEM_PROMPT,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                    ],
                }
            ],
        )
        text_parts = []
        for part in response.content:
            part_text = getattr(part, "text", None)
            if part_text:
                text_parts.append(part_text)
        text = "\n".join(text_parts) if text_parts else ""
        logger.info("Anthropic response (first 200chars): %s", text[:200])
        data = _extract_json(text)
        return _dict_to_result(data)
