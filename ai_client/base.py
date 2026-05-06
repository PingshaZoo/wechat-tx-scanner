from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AIResult:
    is_transaction: bool
    transaction_data: dict | None = None
    raw_response: str = ""
    tokens_used: int = 0


class BaseAIClient(ABC):
    @abstractmethod
    def analyze_image(self, image_path: Path) -> AIResult:
        """Send image to vision AI, get classification + extraction result."""
        ...

    @abstractmethod
    def check_connectivity(self) -> bool:
        """Verify API key and endpoint are working."""
        ...
