"""展示文案：领域枚举到界面文本的唯一映射。"""

from envarium.core.models import EnvKind

KIND_LABELS: dict[EnvKind, str] = {
    EnvKind.PYTHON: "Python",
    EnvKind.CONDA: "Conda",
    EnvKind.VENV: "Venv",
}
