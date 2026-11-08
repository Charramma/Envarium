"""Windows 环境操作：创建、删除、重命名、克隆、包管理与终端唤起。"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from envarium.core.errors import AppError, ErrorKind, classify_os_error
from envarium.core.mirrors import Mirror
from envarium.core.models import (
    CondaChannel,
    Environment,
    EnvKind,
    Package,
    TerminalKind,
)
from envarium.core.ports import LineSink
from envarium.infrastructure.filesystem import remove_tree, rename_directory
from envarium.infrastructure.mirrors import PIP_INI, write_conda_mirror, write_pip_mirror
from envarium.infrastructure.subprocess_runner import CommandResult, SubprocessRunner
from envarium.platforms.windows.conda_adapter import find_conda

logger = logging.getLogger(__name__)

_CREATE_TIMEOUT = 1200.0
_QUERY_TIMEOUT = 180.0
_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def _check(result: CommandResult) -> CommandResult:
    if result.ok:
        return result
    detail = (result.stderr or result.stdout).strip()
    message = f"命令返回码 {result.returncode}：{' '.join(result.command)}"
    raise AppError(message, detail=detail[-2000:])


def _stable_python_versions(payload: str) -> list[str]:
    """从 conda search 的 JSON 结果提取稳定三段版本号，由新到旧。"""
    versions = {
        item["version"]
        for items in json.loads(payload).values()
        for item in items
        if re.fullmatch(r"\d+\.\d+\.\d+", item["version"])
    }
    return sorted(
        versions,
        key=lambda version: tuple(int(part) for part in version.split(".")),
        reverse=True,
    )


class WindowsOperations:
    """实现 EnvironmentOperator 协议。"""

    def __init__(self, runner: SubprocessRunner, conda: Path | None = None) -> None:
        self._runner = runner
        self._conda_path = conda
        self._python_versions: dict[CondaChannel, list[str]] = {}

    def _conda(self) -> Path:
        executable = self._conda_path or find_conda()
        if executable is None:
            raise AppError(
                "未找到 conda 可执行文件，请确认已安装 Anaconda / Miniconda。",
                kind=ErrorKind.NOT_FOUND,
            )
        return executable

    def _conda_root(self) -> Path:
        return self._conda().parent.parent

    def create_venv(
        self, interpreter: Path, target: Path, *, system_site_packages: bool
    ) -> None:
        if target.exists():
            if not target.is_dir():
                raise AppError(f"目标路径已存在同名文件：{target}", kind=ErrorKind.INVALID)
            try:
                if any(target.iterdir()):
                    raise AppError(f"目标目录非空：{target}", kind=ErrorKind.INVALID)
            except OSError as error:
                raise classify_os_error(error, target) from error
        command: list[str | Path] = [interpreter, "-m", "venv"]
        if system_site_packages:
            command.append("--system-site-packages")
        command.append(target)
        _check(self._runner.run(command, timeout=_CREATE_TIMEOUT))
        logger.info("已创建 venv：%s", target)

    def create_conda(
        self, name: str, python_version: str, channel: CondaChannel
    ) -> None:
        # conda 不指定包会创建空环境（没有 python.exe），必须显式安装 python
        spec = f"python={python_version}" if python_version else "python"
        command = [self._conda(), "create", "-y", "-n", name, "-c", channel, spec]
        _check(self._runner.run(command, timeout=_CREATE_TIMEOUT))
        logger.info("已创建 conda 环境：%s", name)

    def list_conda_python_versions(self, channel: CondaChannel) -> list[str]:
        cached = self._python_versions.get(channel)
        if cached is None:
            cached = self._python_versions[channel] = self._query_python_versions(
                channel
            )
        return list(cached)

    def _query_python_versions(self, channel: CondaChannel) -> list[str]:
        """优先读 conda 本地索引（数秒返回），索引不可用时回退联网查询。"""
        for extra in (["--offline"], []):
            result = self._runner.run(
                [self._conda(), "search", "python", "--json", *extra, "-c", channel],
                timeout=_QUERY_TIMEOUT,
            )
            if result.ok:
                versions = _stable_python_versions(result.stdout)
                if versions:
                    return versions
        raise AppError(
            "无法获取 conda 可用的 Python 版本。",
            detail=(result.stderr or result.stdout).strip()[-1000:],
        )

    def remove(self, environment: Environment) -> None:
        if environment.kind is EnvKind.CONDA:
            _check(
                self._runner.run(
                    [self._conda(), "env", "remove", "-y", "-p", str(environment.path)],
                    timeout=_CREATE_TIMEOUT,
                )
            )
            if environment.path.exists():
                remove_tree(environment.path)
            return
        remove_tree(environment.path)

    def rename(self, environment: Environment, new_name: str) -> None:
        if environment.kind is EnvKind.CONDA:
            _check(
                self._runner.run(
                    [self._conda(), "rename", "-p", str(environment.path), new_name],
                    timeout=_CREATE_TIMEOUT,
                )
            )
            return
        rename_directory(environment.path, environment.path.with_name(new_name))

    def clone(self, environment: Environment, new_name: str) -> None:
        _check(
            self._runner.run(
                [
                    self._conda(),
                    "create",
                    "-y",
                    "--clone",
                    str(environment.path),
                    "-n",
                    new_name,
                ],
                timeout=_CREATE_TIMEOUT,
            )
        )
        logger.info("已克隆环境：%s -> %s", environment.name, new_name)

    def list_packages(self, environment: Environment) -> list[Package]:
        if environment.kind is EnvKind.CONDA:
            result = _check(
                self._runner.run(
                    [self._conda(), "list", "-p", str(environment.path), "--json"],
                    timeout=_QUERY_TIMEOUT,
                )
            )
            return self._parse_packages(result.stdout, "name", "version")

        result = _check(
            self._runner.run(
                [environment.interpreter, "-m", "pip", "list", "--format=json"],
                timeout=_QUERY_TIMEOUT,
            )
        )
        return self._parse_packages(result.stdout, "name", "version")

    @staticmethod
    def _parse_packages(payload: str, name_key: str, version_key: str) -> list[Package]:
        try:
            items = json.loads(payload)
        except json.JSONDecodeError as error:
            raise AppError("无法解析包列表输出。", detail=str(error)) from error
        return [
            Package(
                name=str(item.get(name_key, "")),
                version=str(item.get(version_key, "")),
            )
            for item in items
            if item.get(name_key)
        ]

    def install(self, environment: Environment, specs: Sequence[str], log: LineSink) -> None:
        specs = [spec.strip() for spec in specs if spec.strip()]
        if not specs:
            raise AppError("请填写要安装的包。", kind=ErrorKind.INVALID)
        if environment.kind is EnvKind.CONDA:
            command = [self._conda(), "install", "-y", "-p", str(environment.path), *specs]
        else:
            command = [environment.interpreter, "-m", "pip", "install", *specs]
        self._run_stream(command, environment, log, action="安装")

    def uninstall(self, environment: Environment, name: str, log: LineSink) -> None:
        if environment.kind is EnvKind.CONDA:
            command = [self._conda(), "remove", "-y", "-p", str(environment.path), name]
        else:
            command = [environment.interpreter, "-m", "pip", "uninstall", "-y", name]
        self._run_stream(command, environment, log, action="卸载")

    def _run_stream(
        self,
        command: Sequence[str | Path],
        environment: Environment,
        log: LineSink,
        *,
        action: str,
    ) -> None:
        returncode = self._runner.stream(
            command, on_line=log, cwd=environment.path if environment.path.is_dir() else None
        )
        if returncode != 0:
            raise AppError(f"{action}失败（返回码 {returncode}），详见上方输出。")

    def activation_command(self, environment: Environment, terminal: TerminalKind) -> str:
        use_cmd = terminal is TerminalKind.CMD
        if environment.kind is EnvKind.CONDA:
            if use_cmd:
                activate = self._conda_root() / "Scripts" / "activate.bat"
                return f'call "{activate}" "{environment.path}"'
            return (
                f'& "{self._conda()}" shell.powershell hook | Out-String | Invoke-Expression; '
                f'conda activate "{environment.path}"'
            )
        if environment.kind is EnvKind.VENV:
            if use_cmd:
                return f'call "{environment.path / "Scripts" / "activate.bat"}"'
            return f'& "{environment.path / "Scripts" / "Activate.ps1"}"'
        if use_cmd:
            return f'set "PATH={environment.path};%PATH%"'
        return f'$env:Path = "{environment.path};" + $env:Path'

    def configure_mirror(self, mirror: Mirror) -> None:
        try:
            write_pip_mirror(mirror.pip_index_url)
        except OSError as error:
            raise classify_os_error(error, PIP_INI) from error
        conda = self._conda_path or find_conda()
        if conda is not None:
            write_conda_mirror(self._runner, conda, mirror.conda_channels)
        logger.info("已切换镜像源：%s", mirror.label)

    def open_terminal(self, environment: Environment, terminal: TerminalKind) -> None:
        if not environment.path.is_dir():
            raise AppError(f"环境路径不存在：{environment.path}", kind=ErrorKind.NOT_FOUND)
        command = self.activation_command(environment, terminal)
        args: list[str]
        if terminal is TerminalKind.CMD:
            args = ["cmd.exe", "/k", command]
        else:
            args = ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", command]
            if terminal is TerminalKind.WINDOWS_TERMINAL:
                terminal_app = shutil.which("wt")
                if terminal_app is not None:
                    args = [terminal_app, "-d", str(environment.path), *args]
        try:
            subprocess.Popen(args, cwd=environment.path, creationflags=_NEW_CONSOLE)
        except OSError as error:
            raise classify_os_error(error, environment.path) from error
