#!/usr/bin/env python3

import sys
import time
import queue
import serial
import serial.tools.list_ports
import numpy as np
from datetime import datetime
from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QMessageBox,
    QGroupBox, QStackedWidget, QCheckBox, QTabWidget,
    QFileDialog, QProgressBar, QSpinBox, QFrame, QLineEdit,
    QSplitter, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QTextOption, QColor
import pyqtgraph as pg

# ==================== 全局样式 ====================
APP_STYLE = """
/* ============================================================
   现代 AI Agent 风深色主题（Glassmorphism）
   说明：Qt 的 QSS 不支持 CSS 级 backdrop-filter（无法对背景做真实
   高斯模糊）。这里用“半透明层 + 细边框 + 大圆角 + 柔光阴影”来近似
   毛玻璃质感，深色氛围底色用放射渐变营造环境光晕，Windows/macOS 一致。
   ============================================================ */

QMainWindow, QWidget {
    background-color: #0A0A0A;
    color: #E9E9EC;
    font-family: 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    font-size: 13px;
}

/* 主内容区：顶部偏蓝的环境光晕，模拟 AI Agent 界面的深空氛围 */
#mainContent {
    background: qradialgradient(cx:0.5, cy:0.16, radius:1.05, fx:0.5, fy:0.16,
        stop:0 rgba(96,122,255,0.24), stop:0.32 rgba(48,52,92,0.11),
        stop:0.68 rgba(12,12,14,0.0), stop:1 #0A0A0A);
}

/* ---------- 侧边栏：毛玻璃面板 ---------- */
#sidebarFrame {
    background: rgba(255, 255, 255, 0.028);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    border-top-right-radius: 22px;
    border-bottom-right-radius: 22px;
}
#sidebarTitle {
    font-size: 20px; font-weight: 700; color: #ffffff;
    letter-spacing: 0.3px; margin-bottom: 4px;
}
#sidebarSubtitle {
    font-size: 12px; color: #8C8C95; margin-bottom: 30px;
}
QLabel.formLabel {
    color: #9A9AA3; font-size: 11px; margin-bottom: 8px;
    font-weight: 600; letter-spacing: 1.2px;
}

/* ---------- 下拉框 ---------- */
QComboBox {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px 34px 10px 14px;
    color: #E9E9EC; font-size: 13px; font-weight: 500;
    min-height: 20px;
}
QComboBox:hover { border-color: rgba(255, 255, 255, 0.18); background: rgba(255, 255, 255, 0.06); }
QComboBox:focus { border-color: rgba(122, 140, 255, 0.55); background: rgba(255, 255, 255, 0.05); }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow {
    image: none; border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid #A9A9B1; margin-right: 12px;
}
QComboBox QAbstractItemView {
    background-color: #121218; border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 10px; padding: 6px; color: #E9E9EC;
    selection-background-color: rgba(122, 140, 255, 0.30); outline: none;
}

/* ---------- 工具按钮（发送/接收控制区） ---------- */
QPushButton[btnClass="toolBtn"] {
    background-color: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 12px; color: #C9C9D0; font-weight: 500;
    text-align: left;
}
QPushButton[btnClass="toolBtn"]:hover {
    background-color: rgba(255, 255, 255, 0.07);
    border-color: rgba(255, 255, 255, 0.16); color: #ffffff;
}
QPushButton[btnClass="toolBtn"]:pressed { background-color: rgba(255, 255, 255, 0.03); }
QPushButton[btnClass="toolBtn"][btnState="active-yellow"],
QPushButton[btnClass="toolBtn"][btnState="active-cyan"],
QPushButton[btnClass="toolBtn"]:checked {
    background-color: rgba(122, 140, 255, 0.16);
    border-color: rgba(122, 140, 255, 0.45);
    color: #ffffff; font-weight: 600;
}

/* ---------- 连接按钮：毛玻璃 + 绿/红状态灯 ---------- */
#btnConnect {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 14px;
    padding: 13px 18px 13px 46px;
    min-height: 50px;
    color: #ffffff; font-weight: 600; letter-spacing: 0.4px;
}
#btnConnect:hover { background-color: rgba(255, 255, 255, 0.09); border-color: rgba(255, 255, 255, 0.26); }
#btnConnect:pressed { background-color: rgba(255, 255, 255, 0.03); }
#btnConnect:disabled { background-color: rgba(255, 255, 255, 0.03); color: #8C8C95; }

#btnReconnect, #btnExit {
    background-color: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px; color: #C9C9D0; font-weight: 500;
}
#btnReconnect { padding: 11px; min-height: 42px; margin-top: 2px; }
#btnExit { padding: 7px 18px; font-size: 12px; min-width: 84px; }
#btnReconnect:hover, #btnExit:hover {
    background-color: rgba(255, 255, 255, 0.08); color: #ffffff; border-color: rgba(255, 255, 255, 0.16);
}

/* ---------- 顶部导航栏：毛玻璃胶囊 ---------- */
#topNavBar {
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    padding: 14px 28px;
}

/* ---------- 终端显示区：深色玻璃卡片 ---------- */
#terminalDisplay {
    background-color: rgba(9, 10, 13, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 12px;
    font-family: 'Cascadia Code', 'Consolas', 'Menlo', monospace;
    font-size: 12.5px; color: #E6E6EA;
}

#sendInput {
    background-color: rgba(11, 12, 16, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px; padding: 12px;
    font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 13px; color: #ffffff;
    min-height: 70px;
}
#sendInput:focus { border-color: rgba(122, 140, 255, 0.5); background-color: rgba(14, 15, 20, 0.75); }

/* ---------- 主发送按钮：渐变强调色 ---------- */
#btnSend {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6E82F5, stop:1 #5563E8);
    color: #ffffff; border: none; border-radius: 12px;
    padding: 12px 30px; font-weight: 600; font-size: 14px; min-width: 110px;
}
#btnSend:enabled:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7D90F8, stop:1 #6372EC); }
#btnSend:disabled { background-color: rgba(255, 255, 255, 0.05); color: #6E6E76; }

/* ---------- 底部状态栏 ---------- */
#statusBarFrame {
    background: rgba(255, 255, 255, 0.018);
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    padding: 10px 24px; font-size: 12px; color: #C9C9D0;
}
#statusTag {
    background: rgba(255, 255, 255, 0.06); color: #D5D5DA;
    padding: 4px 12px; border-radius: 8px; font-weight: 600; margin-right: 16px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}
#statusTag[connected="true"] {
    background: rgba(52, 211, 153, 0.16); color: #ffffff; border-color: rgba(52, 211, 153, 0.35);
}

/* ---------- 终端页控制面板 ---------- */
#receivePanel { background: rgba(255, 255, 255, 0.015); border-right: 1px solid rgba(255, 255, 255, 0.05); }
#sendPanel { background: rgba(255, 255, 255, 0.015); border-left: 1px solid rgba(255, 255, 255, 0.05); }
#panelTitle {
    color: #ffffff; font-size: 13px; font-weight: 700;
    letter-spacing: 0.4px; padding-bottom: 8px;
}

/* ---------- QSplitter 拖拽手柄 ---------- */
QSplitter::handle { background: rgba(255, 255, 255, 0.06); }
QSplitter::handle:horizontal { width: 8px; }
QSplitter::handle:vertical { height: 8px; }
QSplitter::handle:hover { background: rgba(122, 140, 255, 0.45); }

/* ---------- 分析页卡片 ---------- */
QGroupBox {
    font-weight: 600; font-size: 13px;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 14px; margin-top: 16px; padding-top: 16px;
    background-color: rgba(255, 255, 255, 0.02); color: #E9E9EC;
}
QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 10px; color: #B4B4BC; font-weight: 600; }

QProgressBar {
    border: none; border-radius: 8px; background: rgba(255, 255, 255, 0.06);
    height: 24px; text-align: center; font-weight: 600; color: #E9E9EC;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6E82F5, stop:1 #2DD4BF);
    border-radius: 8px;
}

QTabWidget::pane { border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 14px; background: rgba(255, 255, 255, 0.015); }
QTabBar::tab {
    background: transparent; border: 1px solid rgba(255, 255, 255, 0.06); border-bottom: none;
    border-top-left-radius: 10px; border-top-right-radius: 10px;
    padding: 9px 20px; margin-right: 6px; color: #A9A9B1; font-weight: 500;
}
QTabBar::tab:selected { background: rgba(122, 140, 255, 0.12); color: #ffffff; border-color: rgba(122, 140, 255, 0.35); }
QTabBar::tab:hover:!selected { background: rgba(255, 255, 255, 0.05); color: #E9E9EC; }

QCheckBox { color: #D5D5DA; font-size: 12px; spacing: 10px; padding: 6px 0; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 6px; border: 1.5px solid rgba(255, 255, 255, 0.20); background: rgba(255, 255, 255, 0.04); }
QCheckBox::indicator:hover { border-color: rgba(122, 140, 255, 0.6); }
QCheckBox::indicator:checked { background: rgba(122, 140, 255, 0.85); border-color: rgba(122, 140, 255, 0.85); }
QCheckBox::indicator:disabled { background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.1); }

/* ---------- 滚动条 ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; border-radius: 5px; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.12); border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.24); }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; border-radius: 5px; }
QScrollBar::handle:horizontal { background: rgba(255, 255, 255, 0.12); border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: rgba(255, 255, 255, 0.24); }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QLabel { color: #D5D5DA; }
"""

# ==================== 性能优化配置 ====================
MAX_TIME_SERIES_POINTS = 2000
MAX_SCATTER_POINTS = 3000
PLOT_UPDATE_INTERVAL = 500          # 绘图节流间隔(ms)：限制主线程重绘频率，高速接收时防卡死
RX_FLUSH_INTERVAL = 0.05            # 串口数据合并发射间隔(s)：子线程把数据攒成块再发信号，降低信号频率
MAX_BUFFER_SIZE = 1048576           # 接收缓冲区上限(字节)
CHAT_MAX_BLOCKS = 2000              # 终端显示最大块数，防止 QTextEdit 内存无限增长导致崩溃
CHAT_MAX_MSG_CHARS = 2000           # 单条消息最长显示字符数，防止超大包刷屏卡顿

# ==================== 核心逻辑类 ====================

class CircularBuffer:
    def __init__(self, max_size: int = 100000):
        self.max_size = max_size
        self.buffer = np.zeros(max_size, dtype=np.uint8)
        self.start_idx = 0
        self.length = 0

    def append(self, data: np.ndarray):
        data_len = len(data)
        if data_len == 0:
            return
        if data_len >= self.max_size:
            data = data[-self.max_size:]
            self.buffer[:] = data
            self.start_idx = 0
            self.length = self.max_size
            return
        end_idx = self.start_idx + self.length
        space_available = self.max_size - self.length
        if data_len > space_available:
            overflow = data_len - space_available
            self.start_idx = (self.start_idx + overflow) % self.max_size
            self.length = self.max_size
        for i in range(data_len):
            pos = (end_idx + i) % self.max_size
            self.buffer[pos] = data[i]
        self.length = min(self.length + data_len, self.max_size)

    def get_data(self) -> np.ndarray:
        if self.length == 0:
            return np.array([], dtype=np.uint8)
        end_idx = self.start_idx + self.length
        if end_idx <= self.max_size:
            return self.buffer[self.start_idx:end_idx].copy()
        else:
            part1 = self.buffer[self.start_idx:]
            part2 = self.buffer[:end_idx % self.max_size]
            return np.concatenate([part1, part2])

    def get_recent_data(self, max_points: int) -> np.ndarray:
        if self.length == 0:
            return np.array([], dtype=np.uint8)
        if self.length <= max_points:
            return self.get_data()
        start = (self.start_idx + self.length - max_points) % self.max_size
        end_idx = self.start_idx + self.length
        if end_idx <= self.max_size:
            return self.buffer[start:end_idx].copy()
        else:
            if start < self.max_size:
                return np.concatenate([self.buffer[start:], self.buffer[:end_idx % self.max_size]])
            else:
                start_rel = start - self.max_size
                return self.buffer[start_rel:end_idx % self.max_size].copy()

    def __len__(self) -> int:
        return self.length

    def clear(self):
        self.start_idx = 0
        self.length = 0


class SerialWorker(QThread):
    """串口读写工作线程。

    线程安全设计：
    - 所有对 serial.Serial 的读/写都只发生在该子线程内（run 循环）。
    - 接收数据会先攒到一块，按间隔/帧边界合并后再用 data_received 信号发到主线程，
      从而把“高速接收”的信号频率压制到 RX_FLUSH_INTERVAL (约20Hz) 以内，
      避免主线程事件循环被海量信号淹没。
    - 主线程发送数据只是 request_send() 往 write_queue 里入队，
      真正的 write() 由子线程消费，杜绝了原先主线程/子线程同时读写同一个
      pyserial 对象导致的竞态与崩溃。
    """

    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    port_closed = pyqtSignal()

    def __init__(self, port_name: str, baudrate: int,
                 bytesize: int = 8, parity: str = 'N', stopbits: float = 1,
                 accumulate_mode: bool = True, buffer_timeout: float = 0.05,
                 max_buffer_size: int = MAX_BUFFER_SIZE,
                 flush_interval: float = RX_FLUSH_INTERVAL):
        super().__init__()
        self.port_name = port_name
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.accumulate_mode = accumulate_mode
        self.buffer_timeout = buffer_timeout
        self.max_buffer_size = max_buffer_size
        self.flush_interval = flush_interval
        self.running = True
        self.serial_port: Optional[serial.Serial] = None
        self._rx_accum = bytearray()      # 合并后的接收缓冲，攒够再发，防止高频小包
        self._last_data_time = 0.0
        self._last_flush_time = 0.0
        self.write_queue: "queue.Queue[bytes]" = queue.Queue()  # 写入请求队列(线程安全)

    def run(self):
        try:
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.buffer_timeout,
                write_timeout=1.0
            )
            self.serial_port.flushInput()
            self._last_flush_time = time.time()
            while self.running:
                try:
                    progressed = self._poll_serial()
                    self._drain_writes()
                    if not progressed:
                        # 线路空闲时睡一小会，避免工作线程忙等烧 CPU
                        self.msleep(2)
                except serial.SerialException as e:
                    if self.running:
                        self.error_occurred.emit(f"串口读写错误: {e}")
                        break
        except Exception as e:
            if self.running:
                self.error_occurred.emit(f"串口连接错误: {e}")
        finally:
            self._safe_close()

    def _poll_serial(self) -> bool:
        now = time.time()
        progressed = False
        if self.serial_port and self.serial_port.is_open and self.serial_port.in_waiting > 0:
            data = self.serial_port.read(self.serial_port.in_waiting)
            if data:
                self._rx_accum.extend(data)
                self._last_data_time = now
                progressed = True
        self._maybe_flush(now)
        return progressed

    def _maybe_flush(self, now):
        if not self._rx_accum:
            return
        should_flush = False
        if len(self._rx_accum) >= self.max_buffer_size:
            should_flush = True          # 超上限立即发，防止内存无限增长
        elif self._last_data_time > 0:
            idle = now - self._last_data_time
            if self.accumulate_mode and idle >= self.buffer_timeout:
                # 累积/成帧模式：数据安静一段后当作一个完整包发射
                should_flush = True
            elif not self.accumulate_mode and (now - self._last_flush_time) >= self.flush_interval:
                # 直通模式：达到合并间隔即发射（限流），避免高频小包刷爆主线程
                should_flush = True
        if should_flush:
            self.data_received.emit(bytes(self._rx_accum))
            self._rx_accum.clear()
            self._last_data_time = 0.0
            self._last_flush_time = time.time()

    def _drain_writes(self):
        while True:
            try:
                data = self.write_queue.get_nowait()
            except queue.Empty:
                break
            try:
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.write(data)
                    self.serial_port.flush()
            except Exception as e:
                if self.running:
                    self.error_occurred.emit(f"串口发送失败: {e}")

    def request_send(self, data: bytes):
        """主线程调用。只把字节入队，绝不在主线程触碰 pyserial 对象。"""
        self.write_queue.put(bytes(data))

    def _safe_close(self):
        try:
            if self._rx_accum:
                self.data_received.emit(bytes(self._rx_accum))
                self._rx_accum.clear()
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                self.port_closed.emit()
        except Exception:
            pass

    def stop(self):
        self.running = False
        self.wait(2000)
        if self.isRunning():
            self.terminate()
        self._safe_close()


class RandomnessAnalyzer:
    @staticmethod
    def chi_square_test(data: np.ndarray) -> dict:
        if len(data) < 256:
            return {"passed": False, "statistic": 0, "msg": "数据量不足256字节"}
        observed, _ = np.histogram(data, bins=256, range=(0, 256))
        expected = len(data) / 256
        chi2 = np.sum((observed - expected) ** 2 / expected)
        passed = chi2 < 310.0
        return {"passed": passed, "statistic": chi2, "msg": f"卡方={chi2:.1f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def runs_test(data: np.ndarray) -> dict:
        if len(data) < 20:
            return {"passed": False, "z_score": 0, "msg": "数据量不足20字节"}
        median = np.median(data)
        binary = (data > median).astype(int)
        runs = 1 + np.sum(binary[1:] != binary[:-1])
        n1, n2 = np.sum(binary), len(binary) - np.sum(binary)
        if n1 == 0 or n2 == 0:
            return {"passed": False, "z_score": 0, "msg": "数据分布极端"}
        mu = (2 * n1 * n2) / (n1 + n2) + 1
        sigma = np.sqrt((2 * n1 * n2 * (2 * n1 * n2 - n1 - n2)) / ((n1 + n2) ** 2 * (n1 + n2 - 1)) + 1e-10)
        z = abs(runs - mu) / sigma if sigma > 1e-10 else 0
        passed = z < 2.58
        return {"passed": passed, "z_score": z, "msg": f"游程Z={z:.2f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def autocorrelation_test(data: np.ndarray, max_lag: int = 20) -> dict:
        if len(data) < 100:
            return {"passed": True, "max_corr": 0, "msg": "数据量不足，跳过"}
        data_norm = (data - np.mean(data)) / (np.std(data) + 1e-10)
        max_lag = min(max_lag, len(data_norm) // 10)
        lags = np.arange(1, max_lag + 1)
        corr = np.array([np.mean(data_norm[:-lag] * data_norm[lag:]) for lag in lags])
        max_corr = np.max(np.abs(corr)) if len(corr) > 0 else 0
        passed = max_corr < 0.1
        return {"passed": passed, "max_corr": max_corr, "msg": f"自相关={max_corr:.3f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def entropy_test(data: np.ndarray) -> dict:
        if len(data) < 10:
            return {"passed": False, "entropy": 0, "msg": "数据量不足"}
        hist, _ = np.histogram(data, bins=256, range=(0, 256))
        probs = hist[hist > 0] / len(data)
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        passed = entropy > 7.5
        return {"passed": passed, "entropy": entropy, "msg": f"熵值={entropy:.2f}bits {'通过' if passed else '偏低'}"}

    @staticmethod
    def monobit_test(data: np.ndarray) -> dict:
        if len(data) < 100:
            return {"passed": False, "statistic": 0, "msg": "数据量不足"}
        bits = np.unpackbits(data.astype(np.uint8))
        ones_count = np.sum(bits)
        n = len(bits)
        s = abs(ones_count - n/2) / np.sqrt(n/4)
        passed = s < 1.96
        return {"passed": passed, "statistic": s, "balance": ones_count/n, "msg": f"比特平衡={ones_count/n:.3f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def frequency_test(data: np.ndarray) -> dict:
        if len(data) < 100:
            return {"passed": False, "statistic": 0, "msg": "数据量不足"}
        low_count = np.sum(data < 128)
        expected = len(data) / 2
        chi2 = ((low_count - expected) ** 2 + (len(data) - low_count - expected) ** 2) / expected
        passed = chi2 < 3.84
        return {"passed": passed, "statistic": chi2, "ratio": low_count/len(data), "msg": f"高低比={low_count/len(data):.3f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def serial_correlation_test(data: np.ndarray) -> dict:
        if len(data) < 100:
            return {"passed": False, "correlation": 0, "msg": "数据量不足"}
        if len(data) > 1:
            x = data[:-1].astype(np.float64)
            y = data[1:].astype(np.float64)
            correlation = np.corrcoef(x, y)[0, 1]
            passed = abs(correlation) < 0.1
        else:
            correlation, passed = 0, True
        return {"passed": passed, "correlation": correlation, "msg": f"相邻相关={correlation:.3f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def spectral_test(data: np.ndarray) -> dict:
        if len(data) < 128:
            return {"passed": False, "peak_ratio": 0, "msg": "数据量不足128字节"}
        fft_data = np.fft.fft(data.astype(np.float64))
        magnitude = np.abs(fft_data[:len(fft_data)//2])
        mean_mag = np.mean(magnitude)
        max_mag = np.max(magnitude)
        peak_ratio = max_mag / mean_mag if mean_mag > 0 else 0
        passed = peak_ratio < 10.0
        return {"passed": passed, "peak_ratio": peak_ratio, "msg": f"频谱峰值比={peak_ratio:.2f} {'通过' if passed else '可能有周期性'}"}

    @staticmethod
    def get_statistics(data: np.ndarray) -> Dict[str, float]:
        if len(data) == 0:
            return {}
        return {
            "mean": float(np.mean(data)), "std": float(np.std(data)),
            "min": float(np.min(data)), "max": float(np.max(data)),
            "range": float(np.max(data) - np.min(data)), "median": float(np.median(data)),
            "variance": float(np.var(data)), "cv": float(np.std(data) / (np.mean(data) + 1e-10)),
            "skewness": float(np.mean(((data - np.mean(data)) / (np.std(data) + 1e-10)) ** 3)),
            "kurtosis": float(np.mean(((data - np.mean(data)) / (np.std(data) + 1e-10)) ** 4))
        }

    @staticmethod
    def comprehensive_score(results: Dict[str, dict]) -> dict:
        score = 0
        if results["chi_square"]["passed"]: score += 20
        elif results["chi_square"].get("statistic", 999) < 350: score += 10
        if results["runs"]["passed"]: score += 15
        elif results["runs"].get("z_score", 99) < 3.0: score += 7
        if results["autocorr"]["passed"]: score += 15
        elif results["autocorr"].get("max_corr", 1) < 0.15: score += 7
        entropy = results["entropy"].get("entropy", 0)
        if entropy >= 7.9: score += 12
        elif entropy >= 7.5: score += 8
        elif entropy >= 7.0: score += 5
        if results.get("monobit", {}).get("passed", False): score += 8
        elif results.get("monobit", {}).get("statistic", 99) < 2.5: score += 4
        if results.get("frequency", {}).get("passed", False): score += 8
        elif results.get("frequency", {}).get("statistic", 99) < 4.0: score += 4
        if results.get("serial_corr", {}).get("passed", False): score += 8
        elif abs(results.get("serial_corr", {}).get("correlation", 1)) < 0.15: score += 4
        if results.get("spectral", {}).get("passed", False): score += 8
        elif results.get("spectral", {}).get("peak_ratio", 99) < 12.0: score += 4

        level = "优秀" if score >= 85 else "良好" if score >= 70 else "合格" if score >= 50 else "待优化"
        issues = []
        if not results["chi_square"]["passed"]: issues.append("字节分布不均匀")
        if not results["runs"]["passed"]: issues.append("序列存在可预测模式")
        if not results["autocorr"]["passed"]: issues.append("相邻数据相关性过高")
        if entropy < 7.5: issues.append("信息熵偏低")
        if not results.get("monobit", {}).get("passed", False): issues.append("比特平衡性不足")
        if not results.get("frequency", {}).get("passed", False): issues.append("高低字节分布不均")
        if not results.get("serial_corr", {}).get("passed", False): issues.append("串行相关性过高")
        if not results.get("spectral", {}).get("passed", False): issues.append("频谱可能存在周期性")
        if not issues: issues.append("各项指标符合随机性要求")
        return {"score": min(100, max(0, score)), "level": level, "issues": issues}


# ==================== 连接按钮（带状态指示灯 + 毛玻璃质感） ====================
class ConnectButton(QPushButton):
    """串口“打开/关闭”按钮。

    在按钮左侧绘制一个绿/红圆点作为动态状态指示灯：
        绿色 (已连接) / 红色 (未连接)。
    配合 QSS 的半透明 rgba 背景 + 圆角 + 阴影，模拟 Windows/macOS 通用的
    Frosted Glass（毛玻璃）质感。Qt 原生控件无法真正对背景做模糊，
    这里用半透明层 + 柔光阴影来近似，跨平台表现一致。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("btnConnect")
        self.setCheckable(False)
        self._connected = False

        # 状态指示灯：一个不拦截鼠标事件的小圆点，作为按钮的子控件平铺在按钮左侧
        self._dot = QLabel(self)
        self._dot.setFixedSize(14, 14)
        self._dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._set_dot_color(False)

        # 毛玻璃质感的柔光阴影（外发光）
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(24)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(248, 113, 113, 60))   # 未连接：淡淡的红晕
        self.setGraphicsEffect(self._glow)

        # “呼吸”呼吸灯动画：连接成功后外发光做柔和缩放，营造通电感
        self._glow_anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._glow_anim.setDuration(2200)
        self._glow_anim.setStartValue(18)
        self._glow_anim.setEndValue(40)
        self._glow_anim.setLoopCount(-1)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

    def _set_dot_color(self, connected: bool):
        color = "#34d399" if connected else "#f87171"
        self._dot.setStyleSheet(
            f"background-color: {color};"
            f"border: 2px solid rgba(255,255,255,0.30);"
            f"border-radius: 7px;"
        )

    def set_connected(self, connected: bool):
        if self._connected == connected:
            return
        self._connected = connected
        self._set_dot_color(connected)

        if connected:
            # 通电：绿色呼吸光晕
            self._glow.setColor(QColor(52, 211, 153, 90))
            self._glow_anim.start()
        else:
            # 断电：停掉呼吸，回到淡红晕
            self._glow_anim.stop()
            self._glow.setBlurRadius(24)
            self._glow.setColor(QColor(248, 113, 113, 60))
        self.update()

    def is_connected(self) -> bool:
        return self._connected

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 圆点垂直居中、水平靠左，落在按钮左内边距内
        self._dot.move(18, (self.height() - self._dot.height()) // 2)


# ==================== 主窗口类 ====================
class MainWindow(QMainWindow):
    # 绘图重绘请求信号：主窗口内部用 Signal/Slot 解耦“数据到达”与“UI 绘制”，
    # 并配合节流定时器把重绘频率限制在 PLOT_UPDATE_INTERVAL 以内，防止 UI 卡死。
    plot_update_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("串口助手-随机数分析")
        self.resize(1400, 900)
        self.setMinimumSize(1100, 700)

        self.is_open = False
        self.worker: Optional[SerialWorker] = None
        self.data_buffer = CircularBuffer(max_size=100000)
        self.rx_format = "HEX"
        self.tx_format = "HEX"
        self.auto_scroll = True
        self._rx_count = 0
        self._tx_count = 0

        self.init_ui()
        self.setStyleSheet(APP_STYLE)
        self.refresh_ports()
        self.connect_signals()

        self.analysis_timer = QTimer()
        self.analysis_timer.setInterval(3000)
        self.analysis_timer.timeout.connect(self.auto_analyze)

        # 绘图节流定时器：限流/防抖，高速接收时最多每 PLOT_UPDATE_INTERVAL 重绘一次
        self.plot_update_timer = QTimer()
        self.plot_update_timer.setInterval(PLOT_UPDATE_INTERVAL)
        self.plot_update_timer.timeout.connect(self.update_all_plots)
        self.plot_update_requested.connect(self._schedule_plot_update)

        self.stats_timer = QTimer()
        self.stats_timer.setInterval(1000)
        self.stats_timer.timeout.connect(self.update_realtime_stats)

        self.auto_send_timer = QTimer()
        self.auto_send_timer.timeout.connect(self.send_data)

    # ---------- UI 构建 ----------
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = self.create_sidebar()
        self.sidebar.setMinimumWidth(276)

        right_widget = QWidget()
        right_widget.setObjectName("mainContent")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.top_nav = self.create_top_nav()
        right_layout.addWidget(self.top_nav)

        self.stacked_widget = QStackedWidget()
        self.page_terminal = self.create_terminal_page()
        self.page_analysis = self.create_analysis_page()
        self.stacked_widget.addWidget(self.page_terminal)
        self.stacked_widget.addWidget(self.page_analysis)
        right_layout.addWidget(self.stacked_widget)

        # 整个窗口：侧边栏 + 主内容 用 QSplitter，侧边栏也可拖拽调整宽度
        self.main_splitter_h = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter_h.setObjectName("mainSplitterH")
        self.main_splitter_h.setChildrenCollapsible(False)
        self.main_splitter_h.addWidget(self.sidebar)
        self.main_splitter_h.addWidget(right_widget)
        self.main_splitter_h.setStretchFactor(0, 0)
        self.main_splitter_h.setStretchFactor(1, 1)
        self.main_splitter_h.setSizes([300, 1100])
        main_layout.addWidget(self.main_splitter_h)

    def create_sidebar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("sidebarFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(28, 32, 28, 32)
        layout.setSpacing(20)

        title_label = QLabel("⚡ 串口配置")
        title_label.setObjectName("sidebarTitle")
        layout.addWidget(title_label)

        subtitle_label = QLabel("Serial Port Configuration")
        subtitle_label.setObjectName("sidebarSubtitle")
        layout.addWidget(subtitle_label)
        layout.addSpacing(12)

        port_label = QLabel("串口端口")
        port_label.setObjectName("formLabel")
        layout.addWidget(port_label)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumHeight(42)
        layout.addWidget(self.port_combo)

        baud_label = QLabel("波特率")
        baud_label.setObjectName("formLabel")
        layout.addWidget(baud_label)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setMinimumHeight(42)
        layout.addWidget(self.baud_combo)

        data_bits_label = QLabel("数据位")
        data_bits_label.setObjectName("formLabel")
        layout.addWidget(data_bits_label)
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(["5", "6", "7", "8"])
        self.data_bits_combo.setCurrentText("8")
        self.data_bits_combo.setMinimumHeight(42)
        layout.addWidget(self.data_bits_combo)

        parity_label = QLabel("校验位")
        parity_label.setObjectName("formLabel")
        layout.addWidget(parity_label)
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd", "Mark", "Space"])
        self.parity_combo.setCurrentText("None")
        self.parity_combo.setMinimumHeight(42)
        layout.addWidget(self.parity_combo)

        stop_bits_label = QLabel("停止位")
        stop_bits_label.setObjectName("formLabel")
        layout.addWidget(stop_bits_label)
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        self.stop_bits_combo.setCurrentText("1")
        self.stop_bits_combo.setMinimumHeight(42)
        layout.addWidget(self.stop_bits_combo)

        # 特殊选项：累积模式
        layout.addSpacing(20)
        self.cb_accumulate_mode = QCheckBox("累积模式 (处理长数据)")
        self.cb_accumulate_mode.setChecked(True)
        self.cb_accumulate_mode.setToolTip("启用时，等待数据间隔超时后发送完整数据包")
        layout.addWidget(self.cb_accumulate_mode)

        layout.addSpacing(24)
        # 带绿/红状态指示灯 + 毛玻璃质感的连接按钮
        self.btn_connect = ConnectButton("连接串口")
        layout.addWidget(self.btn_connect)

        layout.addSpacing(8)
        self.btn_reconnect = QPushButton("重新扫描")
        self.btn_reconnect.setObjectName("btnReconnect")
        layout.addWidget(self.btn_reconnect)

        return frame

    def create_top_nav(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("topNavBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(32, 16, 32, 16)

        layout.addStretch()
        self.mode_switcher = QComboBox()
        self.mode_switcher.addItems(["📡 终端收发", "📊 随机数分析"])
        self.mode_switcher.currentIndexChanged.connect(self.on_mode_changed)
        layout.addWidget(self.mode_switcher)

        return frame

    def create_terminal_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # ---------- 显示区：终端/聊天显示 ----------
        self.chat_box = QTextEdit()
        self.chat_box.setObjectName("terminalDisplay")
        self.chat_box.setReadOnly(True)
        self.chat_box.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        # 限制文档块数，高速接收时防止 QTextEdit 内存无限增长导致界面崩溃
        self.chat_box.document().setMaximumBlockCount(CHAT_MAX_BLOCKS)

        # ---------- 底部控制区：接收控制区 + 发送区（水平 QSplitter，可拖拽） ----------
        receive_panel = self._build_receive_panel()
        send_panel = self._build_send_panel()

        self.control_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.control_splitter.setObjectName("controlSplitter")
        self.control_splitter.setChildrenCollapsible(False)
        self.control_splitter.addWidget(receive_panel)
        self.control_splitter.addWidget(send_panel)
        self.control_splitter.setStretchFactor(0, 0)
        self.control_splitter.setStretchFactor(1, 3)   # 发送区默认更宽，可拖拽调整

        # ---------- 垂直 QSplitter：显示区 vs 底部控制区（可上下拖拽） ----------
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setObjectName("mainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.chat_box)
        self.main_splitter.addWidget(self.control_splitter)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setSizes([600, 260])

        layout.addWidget(self.main_splitter)

        # ---------- 底部状态栏 ----------
        status_frame = QFrame()
        status_frame.setObjectName("statusBarFrame")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.status_tag = QLabel("未连接")
        self.status_tag.setObjectName("statusTag")
        status_layout.addWidget(self.status_tag)

        self.tx_label = QLabel("Tx: 0 Bytes")
        self.rx_label = QLabel("Rx: 0 Bytes")
        status_layout.addWidget(self.tx_label)
        status_layout.addWidget(self.rx_label)

        status_layout.addStretch()
        self.btn_exit = QPushButton("退出程序")
        self.btn_exit.setObjectName("btnExit")
        status_layout.addWidget(self.btn_exit)

        layout.addWidget(status_frame)
        return widget

    def _build_receive_panel(self) -> QWidget:
        """接收控制区：接收格式、自动滚动、导出、清空接收。"""
        panel = QFrame()
        panel.setObjectName("receivePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 12, 10, 12)
        panel_layout.setSpacing(10)

        title = QLabel("📥 接收控制区")
        title.setObjectName("panelTitle")
        panel_layout.addWidget(title)

        self.btn_rx_fmt = QPushButton("接收: ASCII")
        self.btn_rx_fmt.setProperty("btnClass", "toolBtn")
        self.btn_rx_fmt.setProperty("btnState", "active-yellow")
        panel_layout.addWidget(self.btn_rx_fmt)

        self.btn_auto_scroll = QPushButton("📜 自动滚动")
        self.btn_auto_scroll.setProperty("btnClass", "toolBtn")
        self.btn_auto_scroll.setCheckable(True)
        self.btn_auto_scroll.setChecked(True)
        self.btn_auto_scroll.setToolTip("切换自动滚动到底部")
        panel_layout.addWidget(self.btn_auto_scroll)

        self.btn_export = QPushButton("💾 导出")
        self.btn_export.setProperty("btnClass", "toolBtn")
        self.btn_export.setToolTip("导出接收数据为文本文件")
        panel_layout.addWidget(self.btn_export)

        self.btn_clear_rx = QPushButton("🗑️ 清空接收")
        self.btn_clear_rx.setProperty("btnClass", "toolBtn")
        self.btn_clear_rx.setToolTip("清空接收区所有记录")
        panel_layout.addWidget(self.btn_clear_rx)

        panel_layout.addStretch()
        return panel

    def _build_send_panel(self) -> QWidget:
        """发送区：发送格式、清空发送、自动发送、输入框、发送按钮。"""
        panel = QFrame()
        panel.setObjectName("sendPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 12, 16, 12)
        panel_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("📤 发送区")
        title.setObjectName("panelTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        self.cb_auto_send = QCheckBox("自动发送")
        self.cb_auto_send.toggled.connect(self.toggle_auto_send)
        title_row.addWidget(self.cb_auto_send)
        panel_layout.addLayout(title_row)

        self.send_input = QTextEdit()
        self.send_input.setObjectName("sendInput")
        self.send_input.setPlaceholderText("输入要发送的数据...")
        panel_layout.addWidget(self.send_input, 1)

        send_btn_row = QHBoxLayout()
        self.btn_tx_fmt = QPushButton("发送: HEX")
        self.btn_tx_fmt.setProperty("btnClass", "toolBtn")
        self.btn_tx_fmt.setProperty("btnState", "active-cyan")
        send_btn_row.addWidget(self.btn_tx_fmt)

        self.btn_clear_tx = QPushButton("🗑️ 清空发送")
        self.btn_clear_tx.setProperty("btnClass", "toolBtn")
        self.btn_clear_tx.setToolTip("清空发送输入框")
        send_btn_row.addWidget(self.btn_clear_tx)

        send_btn_row.addStretch()
        self.btn_send = QPushButton("发送")
        self.btn_send.setObjectName("btnSend")
        self.btn_send.setEnabled(False)
        send_btn_row.addWidget(self.btn_send)
        panel_layout.addLayout(send_btn_row)

        return panel

    def create_analysis_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        control_bar = QHBoxLayout()
        control_bar.addWidget(QLabel("<span style='color: #8C8C95; font-weight: 600;'>分析最近:</span>"))
        self.analyze_range = QSpinBox()
        self.analyze_range.setRange(100, 100000)
        self.analyze_range.setValue(1000)
        self.analyze_range.setSingleStep(100)
        self.analyze_range.setSuffix(" 字节")
        self.analyze_range.setStyleSheet("padding: 8px 14px; border: 1px solid rgba(255,255,255,0.10); border-radius: 10px; background-color: rgba(255,255,255,0.04); color: #E9E9EC; font-weight: 600; min-width: 150px;")
        control_bar.addWidget(self.analyze_range)

        self.btn_manual_analyze = QPushButton("🚀 立即分析")
        self.btn_manual_analyze.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6E82F5, stop:1 #5563E8); color: #ffffff; border: none; border-radius: 10px; padding: 10px 24px; font-weight: 600; font-size: 13px;")
        control_bar.addWidget(self.btn_manual_analyze)
        control_bar.addStretch()
        layout.addLayout(control_bar)

        # 分析页面：左右两栏用 QSplitter 拖拽调整（统计/评分 vs 图表）
        self.analysis_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.analysis_splitter.setObjectName("analysisSplitter")
        self.analysis_splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        score_group = QGroupBox("📊 综合评分")
        score_layout = QVBoxLayout()
        self.score_label = QLabel("评分: --/100")
        self.score_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.score_label.setStyleSheet("color: #ffffff; margin-bottom: 12px;")
        score_layout.addWidget(self.score_label)

        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(0)
        score_layout.addWidget(self.score_bar)

        self.issues_label = QLabel("等待数据进行分析...")
        self.issues_label.setWordWrap(True)
        self.issues_label.setStyleSheet("color: #A9A9B1; font-size: 12px; margin-top: 12px; line-height: 1.6;")
        score_layout.addWidget(self.issues_label)
        score_group.setLayout(score_layout)
        left_layout.addWidget(score_group)

        stats_group = QGroupBox("📈 实时统计")
        stats_layout = QVBoxLayout()
        self.stat_labels = {}
        stats_keys = [("mean", "平均值"), ("std", "标准差"), ("min", "最小值"), ("max", "最大值"), ("range", "范围"), ("cv", "变异系数")]
        for key, label in stats_keys:
            lbl = QLabel(f"{label}: --")
            lbl.setStyleSheet("font-family: Consolas; font-size: 12px; color: #ffffff; padding: 6px 0; border-bottom: 1px solid #444444;")
            stats_layout.addWidget(lbl)
            self.stat_labels[key] = lbl
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)
        left_layout.addStretch()
        self.analysis_splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QTabWidget()
        self.create_plots()
        right_layout.addWidget(self.tab_widget)
        self.analysis_splitter.addWidget(right_panel)

        self.analysis_splitter.setStretchFactor(0, 1)
        self.analysis_splitter.setStretchFactor(1, 3)
        self.analysis_splitter.setSizes([360, 800])
        layout.addWidget(self.analysis_splitter)
        return widget

    def create_plots(self):
        pg.setConfigOptions(
            antialias=False,
            foreground='#E9E9EC',
            background='#0D0E13',
            enableExperimental=True
        )

        self.plot_time = pg.PlotWidget(title="时域波形")
        self.setup_plot_style(self.plot_time)
        self.curve_time = self.plot_time.plot(pen=pg.mkPen('#8A9CFF', width=1.5))
        self.tab_widget.addTab(self.plot_time, "时域波形")

        self.plot_hist = pg.PlotWidget(title="字节分布")
        self.setup_plot_style(self.plot_hist)
        self.bar_hist = pg.BarGraphItem(x=list(range(256)), height=[0]*256, width=1, brush=pg.mkBrush('#8A9CFF'))
        self.plot_hist.addItem(self.bar_hist)
        self.tab_widget.addTab(self.plot_hist, "分布直方图")

        self.plot_scatter = pg.PlotWidget(title="相邻字节相关性")
        self.setup_plot_style(self.plot_scatter)
        self.scatter_plot = pg.ScatterPlotItem(symbol='o', size=3, brush=pg.mkBrush('#8A9CFFc0'), pen=None, pxMode=True)
        self.plot_scatter.addItem(self.scatter_plot)
        self.tab_widget.addTab(self.plot_scatter, "相关性散点")

        self.plot_autocorr = pg.PlotWidget(title="自相关分析")
        self.setup_plot_style(self.plot_autocorr)
        self.plot_autocorr.setXRange(0, 50)
        self.plot_autocorr.addLine(y=0, pen=pg.mkPen('#6E6E76', style=Qt.PenStyle.DashLine))
        self.plot_autocorr.addLine(y=0.1, pen=pg.mkPen('#B4B4BC', style=Qt.PenStyle.DashLine))
        self.plot_autocorr.addLine(y=-0.1, pen=pg.mkPen('#B4B4BC', style=Qt.PenStyle.DashLine))
        x = np.arange(1, 51)
        y = np.zeros(50)
        self.curve_autocorr = self.plot_autocorr.plot(x, y, pen=pg.mkPen('#8A9CFF', width=1.5), symbol='o', symbolSize=4, symbolBrush='#8A9CFF')
        self.tab_widget.addTab(self.plot_autocorr, "自相关分析")

    def setup_plot_style(self, plot_widget):
        plot_widget.setBackground("#0D0E13")
        plot_widget.getAxis("left").setPen("#D5D5DA")
        plot_widget.getAxis("bottom").setPen("#D5D5DA")
        plot_widget.showGrid(x=True, y=True, alpha=0.16)
        plot_widget.setLabel("left", "Value", color="#B4B4BC")
        plot_widget.setLabel("bottom", "Index", color="#B4B4BC")
        plot_widget.setMouseEnabled(x=True, y=False)

    # ---------- 信号连接 ----------
    def connect_signals(self):
        self.btn_connect.clicked.connect(self.toggle_serial)
        self.btn_reconnect.clicked.connect(self.refresh_ports)
        self.btn_rx_fmt.clicked.connect(lambda: self.toggle_fmt('rx'))
        self.btn_tx_fmt.clicked.connect(lambda: self.toggle_fmt('tx'))
        self.btn_auto_scroll.toggled.connect(lambda checked: setattr(self, 'auto_scroll', checked))
        self.btn_export.clicked.connect(self.save_data)
        self.btn_clear_rx.clicked.connect(self.clear_rx)
        self.btn_clear_tx.clicked.connect(self.clear_tx)
        self.btn_send.clicked.connect(self.send_data)
        self.btn_exit.clicked.connect(self.safe_exit)
        self.btn_manual_analyze.clicked.connect(self.manual_analyze)

    # ---------- 模式切换 ----------
    def on_mode_changed(self, index):
        self.stacked_widget.setCurrentIndex(index)
        if index == 1:
            self.update_realtime_stats()

    # ---------- 格式切换 ----------
    def toggle_fmt(self, target):
        if target == 'rx':
            if self.btn_rx_fmt.text() == "接收: ASCII":
                self.btn_rx_fmt.setText("接收: HEX")
                self.btn_rx_fmt.setProperty("btnState", "active-cyan")
                self.rx_format = "HEX"
            else:
                self.btn_rx_fmt.setText("接收: ASCII")
                self.btn_rx_fmt.setProperty("btnState", "active-yellow")
                self.rx_format = "ASCII"
            self._restyle(self.btn_rx_fmt)
        else:
            if self.btn_tx_fmt.text() == "发送: HEX":
                self.btn_tx_fmt.setText("发送: ASCII")
                self.btn_tx_fmt.setProperty("btnState", "")
                self.tx_format = "ASCII"
            else:
                self.btn_tx_fmt.setText("发送: HEX")
                self.btn_tx_fmt.setProperty("btnState", "active-cyan")
                self.tx_format = "HEX"
            self._restyle(self.btn_tx_fmt)

    def _restyle(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ---------- 串口控制 ----------
    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        if not ports:
            self.port_combo.addItem("未检测到串口")
            return
        for port in sorted(ports, key=lambda x: x.device):
            desc = port.description if port.description else "未知设备"
            self.port_combo.addItem(f"{port.device} - {desc}")

    def toggle_serial(self):
        if not self.is_open:
            self.open_serial()
        else:
            self.close_serial()

    def open_serial(self):
        port_text = self.port_combo.currentText()
        if "未检测到" in port_text:
            QMessageBox.warning(self, "警告", "未检测到串口")
            return
        port_name = port_text.split(" - ")[0]
        try:
            baudrate = int(self.baud_combo.currentText())
            bytesize = int(self.data_bits_combo.currentText())
            parity_map = {"None": 'N', "Even": 'E', "Odd": 'O', "Mark": 'M', "Space": 'S'}
            parity = parity_map[self.parity_combo.currentText()]
            stopbits = float(self.stop_bits_combo.currentText())
        except Exception as e:
            QMessageBox.critical(self, "参数错误", str(e))
            return

        try:
            accumulate_mode = self.cb_accumulate_mode.isChecked()
            self.worker = SerialWorker(
                port_name, baudrate, bytesize, parity, stopbits,
                accumulate_mode=accumulate_mode, buffer_timeout=0.05,
                max_buffer_size=MAX_BUFFER_SIZE,
                flush_interval=RX_FLUSH_INTERVAL
            )
            self.worker.data_received.connect(self.handle_data)
            self.worker.error_occurred.connect(self.handle_error)
            self.worker.port_closed.connect(self.on_port_closed)
            self.worker.start()

            self.is_open = True
            self.btn_connect.setText("断开连接")
            self.btn_connect.set_connected(True)     # 状态灯变绿
            self.btn_send.setEnabled(True)

            self.status_tag.setText("已连接")
            self.status_tag.setProperty("connected", True)
            self._restyle(self.status_tag)

            if self.mode_switcher.currentIndex() == 1:
                self.analysis_timer.start()
            self.stats_timer.start()
            self.add_system_msg(f"成功连接到 {port_name} @ {baudrate}bps")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))

    def close_serial(self):
        if self.worker:
            self.worker.stop()
        self.is_open = False
        self.btn_connect.setText("连接串口")
        self.btn_connect.set_connected(False)    # 状态灯变红
        self.btn_send.setEnabled(False)

        self.status_tag.setText("未连接")
        self.status_tag.setProperty("connected", False)
        self._restyle(self.status_tag)

        self.analysis_timer.stop()
        self.stats_timer.stop()
        self.plot_update_timer.stop()
        self.add_system_msg("串口已关闭")

    def on_port_closed(self):
        self.close_serial()
        self.status_tag.setText("连接异常")

    # ---------- 数据接收 ----------
    def handle_data(self, data_bytes: bytes):
        """主线程槽函数（由 SerialWorker.data_received 信号触达）。

        只做轻量操作：写入循环缓冲、更新计数/显示，然后通过
        plot_update_requested 信号请求一次（节流的）绘图。绝不在此触发重绘图。
        """
        try:
            new_data = np.frombuffer(data_bytes, dtype=np.uint8)
            self.data_buffer.append(new_data)
            self._rx_count += len(data_bytes)
            self.rx_label.setText(f"Rx: {self._rx_count} Bytes")

            # 终端显示：限制单条长度，避免超大包挤爆 QTextEdit
            formatted = self.format_display(data_bytes, self.rx_format)
            if formatted.strip():
                self.add_chat_message("RX", formatted)

            # 请求一次绘图（内部信号/槽 + 节流，把重绘频率压制到 PLOT_UPDATE_INTERVAL）
            self.plot_update_requested.emit()
        except Exception as e:
            self.add_system_msg(f"解析错误: {e}")

    def _schedule_plot_update(self):
        """绘图限流/防抖：只在定时器空闲时启动一次，之后每秒最多重绘一次。

        若定时器已在运行（正等待本轮重绘），此调用不做任何事，避免高频数据
        打爆主线程事件循环。
        """
        if not self.plot_update_timer.isActive():
            self.plot_update_timer.start()

    def update_realtime_stats(self):
        if len(self.data_buffer) == 0:
            return
        data = self.data_buffer.get_data()
        if len(data) > 0:
            stats = RandomnessAnalyzer.get_statistics(data)
            label_texts = {
                "mean": "平均值", "std": "标准差", "min": "最小值", 
                "max": "最大值", "range": "范围", "cv": "变异系数"
            }
            for key, lbl in self.stat_labels.items():
                if key in stats:
                    lbl.setText(f"{label_texts[key]}: {stats[key]:.4f}")

    def update_all_plots(self):
        if len(self.data_buffer) < 2:
            return

        time_data = self.data_buffer.get_recent_data(MAX_TIME_SERIES_POINTS)
        if len(time_data) < 10:
            return

        self.curve_time.setData(time_data)
        self.plot_time.setXRange(0, len(time_data))

        all_data = self.data_buffer.get_data()
        if len(all_data) > 0:
            hist, _ = np.histogram(all_data, bins=256, range=(0, 256))
            self.bar_hist.setOpts(height=hist)

        if len(all_data) >= 2:
            display_limit = min(MAX_SCATTER_POINTS, len(all_data)-1)
            x = all_data[:-1][-display_limit:]
            y = all_data[1:][-display_limit:]
            self.scatter_plot.setData(x, y)

        if len(all_data) > 100:
            try:
                sample_data = all_data[-5000:] if len(all_data) > 5000 else all_data
                data_norm = (sample_data - np.mean(sample_data)) / (np.std(sample_data) + 1e-10)
                max_lag = min(50, len(data_norm) // 10)
                if max_lag >= 10:
                    lags = np.arange(1, max_lag + 1)
                    corr = np.array([np.mean(data_norm[:-lag] * data_norm[lag:]) for lag in lags])
                    self.curve_autocorr.setData(corr, pen=pg.mkPen('#8A9CFF', width=1.5), symbol='o', symbolSize=4, symbolBrush='#8A9CFF')
                    self.plot_autocorr.setXRange(1, max_lag)
            except:
                pass

    # ---------- 发送数据 ----------
    def send_data(self):
        if not self.is_open:
            return
        text = self.send_input.toPlainText().strip()
        if not text:
            return
        try:
            data = self.convert_to_bytes(text, self.tx_format)
            # 只把字节交给工作线程的发送队列，由子线程真正写串口，
            # 彻底避免主线程与子线程同时读写同一个 pyserial 对象造成的竞态。
            if self.worker:
                self.worker.request_send(data)
                self.add_chat_message("TX", self.format_display(data, self.tx_format))
                self.send_input.clear()
                self._tx_count += len(data)
                self.tx_label.setText(f"Tx: {self._tx_count} Bytes")
        except ValueError as e:
            QMessageBox.critical(self, "发送失败", str(e))

    def toggle_auto_send(self, checked):
        if checked:
            self.auto_send_timer.start(1000)
        else:
            self.auto_send_timer.stop()

    # ---------- 格式转换 ----------
    def convert_to_bytes(self, text: str, fmt: str) -> bytes:
        if fmt == "ASCII":
            return text.encode('utf-8')
        elif fmt == "HEX":
            clean = ''.join(c for c in text if c.isalnum())
            if len(clean) % 2 != 0:
                raise ValueError("HEX长度必须为偶数")
            return bytes.fromhex(clean)
        elif fmt == "DEC":
            nums = [int(x.strip()) for x in text.replace(',', ' ').split() if x.strip()]
            if not all(0 <= n <= 255 for n in nums):
                raise ValueError("数字超出0-255范围")
            return bytes(nums)
        elif fmt == "BIN":
            clean = ''.join(c for c in text if c in '01')
            if len(clean) % 8 != 0:
                raise ValueError("二进制长度必须是8的倍数")
            return bytes([int(clean[i:i+8], 2) for i in range(0, len(clean), 8)])
        return b""

    def format_display(self, data: bytes, fmt: str) -> str:
        if fmt == "ASCII":
            try:
                return data.decode('utf-8', errors='replace')
            except:
                return "<Decode Error>"
        elif fmt == "HEX":
            return data.hex(' ').upper()
        elif fmt == "DEC":
            return ' '.join(str(b) for b in data)
        elif fmt == "BIN":
            return ' '.join(f"{b:08b}" for b in data)
        return ""

    # ---------- 消息显示 ----------
    def add_chat_message(self, role: str, content: str):
        time_str = datetime.now().strftime("%H:%M:%S")
        tag = "ASCII" if self.rx_format == "ASCII" else "HEX"
        if role == "TX":
            tag = "TX"
        # 接收信息用靛蓝强调，发送信息用青绿强调
        accent = "#8A9CFF" if role == "RX" else "#2DD4BF"
        tag_color = "#C9C9D0" if role == "RX" else "#8A9CFF"

        # 限制单条消息长度：高速数据包可能很长，只展示前段，防 QTextEdit 卡顿
        if len(content) > CHAT_MAX_MSG_CHARS:
            content = content[:CHAT_MAX_MSG_CHARS] + " …(已截断)"

        content_escaped = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html = f'<div style="margin: 8px 0;">'
        html += f'<span style="color: #6E6E76; font-size: 11px;">{time_str}</span>'
        html += f'<span style="color: {tag_color}; font-size: 11px; margin-left: 12px; font-weight: 600;">{tag}</span>'
        html += f'<div style="margin-top: 6px; background-color: rgba(255,255,255,0.035); border-left: 3px solid {accent}; padding: 8px 12px; border-radius: 8px; font-family: Consolas; font-size: 12px; color: #E6E6EA;">'
        html += f'{content_escaped}'
        html += '</div></div>'
        
        self.chat_box.append(html)
        if self.auto_scroll:
            self.chat_box.verticalScrollBar().setValue(self.chat_box.verticalScrollBar().maximum())

    def add_system_msg(self, msg: str):
        time_str = datetime.now().strftime("%H:%M:%S")
        html = f'<div style="text-align: center; margin: 12px 0;"><span style="background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.07); color: #B4B4BC; padding: 6px 16px; border-radius: 16px; font-size: 11px;">[{time_str}] {msg}</span></div>'
        self.chat_box.append(html)

    # ---------- 分析功能 ----------
    def manual_analyze(self):
        self.run_analysis()

    def auto_analyze(self):
        if self.mode_switcher.currentIndex() == 1 and len(self.data_buffer) >= 100:
            self.run_analysis()

    def run_analysis(self):
        total = len(self.data_buffer)
        if total < 100:
            self.issues_label.setText("数据量不足 (需要≥100字节)")
            return
        range_size = min(self.analyze_range.value(), total)
        analysis_data = self.data_buffer.get_data()[-range_size:]

        results = {
            "chi_square": RandomnessAnalyzer.chi_square_test(analysis_data),
            "runs": RandomnessAnalyzer.runs_test(analysis_data),
            "autocorr": RandomnessAnalyzer.autocorrelation_test(analysis_data),
            "entropy": RandomnessAnalyzer.entropy_test(analysis_data),
            "monobit": RandomnessAnalyzer.monobit_test(analysis_data),
            "frequency": RandomnessAnalyzer.frequency_test(analysis_data),
            "serial_corr": RandomnessAnalyzer.serial_correlation_test(analysis_data),
            "spectral": RandomnessAnalyzer.spectral_test(analysis_data),
        }
        summary = RandomnessAnalyzer.comprehensive_score(results)
        score = summary["score"]
        self.score_bar.setValue(score)

        # 评分颜色随等级渐变：优秀→绿/靛蓝，合格→靛蓝，待优化→琥珀
        color = "#34D399" if score >= 75 else "#6E82F5" if score >= 60 else "#FBBF24"
        self.score_bar.setStyleSheet(f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}, stop:1 #2DD4BF); }}")
        self.score_label.setText(f"评分: {score}/100 [{summary['level']}]")
        self.score_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 18px; margin-bottom: 12px;")
        self.issues_label.setText("\n".join(f"• {issue}" for issue in summary["issues"]))

        test_keys = ["chi_square", "runs", "autocorr", "entropy"]
        log_lines = [results[k]["msg"] for k in test_keys if k in results]
        self.add_system_msg(f"Analysis: {' | '.join(log_lines)}")

    # ---------- 辅助功能 ----------
    def save_data(self):
        if len(self.data_buffer) == 0:
            QMessageBox.information(self, "提示", "暂无数据")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存数据", "data.txt", "Text Files (*.txt)")
        if path:
            data = self.data_buffer.get_data()
            with open(path, 'w') as f:
                f.write(data.hex(' '))
            self.add_system_msg(f"已保存 {len(data)} 字节至 {path}")

    def clear_rx(self):
        self.chat_box.clear()
        self._rx_count = 0
        self.rx_label.setText("Rx: 0 Bytes")

    def clear_tx(self):
        self.send_input.clear()
        self._tx_count = 0
        self.tx_label.setText("Tx: 0 Bytes")

    def safe_exit(self):
        reply = QMessageBox.question(self, "确认退出", "确定要退出程序吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.close()

    def handle_error(self, msg):
        QMessageBox.critical(self, "错误", msg)
        self.close_serial()

    def closeEvent(self, event):
        if self.is_open:
            self.close_serial()
        self.analysis_timer.stop()
        self.stats_timer.stop()
        self.plot_update_timer.stop()
        self.auto_send_timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())