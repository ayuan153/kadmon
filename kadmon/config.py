import os

from pydantic import BaseModel

# Single source of truth for defaults — update here when new models ship
DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-6"
DEFAULT_PROVIDER = "bedrock"
DEFAULT_REGION = "us-east-1"


class Settings(BaseModel):
    model: str = DEFAULT_MODEL
    provider: str = DEFAULT_PROVIDER
    aws_region: str = DEFAULT_REGION
    max_tokens: int = 200000
    max_iterations: int = 50
    api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
