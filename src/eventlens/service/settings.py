"""Server-owned settings; API clients cannot select credentials or endpoints."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path

from ..macro.agent import validate_config
from ..llm import ProviderSettings

DEFAULT_CONFIG = {
    'max_calls': 20, 'max_tool_calls': 18, 'max_output_tokens_per_call': 6000,
    'max_input_characters': 160000, 'max_brief_words': 450, 'freshness_days': 45,
}


@dataclass(frozen=True)
class Settings:
    state_dir: Path
    api_token: str = field(repr=False)
    model: str = ''
    max_pending_jobs: int = 50
    config: dict = field(default_factory=lambda: dict(DEFAULT_CONFIG))
    provider: ProviderSettings = field(default_factory=ProviderSettings.from_env)

    def __post_init__(self):
        if len(self.api_token) < 24 or self.api_token.startswith('CHANGE_ME'):
            raise ValueError('EVENTLENS_SERVICE_TOKEN must contain at least 24 characters')
        if not 1 <= self.max_pending_jobs <= 1000:
            raise ValueError('max pending jobs must be 1..1000')
        validate_config(self.config)

    @classmethod
    def from_env(cls):
        config_path = os.getenv('EVENTLENS_CONFIG')
        config = json.loads(Path(config_path).read_text()) if config_path else dict(DEFAULT_CONFIG)
        return cls(Path(os.getenv('EVENTLENS_STATE_DIR', 'work/service')).resolve(),
                   os.getenv('EVENTLENS_SERVICE_TOKEN', ''), os.getenv('EVENTLENS_MODEL', ''),
                   int(os.getenv('EVENTLENS_MAX_PENDING_JOBS', '50')), config)

    @property
    def database(self):
        return self.state_dir / 'service.sqlite'
