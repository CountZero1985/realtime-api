"""Base session class for all API sessions."""
from abc import ABC, abstractmethod
from typing import Optional
from openai_apis._config import BaseConfig


class BaseSession(ABC):
    """Base class for all API sessions."""

    def __init__(self, config: Optional[BaseConfig] = None):
        self._config = config

    @abstractmethod
    async def close(self) -> None:
        """Close the session and release resources."""
        ...
