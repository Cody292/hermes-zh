"""Hermes-zh official Simplified Chinese language pack."""
from __future__ import annotations

from pathlib import Path

__all__ = ["register"]


def register(ctx) -> None:
    """Register Simplified Chinese locale directory."""
    locales_dir = Path(__file__).parent / "locales"
    if hasattr(ctx, "register_locale_dir"):
        ctx.register_locale_dir(locales_dir)
