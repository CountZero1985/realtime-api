"""Base configuration for all API sessions."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class BaseConfig:
    """Base configuration for all API sessions."""
    api_key: Optional[str] = None
    timeout: float = 30.0
