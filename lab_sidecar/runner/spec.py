from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


RunSpecMode = Literal["shell", "argv"]


def display_argv(argv: Sequence[str]) -> str:
    values = list(argv)
    if os.name == "nt":
        return subprocess.list2cmdline(values)
    return shlex.join(values)


class RunSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: RunSpecMode
    command_text: str
    argv: list[str] | None = None
    safe_profile: str | None = None

    @model_validator(mode="after")
    def _validate_mode_shape(self) -> RunSpec:
        if self.mode == "shell":
            if self.argv is not None:
                raise ValueError("shell mode does not accept argv")
            return self
        if not self.argv:
            raise ValueError("argv mode requires non-empty argv")
        return self

    @classmethod
    def shell(cls, command_text: str) -> RunSpec:
        return cls(mode="shell", command_text=command_text, argv=None, safe_profile=None)

    @classmethod
    def argv_command(cls, argv: Sequence[str]) -> RunSpec:
        values = list(argv)
        return cls(
            mode="argv",
            command_text=display_argv(values),
            argv=values,
            safe_profile=None,
        )

    @classmethod
    def from_jsonable(cls, value: Any) -> RunSpec:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls.shell(value)
        return cls.model_validate(value)

    @classmethod
    def from_json(cls, raw: str | bytes | bytearray) -> RunSpec:
        return cls.from_jsonable(json.loads(raw))

    def to_jsonable(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        return json.dumps(self.to_jsonable(), ensure_ascii=False)

    def display_command(self) -> str:
        if self.mode == "argv" and self.argv is not None:
            return display_argv(self.argv)
        return self.command_text
