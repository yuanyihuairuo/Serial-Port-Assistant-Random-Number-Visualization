#!/bin/bash
# ============================================================
#  串口助手 · 随机数分析 —— 一键启动 (macOS / Linux)
#  双击 macOS 的 start.command，或在终端执行 ./start.sh
# ============================================================
set -e
cd "$(dirname "$0")"

PY=python3
VENV=.venv

echo "=========================================="
echo "  ⚡ 串口助手 · 随机数分析  V2.0"
echo "=========================================="

# 1) 虚拟环境
if [ ! -d "$VENV" ]; then
  echo "[1/3] 创建虚拟环境 ($PY -m venv $VENV) ..."
  $PY -m venv "$VENV"
else
  echo "[1/3] 虚拟环境已存在，跳过。"
fi

# 2) 依赖（用标记文件避免重复安装）
if [ ! -f "$VENV/.installed" ]; then
  echo "[2/3] 安装依赖 (pip install -r requirements.txt) ..."
  "$VENV/bin/python" -m pip install -q \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    -r requirements.txt
  touch "$VENV/.installed"
else
  echo "[2/3] 依赖已安装，跳过。"
fi

# 3) 启动
echo "[3/3] 启动服务，浏览器将自动打开 ..."
exec "$VENV/bin/python" run.py
