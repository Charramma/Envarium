"""镜像源预设：pip 与 conda 的公共数据定义。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Mirror:
    key: str
    label: str
    pip_index_url: str
    conda_channels: tuple[str, ...]


MIRRORS: tuple[Mirror, ...] = (
    Mirror("official", "官方源（默认）", "", ()),
    Mirror(
        "tsinghua",
        "清华大学 TUNA",
        "https://pypi.tuna.tsinghua.edu.cn/simple",
        (
            "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main",
            "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r",
        ),
    ),
    Mirror(
        "aliyun",
        "阿里云",
        "https://mirrors.aliyun.com/pypi/simple",
        (
            "https://mirrors.aliyun.com/anaconda/pkgs/main",
            "https://mirrors.aliyun.com/anaconda/pkgs/r",
        ),
    ),
    Mirror(
        "ustc",
        "中国科学技术大学",
        "https://mirrors.ustc.edu.cn/pypi/simple",
        (
            "https://mirrors.ustc.edu.cn/anaconda/pkgs/main",
            "https://mirrors.ustc.edu.cn/anaconda/pkgs/r",
        ),
    ),
)
