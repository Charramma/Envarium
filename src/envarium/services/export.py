"""环境信息序列化：requirements.txt / environment.yml / JSON 快照。"""

from __future__ import annotations

import json
from collections.abc import Sequence

from envarium.core.errors import AppError, ErrorKind
from envarium.core.models import (
    Environment,
    EnvironmentMetrics,
    EnvKind,
    ExportFormat,
    Package,
)


def render_export(
    environment: Environment,
    packages: Sequence[Package],
    metrics: EnvironmentMetrics | None,
    export_format: ExportFormat,
) -> str:
    if export_format is ExportFormat.REQUIREMENTS:
        return "".join(f"{package.name}=={package.version}\n" for package in packages)

    if export_format is ExportFormat.CONDA_ENV:
        if environment.kind is not EnvKind.CONDA:
            raise AppError(
                "environment.yml 仅适用于 conda 环境。", kind=ErrorKind.INVALID
            )
        dependencies = [
            f"  - {package.name}={package.version}" if package.version else f"  - {package.name}"
            for package in packages
            if package.name.lower() != "python"
        ]
        lines = [
            f"name: {environment.name}",
            "channels:",
            "  - defaults",
            "dependencies:",
            f"  - python={environment.version}" if environment.version else "  - python",
            *dependencies,
        ]
        return "\n".join(lines) + "\n"

    snapshot = {
        "environment": environment.model_dump(mode="json"),
        "metrics": metrics.model_dump(mode="json") if metrics is not None else None,
        "packages": [package.model_dump(mode="json") for package in packages],
    }
    return json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
