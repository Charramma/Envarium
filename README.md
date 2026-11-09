# Envarium

Windows 桌面端 Python 环境发现与管理工具。统一发现官网安装的 Python、Anaconda / Miniconda、`venv` 虚拟环境，并以一个界面集中展示与管理。

当前版本覆盖需求文档的 M1 与 M2：环境发现与展示、创建 / 删除 / 重命名 / 克隆、包列表与安装卸载、终端激活、信息导出与环境对比，以及概览页与全局运行日志。支持 PyInstaller 打包为免安装目录，CI 与跨平台支持待后续版本。

## 特性

- 概览：默认首页展示操作系统、官网 Python 与 pip（支持一键升级）、conda、venv 与 conda 环境清单
- 统一发现：PEP 514 注册表枚举标准 Python、`conda env list --json` 枚举 conda 环境；venv 环境通过创建或「添加已有环境」纳入
- 统一展示：类型徽标、Python 版本、大小、修改时间、可写性与当前 PATH 状态，支持搜索、类型 / 版本筛选与排序
- 环境管理：创建 venv / conda 环境、删除、重命名、克隆，破坏性操作带路径与占用空间确认
- 包管理：读取包列表、流式日志安装 / 卸载
- 快捷操作：打开终端并自动激活、复制路径、导出 requirements.txt / environment.yml / JSON 快照、双环境包差异对比
- 运行日志：底部可折叠终端面板，实时显示执行的命令与流式输出
- 设置：Light / Dark 主题、默认终端、pip / conda 镜像源、诊断日志导出
- 轻量启动：优先读取本地缓存快照，后台刷新真实数据；环境大小异步计算并缓存

## 环境要求

- Windows 10 21H2 及以上 / Windows 11
- 开发需要 Python 3.11+ 与 [uv](https://docs.astral.sh/uv/)

## 开发

```powershell
uv sync                 # 创建 .venv 并安装依赖
uv run envarium         # 启动应用
uv run pytest           # 运行测试
uv run ruff check .     # 静态检查
```

打包（PyInstaller）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

产物：`dist\Envarium\`（免安装目录）与 `dist\Envarium-v<版本>-windows-x64.zip`。构建配置见 [Envarium.spec](Envarium.spec)。

## 代码结构

| 路径 | 职责 |
| --- | --- |
| [src/envarium/core](src/envarium/core) | 领域模型与平台端口协议，零 Qt 依赖 |
| [src/envarium/infrastructure](src/envarium/infrastructure) | 子进程执行器、配置存储、日志 |
| [src/envarium/platforms/windows](src/envarium/platforms/windows) | 注册表 / conda / venv 检测实现 |
| [src/envarium/services](src/envarium/services) | 环境库编排：合并、去重、缓存 |
| [src/envarium/ui](src/envarium/ui) | 主窗口、页面、主题令牌、后台任务 |

分层依赖方向：`ui → services → platforms/core → infrastructure`，`core` 不依赖任何其它层。

## 许可证

[MIT](LICENSE)。第三方组件声明见应用内「关于」页与 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。
