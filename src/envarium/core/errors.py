"""跨层错误：把底层失败收敛为可展示给用户、带处理建议的操作错误。"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path


class ErrorKind(StrEnum):
    """错误的可操作分类。"""

    NOT_FOUND = "not_found"
    PERMISSION = "permission"
    IN_USE = "in_use"
    INVALID = "invalid"
    COMMAND = "command"


_HINTS: dict[ErrorKind, str] = {
    ErrorKind.NOT_FOUND: "路径已不存在，环境可能已被移动或删除。",
    ErrorKind.PERMISSION: "权限不足，请以管理员身份运行 Envarium，或检查文件是否为只读。",
    ErrorKind.IN_USE: "文件正被其他进程占用，请先关闭使用该环境的终端、编辑器或 Python 进程。",
    ErrorKind.INVALID: "",
    ErrorKind.COMMAND: "可展开设置页的日志查看详细输出。",
}


class AppError(RuntimeError):
    """带分类与处理建议的操作错误。"""

    def __init__(
        self, message: str, *, kind: ErrorKind = ErrorKind.COMMAND, detail: str = ""
    ) -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.detail = detail

    def __str__(self) -> str:
        parts = [self.message]
        if self.detail:
            parts.append(self.detail)
        hint = _HINTS[self.kind]
        if hint:
            parts.append(hint)
        return "\n".join(parts)


def classify_os_error(error: OSError, path: Path) -> AppError:
    """按 Windows 错误码区分权限、占用与路径不存在。"""
    winerror = getattr(error, "winerror", None)
    if isinstance(error, FileNotFoundError) or winerror in (2, 3):
        kind = ErrorKind.NOT_FOUND
    elif winerror in (32, 33):
        kind = ErrorKind.IN_USE
    elif isinstance(error, PermissionError) or winerror == 5:
        kind = ErrorKind.PERMISSION
    else:
        kind = ErrorKind.COMMAND
    return AppError(f"操作失败：{path}", kind=kind, detail=str(error))
