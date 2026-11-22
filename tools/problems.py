"""The Problem record that every repository validator reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, order=True)
class Problem:
    path: PurePosixPath
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"
