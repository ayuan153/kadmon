import os

from pydantic import BaseModel


class Settings(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 200000
    max_iterations: int = 50
    api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
