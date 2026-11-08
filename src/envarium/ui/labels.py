"""展示文案：领域枚举到界面文本的唯一映射。"""

from envarium.core.models import CondaChannel, EnvKind, ExportFormat, TerminalKind

KIND_LABELS: dict[EnvKind, str] = {
    EnvKind.PYTHON: "Python",
    EnvKind.CONDA: "Conda",
    EnvKind.VENV: "Venv",
}

CHANNEL_LABELS: dict[CondaChannel, str] = {
    CondaChannel.DEFAULTS: "defaults（官方源）",
    CondaChannel.CONDA_FORGE: "conda-forge（社区源）",
}

TERMINAL_LABELS: dict[TerminalKind, str] = {
    TerminalKind.POWERSHELL: "PowerShell",
    TerminalKind.CMD: "命令提示符 (cmd)",
    TerminalKind.WINDOWS_TERMINAL: "Windows Terminal",
}

EXPORT_LABELS: dict[ExportFormat, str] = {
    ExportFormat.REQUIREMENTS: "requirements.txt (*.txt)",
    ExportFormat.CONDA_ENV: "environment.yml (*.yml)",
    ExportFormat.JSON: "JSON 快照 (*.json)",
}
