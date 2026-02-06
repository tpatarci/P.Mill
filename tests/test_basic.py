"""Basic smoke tests for Program Mill."""

from backend import __version__
from backend.config import settings


def test_version():
    """Test version is defined."""
    assert __version__ == "0.1.0"


def test_settings_load():
    """Test settings can be loaded."""
    assert settings.default_llm_provider in ["anthropic", "cerebras"]
    assert settings.verification_depth in ["quick", "standard", "rigorous"]
    assert settings.max_tokens_per_analysis > 0
