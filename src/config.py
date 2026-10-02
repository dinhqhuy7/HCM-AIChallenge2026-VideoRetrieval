"""Settings files: one YAML file in, one read-only object out."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


class MissingSetting(ValueError):
    """A value the configs leave empty on purpose, because no published default exists."""


class Settings:
    """A YAML file addressed with dotted keys, e.g. ``settings.get("fusion.rrf_k")``.

    A key that is absent, or present as ``null``, reads as the default. The configs use
    null for "not set": either the library's own default applies, or the value has to be
    chosen by whoever runs the system.
    """

    def __init__(self, values: dict[str, Any], source: str = "<settings>") -> None:
        if not isinstance(values, dict):
            raise ValueError(f"{source}: expected a mapping of keys to values")
        self._values = values
        self.source = source

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        with Path(path).open(encoding="utf-8") as handle:
            return cls(yaml.safe_load(handle) or {}, str(path))

    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self._values
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return default if node is None else node

    def require(self, key: str, hint: str = "") -> Any:
        """The value of ``key``, or an error that names the file and the key to fill in."""
        value = self.get(key)
        if value is None:
            raise MissingSetting(f"{self.source}: set `{key}`" + (f" -- {hint}" if hint else ""))
        return value

    def section(self, key: str) -> "Settings":
        return Settings(self.get(key, {}), f"{self.source}:{key}")

    def to_dict(self) -> dict[str, Any]:
        """A copy of every value, nested ones included."""
        return copy.deepcopy(self._values)
