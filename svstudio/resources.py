from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return a bundled asset path in source and PyInstaller builds."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_root.joinpath(*parts)


def application_icon_path() -> Path:
    return resource_path("assets", "branding", "sv-studio-logo.png")
