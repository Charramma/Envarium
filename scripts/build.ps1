# 构建 Windows 可执行程序并打包为 zip。
#
# 构建前必须剔除 conda 目录：PyInstaller 会从 PATH 解析 DLL 依赖，
# conda 自带的 icuuc.dll 等第三方 DLL 一旦被打进包，会与 Qt6 所需的
# 系统 ICU 冲突，启动时报 "DLL load failed while importing QtGui"。

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw '缺少 .venv，请先运行 uv sync。'
}

$env:PATH = ($env:PATH -split ';' | Where-Object {
    $_ -and $_ -notmatch 'anaconda|miniconda|miniforge|mambaforge'
}) -join ';'

& $python -m PyInstaller --noconfirm Envarium.spec

$version = (& $python -c "import envarium; print(envarium.__version__)").Trim()
$archive = "dist\Envarium-v$version-windows-x64.zip"
if (Test-Path $archive) {
    Remove-Item $archive
}
Compress-Archive -Path 'dist\Envarium' -DestinationPath $archive
Write-Host "已生成 $archive"
