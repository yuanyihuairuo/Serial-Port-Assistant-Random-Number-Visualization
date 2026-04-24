import sys
import serial
import serial.tools.list_ports
import numpy as np
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QComboBox, QPushButton,
                             QTextEdit, QMessageBox, QGroupBox, QSplitter,
                             QCheckBox, QRadioButton, QTabWidget,
                             QFileDialog, QProgressBar, QSpinBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QTextOption
import pyqtgraph as pg

APP_STYLE = """
QMainWindow, QWidget { background-color: #1e1e24; color: #e0e0e0; }
QGroupBox { font-weight: bold; border: 1px solid #3a3a45; border-radius: 6px; margin-top: 8px; padding-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #a0a0b0; }
QComboBox, QTextEdit, QLineEdit, QSpinBox { background-color: #2a2a32; border: 1px solid #3a3a45; border-radius: 4px; padding: 6px; color: #e0e0e0; }
QPushButton { background-color: #3a506b; color: white; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
QPushButton:hover { background-color: #4a6fa5; }
QPushButton:pressed { background-color: #2c3e50; }
QPushButton#saveBtn { background-color: #2d6a4f; }
QProgressBar { border: 1px solid #3a3a45; border-radius: 4px; background: #2a2a32; }
QProgressBar::chunk { background: #00ff88; border-radius: 3px; }
QScrollBar:vertical { background: #2a2a32; width: 8px; }
QScrollBar::handle:vertical { background: #4a4a5a; border-radius: 4px; min-height: 20px; }
"""

class SerialWorker(QThread):
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    port_closed = pyqtSignal()

    def __init__(self, port_name, baudrate):
        super().__init__()
        self.port_name = port_name
        self.baudrate = baudrate
        self.running = True
        self.serial_port = None

    def run(self):
        try:
            self.serial_port = serial.Serial(self.port_name, self.baudrate, timeout=0.05)
            while self.running:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    self.data_received.emit(data)
        except Exception as e:
            if self.running:
                self.error_occurred.emit(str(e))
        finally:
            self._safe_close()

    def _safe_close(self):
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
        except (OSError, Exception):
            pass

    def stop(self):
        self.running = False
        self.wait(2000)
        if self.isRunning():
            self.terminate()
        self.port_closed.emit()

class RandomnessAnalyzer:
    @staticmethod
    def chi_square_test(data: np.ndarray) -> dict:
        if len(data) < 256:
            return {"passed": False, "statistic": 0, "msg": "数据量不足256字节"}
        observed, _ = np.histogram(data, bins=256, range=(0, 256))
        expected = len(data) / 256
        chi2 = np.sum((observed - expected)**2 / expected)
        critical = 310.0
        passed = chi2 < critical
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
        sigma = np.sqrt((2 * n1 * n2 * (2 * n1 * n2 - n1 - n2)) / ((n1 + n2)**2 * (n1 + n2 - 1)) + 1e-10)
        z = abs(runs - mu) / sigma if sigma > 1e-10 else 0
        passed = z < 2.58
        return {"passed": passed, "z_score": z, "msg": f"游程Z={z:.2f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def autocorrelation_test(data: np.ndarray, max_lag: int = 20) -> dict:
        """优化：使用Numpy向量化计算自相关系数"""
        if len(data) < 100:
            return {"passed": True, "max_corr": 0, "msg": "数据量不足，跳过"}
        data_norm = (data - np.mean(data)) / (np.std(data) + 1e-10)
        max_lag = min(max_lag, len(data_norm)//10)
        
        # 使用向量化计算替代循环
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
    def comprehensive_score(results: dict) -> dict:
        score = 0
        if results["chi_square"]["passed"]: score += 30
        elif results["chi_square"].get("statistic", 999) < 350: score += 15
        if results["runs"]["passed"]: score += 25
        elif results["runs"].get("z_score", 99) < 3.0: score += 12
        if results["autocorr"]["passed"]: score += 25
        elif results["autocorr"].get("max_corr", 1) < 0.15: score += 12
        ent = results["entropy"].get("entropy", 0)
        if ent >= 7.9: score += 20
        elif ent >= 7.5: score += 15
        elif ent >= 7.0: score += 10
        level = "优秀" if score >= 90 else "良好" if score >= 75 else "合格" if score >= 60 else "待优化"
        issues = []
        if not results["chi_square"]["passed"]: issues.append("字节分布不均匀")
        if not results["runs"]["passed"]: issues.append("序列存在可预测模式")
        if not results["autocorr"]["passed"]: issues.append("相邻数据相关性过高")
        if ent < 7.5: issues.append("信息熵偏低")
        return {"score": min(100, max(0, score)), "level": level, "issues": issues if issues else ["各项指标符合随机性要求"]}

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("专业串口随机数分析助手")
        self.resize(1100, 800)
        self.is_open = False
        self.worker = None
        self.data_buffer = np.array([], dtype=np.uint8)
        self.max_buffer_size = 50000
        self.rx_format = "HEX"
        self.tx_format = "HEX"
        self.auto_scroll = True
        self.analysis_timer = QTimer()
        self.analysis_timer.setInterval(3000)
        self.analysis_timer.timeout.connect(self.auto_analyze)

        self.init_ui()
        self.setStyleSheet(APP_STYLE)
        self.refresh_ports()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        top_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "921600"])
        self.baud_combo.setCurrentText("115200")
        self.refresh_btn = QPushButton("刷新端口")
        self.open_btn = QPushButton("打开串口")
        top_layout.addWidget(QLabel("端口:"))
        top_layout.addWidget(self.port_combo, 2)
        top_layout.addWidget(QLabel("波特率:"))
        top_layout.addWidget(self.baud_combo, 1)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addWidget(self.open_btn)
        main_layout.addLayout(top_layout)

        fmt_layout = QHBoxLayout()
        for name in ["HEX", "DEC", "ASCII", "BIN"]:
            btn = QRadioButton(name)
            btn.toggled.connect(lambda c, n=name: self.set_rx_fmt(n) if c else None)
            fmt_layout.addWidget(QLabel("接收:") if name=="HEX" else btn)
            if name == "HEX": btn.setChecked(True)
        fmt_layout.addSpacing(15)
        for name in ["HEX", "DEC", "ASCII", "BIN"]:
            btn = QRadioButton(name)
            btn.toggled.connect(lambda c, n=name: self.set_tx_fmt(n) if c else None)
            fmt_layout.addWidget(QLabel("发送:") if name=="HEX" else btn)
            if name == "HEX": btn.setChecked(True)
        
        self.auto_scroll_cb = QCheckBox("日志自动滚动")
        self.auto_scroll_cb.setChecked(True)
        self.auto_analyze_cb = QCheckBox("自动分析")
        self.auto_analyze_cb.setChecked(True)
        self.auto_analyze_cb.stateChanged.connect(lambda: self.analysis_timer.start() if self.auto_analyze_cb.isChecked() else self.analysis_timer.stop())
        
        fmt_layout.addStretch()
        fmt_layout.addWidget(self.auto_scroll_cb)
        fmt_layout.addWidget(self.auto_analyze_cb)
        main_layout.addLayout(fmt_layout)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.chat_box.setFont(QFont("Menlo", 10))
        self.chat_box.setStyleSheet("background-color: #25252d; border-radius: 6px; padding: 8px;")
        
        self.tab_widget = QTabWidget()
        
        self.plot_time = pg.PlotWidget(title="时域波形 - 全部历史数据")
        self._config_plot(self.plot_time, "接收序号", "数值(0-255)", (0, 256), '#00ff88')
        self.curve_time = self.plot_time.plot(pen=pg.mkPen('#00ff88', width=1.5))
        
        self.plot_hist = pg.PlotWidget(title="字节值分布 - 全部历史数据")
        self._config_plot(self.plot_hist, "字节值", "出现频次", None, '#4a90e2')
        self.bar_hist = pg.BarGraphItem(x=list(range(256)), height=[0]*256, width=1, brush=pg.mkBrush('#4a90e280'))
        self.plot_hist.addItem(self.bar_hist)
        
        self.plot_scatter = pg.PlotWidget(title="相邻字节散点 - 全部历史数据")
        self._config_plot(self.plot_scatter, "当前字节Xn", "下一字节Xn+1", (0, 256), '#e94b3c')
        self.scatter_plot = pg.ScatterPlotItem(symbol='o', size=3, brush=pg.mkBrush('#e94b3c80'), pen=None)
        self.plot_scatter.addItem(self.scatter_plot)
        
        self.plot_autocorr = pg.PlotWidget(title="自相关系数 - 全部历史数据")
        self._config_plot(self.plot_autocorr, "延迟阶数", "相关系数", (-1, 1), '#9b59b6')
        self.plot_autocorr.addLine(y=0, pen=pg.mkPen('#666', style=Qt.PenStyle.DashLine))
        self.plot_autocorr.addLine(y=0.1, pen=pg.mkPen('#f39c12', style=Qt.PenStyle.DashLine))
        self.plot_autocorr.addLine(y=-0.1, pen=pg.mkPen('#f39c12', style=Qt.PenStyle.DashLine))
        self.curve_autocorr = self.plot_autocorr.plot(pen=pg.mkPen('#9b59b6', width=2))
        
        self.tab_widget.addTab(self.plot_time, "时域波形")
        self.tab_widget.addTab(self.plot_hist, "分布直方图")
        self.tab_widget.addTab(self.plot_scatter, "相关性散点")
        self.tab_widget.addTab(self.plot_autocorr, "自相关分析")
        
        self.splitter.addWidget(self.chat_box)
        self.splitter.addWidget(self.tab_widget)
        self.splitter.setSizes([250, 550])
        main_layout.addWidget(self.splitter, 1)

        score_group = QGroupBox("随机性质量评估（基于全部历史数据）")
        score_layout = QVBoxLayout()
        self.data_count_label = QLabel("当前历史数据: 0 字节")
        self.data_count_label.setFont(QFont("Menlo", 10))
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_label = QLabel("等待数据...")
        self.score_label.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        self.issues_label = QLabel("")
        self.issues_label.setWordWrap(True)
        
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("分析最近:"))
        self.analyze_range = QSpinBox()
        self.analyze_range.setRange(100, 50000)
        self.analyze_range.setValue(1000)
        self.analyze_range.setSingleStep(100)
        range_layout.addWidget(self.analyze_range)
        range_layout.addWidget(QLabel("字节"))
        range_layout.addStretch()
        
        score_layout.addWidget(self.data_count_label)
        score_layout.addLayout(range_layout)
        score_layout.addWidget(self.score_label)
        score_layout.addWidget(self.score_bar)
        score_layout.addWidget(self.issues_label)
        score_group.setLayout(score_layout)
        main_layout.addWidget(score_group)

        bottom_layout = QHBoxLayout()
        self.send_input = QTextEdit()
        self.send_input.setMaximumHeight(50)
        self.send_input.setFont(QFont("Menlo", 10))
        self.send_input.setPlaceholderText("输入发送数据...")
        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet("background-color: #2d6a4f; min-width: 80px;")
        self.save_btn = QPushButton("保存历史数据")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.clicked.connect(self.save_data)
        self.analyze_btn = QPushButton("立即分析")
        self.analyze_btn.clicked.connect(self.manual_analyze)
        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.clicked.connect(self.clear_all)
        
        bottom_layout.addWidget(self.send_input, 3)
        bottom_layout.addWidget(self.send_btn)
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(self.analyze_btn)
        bottom_layout.addWidget(self.clear_btn)
        main_layout.addLayout(bottom_layout)

        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.open_btn.clicked.connect(self.toggle_serial)
        self.send_btn.clicked.connect(self.send_data)
        self.auto_scroll_cb.stateChanged.connect(lambda: setattr(self, 'auto_scroll', self.auto_scroll_cb.isChecked()))

    def _config_plot(self, plot, xlabel, ylabel, yrange, color):
        plot.setBackground("#25252d")
        plot.getAxis("left").setPen("#888")
        plot.getAxis("bottom").setPen("#888")
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.setLabel("left", ylabel)
        plot.setLabel("bottom", xlabel)
        if yrange: plot.setYRange(*yrange)

    def set_rx_fmt(self, fmt): self.rx_format = fmt
    def set_tx_fmt(self, fmt): self.tx_format = fmt

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(f"{p.device} ({p.description})")
        if not ports: self.port_combo.addItem("未检测到串口")

    def toggle_serial(self):
        if not self.is_open: self.open_serial()
        else: self.close_serial()

    def open_serial(self):
        port_text = self.port_combo.currentText()
        if "未检测到" in port_text:
            QMessageBox.warning(self, "提示", "请选择有效串口")
            return
        port_name = port_text.split(" ")[0]
        baudrate = int(self.baud_combo.currentText())
        self.worker = SerialWorker(port_name, baudrate)
        self.worker.data_received.connect(self.handle_data)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.port_closed.connect(self.on_port_closed)
        self.worker.start()
        self.is_open = True
        self.open_btn.setText("关闭串口")
        self.open_btn.setStyleSheet("background-color: #b54444;")
        self.add_system_msg(f"已连接 {port_name} @ {baudrate}")
        if self.auto_analyze_cb.isChecked(): self.analysis_timer.start()

    def close_serial(self):
        if self.worker: self.worker.stop()
        self.is_open = False
        self.open_btn.setText("打开串口")
        self.open_btn.setStyleSheet("")
        self.analysis_timer.stop()
        self.add_system_msg("串口已断开")

    def on_port_closed(self):
        self.is_open = False
        self.open_btn.setText("打开串口")
        self.open_btn.setStyleSheet("")

    def handle_data(self, data_bytes: bytes):
        """处理接收到的串口数据"""
        try:
            formatted = self.format_display(data_bytes, self.rx_format)
            self.add_chat_message("RX", formatted)
            new_data = np.frombuffer(data_bytes, dtype=np.uint8)
            self.data_buffer = np.concatenate([self.data_buffer, new_data])
            if len(self.data_buffer) > self.max_buffer_size:
                self.data_buffer = self.data_buffer[-self.max_buffer_size:]
            
            # 实时更新时域图
            self.curve_time.setData(self.data_buffer)
            self.plot_time.setXRange(0, len(self.data_buffer))
            
            # 每200字节或数据量变化时更新其他图表
            if len(self.data_buffer) % 200 < len(new_data):
                self.update_all_plots()
            self.data_count_label.setText(f"当前历史数据: {len(self.data_buffer):,} 字节")
        except Exception as e:
            self.add_system_msg(f"接收处理错误: {e}")
            print(f"[接收异常] {e}")

    def send_data(self):
        text = self.send_input.toPlainText().strip()
        if not text: return
        try:
            if self.tx_format == "ASCII": data = text.encode('utf-8')
            elif self.tx_format == "HEX":
                clean = text.replace(" ", "").replace("0x", "").replace(",", "")
                if len(clean) % 2 != 0: raise ValueError("HEX长度需为偶数")
                data = bytes.fromhex(clean)
            elif self.tx_format == "DEC":
                nums = [int(x) for x in text.replace(",", " ").split() if x.strip()]
                if any(n < 0 or n > 255 for n in nums): raise ValueError("DEC需0~255")
                data = bytes(nums)
            elif self.tx_format == "BIN":
                clean = text.replace(" ", "")
                if len(clean) % 8 != 0: raise ValueError("BIN长度需为8的倍数")
                data = bytes([int(clean[i:i+8], 2) for i in range(0, len(clean), 8)])
            if self.worker and self.worker.serial_port and self.worker.serial_port.is_open:
                self.worker.serial_port.write(data)
                self.add_chat_message("TX", self.format_display(data, self.tx_format))
                self.send_input.clear()
            else: QMessageBox.warning(self, "警告", "串口未打开")
        except Exception as e: QMessageBox.critical(self, "发送失败", str(e))

    def format_display(self, data: bytes, fmt: str) -> str:
        if fmt == "ASCII":
            try: return data.decode('utf-8', errors='replace')
            except: return "<解码错误>"
        elif fmt == "HEX": return data.hex(' ').upper()
        elif fmt == "DEC": return ' '.join(str(b) for b in data)
        elif fmt == "BIN": return ' '.join(f"{b:08b}" for b in data)
        return ""

    def add_chat_message(self, role: str, content: str):
        time_str = datetime.now().strftime("%H:%M:%S")
        bg = "#2d3436" if role == "RX" else "#1e3a5f"
        align = "left" if role == "RX" else "right"
        tag = "接收" if role == "RX" else "发送"
        html = f"""<div style='text-align:{align};margin:4px 0;'>
            <span style='font-size:10px;color:#7f8c8d;'>[{time_str}]</span>
            <div style='display:inline-block;background:{bg};color:#ecf0f1;
                padding:6px 10px;border-radius:8px;max-width:85%;
                word-wrap:break-word;font-family:Menlo,monospace;font-size:11px;'>
                <b style='color:#3498db;'>{tag}</b><br>{content}
            </div></div>"""
        self.chat_box.append(html)
        if self.auto_scroll:
            self.chat_box.verticalScrollBar().setValue(self.chat_box.verticalScrollBar().maximum())

    def add_system_msg(self, msg: str):
        time_str = datetime.now().strftime("%H:%M:%S")
        html = f"<div style='text-align:center;margin:6px 0;'><span style='color:#f39c12;font-size:11px;background:#333;padding:2px 8px;border-radius:4px;'>[{time_str}] {msg}</span></div>"
        self.chat_box.append(html)

    def update_all_plots(self):
        """优化：使用向量化计算提高性能，减少内存分配"""
        if len(self.data_buffer) < 10: 
            return
        
        # 直方图更新
        hist, _ = np.histogram(self.data_buffer, bins=256, range=(0, 256))
        self.bar_hist.setOpts(height=hist)
        
        # 相邻字节散点图更新（限制显示数量）
        if len(self.data_buffer) >= 2:
            display_limit = 8000
            x = self.data_buffer[:-1][-display_limit:]
            y = self.data_buffer[1:][-display_limit:]
            self.scatter_plot.setData(x, y)
        else:
            self.scatter_plot.setData([], [])
        
        # 自相关分析优化（向量化计算）
        data_norm = (self.data_buffer - np.mean(self.data_buffer)) / (np.std(self.data_buffer) + 1e-10)
        max_lag = min(50, len(data_norm)//10)
        
        # 使用 Numpy 向量化计算自相关系数
        if len(data_norm) > max_lag:
            lags = np.arange(max_lag + 1)
            corr = np.array([np.mean(data_norm[:len(data_norm)-lag] * data_norm[lag:]) for lag in lags])
            self.curve_autocorr.setData(corr)
        else:
            self.curve_autocorr.setData([])

    def save_data(self):
        if len(self.data_buffer) == 0:
            QMessageBox.information(self, "提示", "暂无历史数据可保存")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "保存历史随机数数据", 
                                                   f"random_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                                   "文本文件 (*.txt);;所有文件 (*)")
        if not file_path: return
        try:
            fmt = self.rx_format
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# 历史随机数数据导出 | 时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 格式:{fmt}\n")
                f.write(f"# 总字节数:{len(self.data_buffer)}\n\n")
                for i in range(0, len(self.data_buffer), 16):
                    chunk = self.data_buffer[i:i+16]
                    if fmt == "HEX": line = " ".join(f"{b:02X}" for b in chunk)
                    elif fmt == "DEC": line = " ".join(f"{b:3d}" for b in chunk)
                    elif fmt == "BIN": line = " ".join(f"{b:08b}" for b in chunk)
                    elif fmt == "ASCII": line = "".join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                    f.write(f"{i:06d} | {line}\n")
            self.add_system_msg(f"已保存 {len(self.data_buffer):,} 字节历史数据")
        except Exception as e: QMessageBox.critical(self, "保存失败", str(e))

    def manual_analyze(self): self.run_analysis()
    
    def auto_analyze(self):
        if self.auto_analyze_cb.isChecked() and len(self.data_buffer) >= 100:
            self.run_analysis()

    def run_analysis(self):
        total = len(self.data_buffer)
        if total < 100:
            self.score_label.setText("数据量不足 (需>=100字节)")
            return
        range_size = min(self.analyze_range.value(), total)
        analysis_data = self.data_buffer[-range_size:]
        results = {
            "chi_square": RandomnessAnalyzer.chi_square_test(analysis_data),
            "runs": RandomnessAnalyzer.runs_test(analysis_data),
            "autocorr": RandomnessAnalyzer.autocorrelation_test(analysis_data),
            "entropy": RandomnessAnalyzer.entropy_test(analysis_data)
        }
        summary = RandomnessAnalyzer.comprehensive_score(results)
        self.score_bar.setValue(summary["score"])
        color = "#00ff88" if summary["score"] >= 75 else "#f39c12" if summary["score"] >= 60 else "#e74c3c"
        self.score_bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
        self.score_label.setText(f"评分: {summary['score']}/100 [{summary['level']}] (基于最近{range_size:,}字节)")
        self.issues_label.setText("\n".join(f"• {i}" for i in summary["issues"]))
        log_lines = [results[k]["msg"] for k in ["chi_square", "runs", "autocorr", "entropy"]]
        self.add_system_msg(f"分析{range_size:,}字节: {' | '.join(log_lines)}")

    def clear_all(self):
        reply = QMessageBox.question(self, "确认清空", "确定要清空所有历史数据与图表吗？", 
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        self.data_buffer = np.array([], dtype=np.uint8)
        self.chat_box.clear()
        self.curve_time.setData([])
        self.bar_hist.setOpts(height=[0]*256)
        self.scatter_plot.setData([], [])
        self.curve_autocorr.setData([])
        self.score_bar.setValue(0)
        self.score_label.setText("等待数据...")
        self.issues_label.setText("")
        self.data_count_label.setText("当前历史数据: 0 字节")
        self.add_system_msg("已清空全部历史数据")

    def handle_error(self, msg): QMessageBox.critical(self, "串口异常", msg); self.close_serial()
    
    def closeEvent(self, event):
        if self.is_open: self.close_serial()
        self.analysis_timer.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pg.setConfigOptions(antialias=True, background='#25252d')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())