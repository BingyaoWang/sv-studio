from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_FILE = ".svstudio.json"
SOURCE_SUFFIXES = {".sv", ".svh", ".v", ".vh"}


@dataclass
class ProjectConfig:
    name: str = "SystemVerilog Project"
    top: str = "tb_top"
    test: str = "counter_smoke_test"
    simulator: str = "auto"
    sources: list[str] = field(default_factory=lambda: ["rtl/**/*.sv", "tb/**/*.sv"])
    include_dirs: list[str] = field(default_factory=lambda: ["tb"])
    defines: list[str] = field(default_factory=list)
    uvm_home: str = ""
    waveform: str = ".svstudio/waves.vcd"
    plusargs: list[str] = field(default_factory=list)
    custom_compile: str = ""
    custom_run: str = ""

    @classmethod
    def load(cls, root: Path) -> "ProjectConfig":
        path = root / PROJECT_FILE
        if not path.exists():
            config = cls(name=root.name or cls.name)
            config.save(root)
            return config
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def save(self, root: Path) -> None:
        # Keep the project file intentionally small. Toolchain selection,
        # random seeds, verbosity, and command-line details are automatic and
        # must not become user-facing configuration.
        project_data = {
            "name": self.name,
            "top": self.top,
            "test": self.test,
            "sources": self.sources,
            "include_dirs": self.include_dirs,
            "waveform": self.waveform,
        }
        (root / PROJECT_FILE).write_text(
            json.dumps(project_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def source_files(self, root: Path) -> list[Path]:
        found: set[Path] = set()
        for pattern in self.sources:
            for path in root.glob(pattern):
                if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
                    found.add(path.resolve())
        return sorted(found, key=lambda path: path.as_posix().lower())

    def resolved_uvm_home(self, root: Path) -> Path | None:
        raw = self.uvm_home or os.environ.get("UVM_HOME", "")
        if not raw:
            return None
        path = Path(os.path.expandvars(os.path.expanduser(raw)))
        if not path.is_absolute():
            path = root / path
        return path.resolve()


def find_project_root(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / PROJECT_FILE).exists():
            return candidate
    return None
