"""FastAPI 后端：串口服务 + WebSocket 实时推送 + REST 控制接口。

启动后：
- 前端静态资源挂载于 `/`。
- WebSocket `/ws` 向后端订阅实时数据（rx 流 / 周期快照 / 分析结果）。
- REST `/api/*` 用于控制串口、发送数据、手动分析。
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Set

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .analysis import RandomnessAnalyzer, build_chart_data, run_full_analysis
from .serial_service import DEMO_PATTERNS, SerialService

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.serial = SerialService()
    task = asyncio.create_task(_broadcast_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="串口助手 · 随机数分析", version="2.0", lifespan=lifespan)

# 前端静态资源（SPA 风格：先挂 API，再挂静态目录）
app.mount("/vendor", StaticFiles(directory=FRONTEND_DIR / "vendor"), name="vendor")


# ==================== WebSocket 客户端管理器 ====================
class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self.auto_analyze = False

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active:
            return
        text = json.dumps(message, ensure_ascii=False)
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ==================== 请求模型 ====================
class OpenRequest(BaseModel):
    port: str
    baud: int = 115200
    databits: int = 8
    parity: str = "N"
    stopbits: float = 1
    mode: str = "serial"     # "serial" | "sim"
    pattern: str = "random"  # 演示模式的数据图案（mode=sim 时生效）


class SendRequest(BaseModel):
    data: str                 # 原始文本
    fmt: str = "HEX"          # ASCII | HEX | DEC | BIN


class AnalyzeRequest(BaseModel):
    size: int = 1000


# ==================== REST 接口 ====================
@app.get("/api/ports")
def get_ports():
    return {"ports": SerialService.scan_ports()}


@app.get("/api/patterns")
def get_patterns():
    return {"patterns": DEMO_PATTERNS}


@app.get("/api/status")
def get_status():
    return app.state.serial.status()


@app.post("/api/open")
def open_serial(req: OpenRequest):
    try:
        app.state.serial.open(req.port, req.baud, req.databits, req.parity,
                              req.stopbits, mode=req.mode, pattern=req.pattern)
        return {"ok": True, "status": app.state.serial.status()}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/close")
@app.get("/api/close")
def close_serial():
    app.state.serial.close()
    return {"ok": True, "status": app.state.serial.status()}


@app.post("/api/send")
def send_data(req: SendRequest):
    try:
        data = _text_to_bytes(req.data, req.fmt)
        n = app.state.serial.send(data)
        return {"ok": True, "sent": n}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    return _run_analysis(req.size)


@app.post("/api/clear")
@app.get("/api/clear")
def clear():
    app.state.serial.clear()
    return {"ok": True}


# ==================== WebSocket ====================
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "set_auto_analyze":
                manager.auto_analyze = bool(msg.get("enabled", False))
            elif msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# ==================== 分析工具 ====================
def _json_safe(obj: Any) -> Any:
    """递归地把 numpy 标量/数组转换为可 JSON 序列化的原生类型。"""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [_json_safe(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _run_analysis(size: int) -> Dict[str, Any]:
    buf = app.state.serial.buffer
    total = len(buf)
    if total < 100:
        return {"ok": False, "error": "数据量不足 (需要≥100字节)", "total": total}
    size = min(max(size, 100), total)
    data = buf.get_data()[-size:]
    payload = run_full_analysis(data)
    return _json_safe({"ok": True, "total": total,
                       "summary": payload["summary"],
                       "results": payload["results"],
                       "statistics": payload["statistics"]})


# ==================== 后台广播任务 ====================
def _text_to_bytes(text: str, fmt: str) -> bytes:
    text = text.strip() if text else ""
    if fmt == "ASCII":
        return text.encode("utf-8")
    if fmt == "HEX":
        clean = "".join(c for c in text if c.isalnum())
        if len(clean) % 2 != 0:
            raise ValueError("HEX 长度必须为偶数")
        return bytes.fromhex(clean)
    if fmt == "DEC":
        nums = [int(x) for x in text.replace(",", " ").split() if x.strip()]
        if not all(0 <= n <= 255 for n in nums):
            raise ValueError("数字超出 0-255 范围")
        return bytes(nums)
    if fmt == "BIN":
        clean = "".join(c for c in text if c in "01")
        if len(clean) % 8 != 0:
            raise ValueError("二进制长度必须是8的倍数")
        return bytes(int(clean[i:i + 8], 2) for i in range(0, len(clean), 8))
    raise ValueError("未知格式")


async def _broadcast_loop():
    serial = app.state.serial
    last_update = 0.0
    last_analysis = 0.0
    while True:
        # 1) 即时发送新收到的数据块
        drained = 0
        while drained < 500:
            try:
                chunk = serial.new_data.get_nowait()
            except Exception:
                break
            drained += 1
            await manager.broadcast({"type": "rx", "data": chunk.hex(" ").upper(),
                                     "ts": int(time.time() * 1000)})

        now = time.time()
        # 2) 周期快照（状态 + 实时统计 + 图表数据）
        if now - last_update >= 0.5:
            last_update = now
            buf = serial.buffer
            stats = _statistics_for() if len(buf) > 0 else {}
            await manager.broadcast({
                "type": "update",
                "status": serial.status(),
                "stats": stats,
                "charts": build_chart_data(buf),
            })

        # 3) 自动分析（每 3s，若开启且数据足够）
        if manager.auto_analyze and now - last_analysis >= 3.0 and len(serial.buffer) >= 100:
            last_analysis = now
            payload = _run_analysis(1000)
            if payload.get("ok"):
                await manager.broadcast({"type": "analysis", **payload})

        await asyncio.sleep(0.05)


def _statistics_for() -> Dict[str, float]:
    data = app.state.serial.buffer.get_data()
    if len(data) == 0:
        return {}
    return RandomnessAnalyzer.get_statistics(data)


# ==================== 前端静态服务 ====================
@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
