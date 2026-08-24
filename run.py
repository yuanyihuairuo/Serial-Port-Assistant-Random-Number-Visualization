#!/usr/bin/env python3
"""串口助手 · 随机数分析 —— 启动脚本（自动打开浏览器）。

用法:
    python run.py                 # 默认 http://127.0.0.1:8000，自动打开浏览器
    python run.py --port 8080
    python run.py --no-browser    # 不自动打开浏览器
"""
import argparse
import threading
import time
import webbrowser

import uvicorn


def _open_browser(url: str):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="串口助手 · 随机数分析")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"\n  ⚡ 串口助手 · 随机数分析 V2.0")
    print(f"  ➜  访问 {url}\n")

    if not args.no_browser:
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
