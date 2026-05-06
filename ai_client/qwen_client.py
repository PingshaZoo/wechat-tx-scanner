import base64
import io
import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from ai_client.base import BaseAIClient, AIResult
from parser.transaction_parser import parse_ai_response

logger = logging.getLogger("tx_scanner.ai")


class QwenClient(BaseAIClient):
    def __init__(self, config: dict):
        ai_config = config["ai"]
        self.base_url = ai_config["base_url"].rstrip("/")
        self.api_key = ai_config["api_key"]
        self.model = ai_config["model"]
        self.max_tokens = ai_config["max_tokens"]
        self.temperature = ai_config["temperature"]
        self.timeout = ai_config["timeout_seconds"]
        self.max_retries = ai_config["max_retries"]
        self.image_max_side = ai_config["image_max_side"]
        self.image_quality = ai_config["image_quality"]
        self.prompt = self._load_prompt(ai_config["prompt_file"])

    def _load_prompt(self, prompt_file: str) -> str:
        path = Path(prompt_file)
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        logger.warning("Prompt file not found: %s, using default", prompt_file)
        return "Identify if this image contains a transaction record. Reply NOT_TRANSACTION if not, or JSON if yes."

    def _prepare_image(self, image_path: Path) -> str:
        """Resize, compress, and base64-encode an image for the API."""
        img = Image.open(image_path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        # Resize: keep aspect ratio, only downscale
        w, h = img.size
        longest = max(w, h)
        if longest > self.image_max_side:
            scale = self.image_max_side / longest
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.LANCZOS)

        # Compress to JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self.image_quality)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    def _call_api(self, image_path: Path) -> str:
        data_uri = self._prepare_image(image_path)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": self.prompt},
                    ],
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"
        last_error = None

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code == 200:
                    body = resp.json()
                    return body["choices"][0]["message"]["content"]
                else:
                    logger.warning("API error (attempt %d/%d): HTTP %d %s",
                                   attempt + 1, self.max_retries, resp.status_code, resp.text[:200])
                    last_error = f"HTTP {resp.status_code}"
            except requests.RequestException as e:
                logger.warning("API request failed (attempt %d/%d): %s", attempt + 1, self.max_retries, e)
                last_error = str(e)

            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)

        raise RuntimeError(f"API call failed after {self.max_retries} attempts: {last_error}")

    def analyze_image(self, image_path: Path) -> AIResult:
        raw_text = self._call_api(image_path)
        logger.debug("AI raw response: %s", raw_text[:300])

        transaction_data = parse_ai_response(raw_text)
        return AIResult(
            is_transaction=transaction_data is not None,
            transaction_data=transaction_data,
            raw_response=raw_text,
        )

    def check_connectivity(self) -> bool:
        """Test connectivity with a small JPEG (no real image needed)."""
        try:
            # qwen-vl-max requires min 10x10, use 32x32
            img = Image.new("RGB", (32, 32))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                            {"type": "text", "text": "Reply with just: OK"},
                        ],
                    }
                ],
                "max_tokens": 10,
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            url = f"{self.base_url}/chat/completions"
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                logger.info("AI connectivity check passed (%s)", self.model)
                return True
            else:
                logger.error("AI connectivity check failed: HTTP %d %s", resp.status_code, resp.text[:200])
                return False
        except Exception as e:
            logger.error("AI connectivity check failed: %s", e)
            return False
