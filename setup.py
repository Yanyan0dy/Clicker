from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup


def _read_requirements() -> list[str]:
    req = Path(__file__).with_name("requirements.txt")
    if not req.exists():
        return []
    lines: list[str] = []
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


setup(
    name="sequential-clicker",
    version="0.1.0",
    description="基于PyQt6的跨平台桌面端顺序连点器",
    packages=find_packages(),
    install_requires=_read_requirements(),
    python_requires=">=3.10",
    entry_points={"console_scripts": ["sequential-clicker=clicker.main:main"]},
)

