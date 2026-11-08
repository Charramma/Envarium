"""概览数据汇总：系统、Python/pip、conda 与环境清单的唯一入口。"""

from __future__ import annotations

from collections.abc import Sequence

from envarium.core.models import Environment, EnvKind, OverviewData, PythonToolchain
from envarium.core.ports import LineSink, RuntimeProbe


class OverviewService:
    """对界面暴露的概览唯一入口。"""

    def __init__(self, probe: RuntimeProbe) -> None:
        self._probe = probe

    def snapshot(self, environments: Sequence[Environment]) -> OverviewData:
        """汇总运行时与环境信息；阻塞调用，应由后台任务执行。"""
        return OverviewData(
            system=self._probe.system_info(),
            pythons=self._probe.python_toolchains(
                [item for item in environments if item.kind is EnvKind.PYTHON]
            ),
            conda=self._probe.conda_runtime(),
            venvs=[item for item in environments if item.kind is EnvKind.VENV],
            conda_environments=[
                item for item in environments if item.kind is EnvKind.CONDA
            ],
        )

    def upgrade_pip(self, toolchain: PythonToolchain, log: LineSink) -> None:
        """升级系统 Python 附带的 pip；阻塞调用，应由后台任务执行。"""
        self._probe.upgrade_pip(toolchain.environment.interpreter, log)
