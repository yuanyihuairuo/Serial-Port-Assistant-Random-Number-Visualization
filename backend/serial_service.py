"""串口收发服务（线程安全，无 UI 依赖）。

职责：
- 扫描可用串口。
- 在独立后台线程中持续读取串口，写入循环缓冲并投递到新数据队列。
- 通过写队列在主线程安全地把数据发送到串口（避免上下游并发写同一对象）。
- 维护 Tx/Rx 字节计数与连接状态，供上层 WebSocket 广播使用。
- 支持 "sim" 模拟源：无需真实硬件即可全链路测试（数据分析/图表/UI）。

本模块与 FastAPI/WebSocket 解耦：只暴露同步接口 + 内部队列，
由 `main.py` 中的 asyncio 广播任务轮询消费。
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict, List, Optional

import serial
import serial.tools.list_ports
import numpy as np

from .analysis import CircularBuffer

# 与旧版一致的缓冲/限流配置
MAX_BUFFER_SIZE = 100000
RX_FLUSH_INTERVAL = 0.05

# 演示模式：无需硬件即可展示不同随机性特征的数据源
DEMO_PATTERNS = [
    {"key": "random", "label": "均匀随机 (随机性佳)"},
    {"key": "sine",   "label": "正弦波形 (强周期性)"},
    {"key": "biased", "label": "偏置分布 (熵偏低)"},
    {"key": "repeat", "label": "重复序列 (可预测)"},
    {"key": "ramp",   "label": "线性递增 (全可预测)"},
    {"key": "alt",    "label": "高低交替 (串行相关)"},
]


class SerialService:
    def __init__(self, buffer_size: int = MAX_BUFFER_SIZE):
        self._lock = threading.RLock()
        self.ser: Optional[serial.Serial] = None
        self._reader: Optional[threading.Thread] = None
        self._running = False

        self.buffer = CircularBuffer(buffer_size)
        self.new_data: "queue.Queue[bytes]" = queue.Queue()   # 待广播的数据块

        self.connected = False
        self.port_name: Optional[str] = None
        self.baudrate: Optional[int] = None
        self.mode: str = "serial"       # "serial" | "sim"
        self.pattern: str = "random"    # 演示模式下的数据图案（仅模式=sim 时生效）
        self.rx_count = 0
        self.tx_count = 0
        self.last_activity = 0.0
        self._phase = 0                 # 演示模式的连续相位（正弦/渐变保持连贯）

    # ---------- 端口扫描 ----------
    @staticmethod
    def scan_ports() -> List[Dict[str, Any]]:
        ports = []
        for p in sorted(serial.tools.list_ports.comports(), key=lambda x: x.device):
            ports.append({"device": p.device, "description": p.description or "未知设备"})
        return ports

    # ---------- 开关串口 ----------
    def open(self, port: str, baud: int, databits: int = 8, parity: str = "N",
             stopbits: float = 1, mode: str = "serial", pattern: str = "random") -> None:
        self.close()
        self.mode = mode
        self.pattern = pattern if pattern in {p["key"] for p in DEMO_PATTERNS} else "random"
        self._phase = 0
        self.port_name = port
        self.baudrate = baud
        self._running = True
        # 每次开关 / 切换数据源都清空缓冲与计数，让分析从当前源的新数据开始
        self.buffer.clear()
        self.rx_count = 0
        self.tx_count = 0
        while not self.new_data.empty():
            try:
                self.new_data.get_nowait()
            except Exception:
                break

        if mode == "sim":
            # 模拟源：伪随机字节，模拟真实数据流
            self._reader = threading.Thread(target=self._sim_loop, daemon=True)
        else:
            parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN,
                          "O": serial.PARITY_ODD, "M": serial.PARITY_MARK,
                          "S": serial.PARITY_SPACE}
            try:
                self.ser = serial.Serial(port=port, baudrate=baud, bytesize=databits,
                                         parity=parity_map.get(parity, serial.PARITY_NONE),
                                         stopbits=stopbits, timeout=0.05, write_timeout=1.0)
            except Exception as e:  # 打开失败：回滚状态并上抛
                self._running = False
                self.connected = False
                raise
            self.ser.flushInput()
            self._reader = threading.Thread(target=self._read_loop, daemon=True)

        self.connected = True
        self.last_activity = time.time()
        self._reader.start()

    def close(self) -> None:
        self._running = False
        if self._reader and self._reader.is_alive():
            self._reader.join(timeout=1.0)
        self._reader = None
        with self._lock:
            if self.ser:
                try:
                    if self.ser.is_open:
                        self.ser.close()
                except Exception:
                    pass
                self.ser = None
        self.connected = False

    # ---------- 发送 ----------
    def send(self, data: bytes) -> int:
        if not self.connected:
            raise RuntimeError("串口未连接")
        if self.mode == "sim":
            # 模拟发送：直接回显到新数据队列
            self.new_data.put(bytes(data))
            with self._lock:
                self.tx_count += len(data)
            self.last_activity = time.time()
            return len(data)
        with self._lock:
            if self.ser and self.ser.is_open:
                self.ser.write(data)
                self.ser.flush()
                self.tx_count += len(data)
                self.last_activity = time.time()
                return len(data)
        raise RuntimeError("串口未连接")

    # ---------- 读取线程（真实串口） ----------
    def _read_loop(self):
        ser = self.ser
        while self._running:
            try:
                if not ser or not ser.is_open:
                    break
                in_waiting = ser.in_waiting
                if in_waiting > 0:
                    data = ser.read(in_waiting)
                    if data:
                        self._ingest(data)
                else:
                    time.sleep(0.002)
            except Exception:
                break
        # 退出时保留最后一块数据
        self._flush_remaining()
        self.connected = False

    def _flush_remaining(self):
        with self._lock:
            data = self.buffer.get_data()
        # 已通过 _ingest 逐块投递，这里不重复投递

    # ---------- 读取线程（模拟/演示源） ----------
    def _sim_loop(self):
        """演示模式：按所选图案持续生成字节，用于无硬件展示分析功能。"""
        while self._running:
            chunk = self._generate_demo_chunk()
            if chunk:
                self._ingest(chunk)
                self.last_activity = time.time()
            time.sleep(np.random.uniform(0.03, 0.12))

    def _generate_demo_chunk(self) -> bytes:
        """根据 self.pattern 生成一块演示数据（不同图案呈现不同随机性特征）。"""
        n = int(np.random.randint(64, 512))
        rng = np.random.default_rng(int(time.time() * 1000) & 0xFFFFFF)
        p = self.pattern

        if p == "sine":
            # 一个周期的正弦波，呈现极强的周期性与频谱峰值
            period = 64
            t = (np.arange(n) + self._phase) % period
            vals = np.round((np.sin(t / period * 2 * np.pi) + 1) / 2 * 255).astype(np.uint8)
            self._phase = (self._phase + n) % period
            return vals.tobytes()

        if p == "biased":
            # 90% 落在低值区（0-79），熵偏低，卡方/单比特检验易失败
            vals = np.concatenate([
                rng.integers(0, 80, size=int(n * 0.9), dtype=np.uint8),
                rng.integers(0, 256, size=n - int(n * 0.9), dtype=np.uint8),
            ])
            rng.shuffle(vals)
            return vals.tobytes()

        if p == "repeat":
            # 一个固定 32 字节序列不断重复，可预测性强
            seq = np.array([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0,
                            0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88,
                            0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00,
                            0x0F, 0x1E, 0x2D, 0x3C, 0x4B, 0x5A, 0x69, 0x78],
                           dtype=np.uint8)
            reps = (n + len(seq) - 1) // len(seq)
            return np.tile(seq, reps)[:n].tobytes()

        if p == "ramp":
            # 线性递增 0..255 循环，完美可预测
            vals = ((np.arange(n) + self._phase) % 256).astype(np.uint8)
            self._phase = (self._phase + n) % 256
            return vals.tobytes()

        if p == "alt":
            # 交替高低 0x00 / 0xFF，串行相关极强
            vals = (np.arange(n) % 2 * 255).astype(np.uint8)
            return vals.tobytes()

        # 默认：均匀随机（随机性佳）
        return rng.integers(0, 256, size=n, dtype=np.uint8).tobytes()

    # ---------- 数据入库 + 投递 ----------
    def _ingest(self, data: bytes):
        if not data:
            return
        with self._lock:
            self.buffer.append(np.frombuffer(data, dtype=np.uint8))
            self.rx_count += len(data)
            self.last_activity = time.time()
        self.new_data.put(bytes(data))

    # ---------- 状态快照 ----------
    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "connected": self.connected,
                "mode": self.mode,
                "pattern": self.pattern,
                "port": self.port_name,
                "baud": self.baudrate,
                "rx": self.rx_count,
                "tx": self.tx_count,
                "buffer_len": len(self.buffer),
            }

    def clear(self):
        with self._lock:
            self.buffer.clear()
            self.rx_count = 0
            self.tx_count = 0
