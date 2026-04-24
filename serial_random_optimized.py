#!/usr/bin/env python3
"""
专业串口随机数分析助手 - 优化版
修复了原始代码中的 bug 并增加了性能和用户体验优化
"""

import sys
import serial
import serial.tools.list_ports
import numpy as np
from datetime import datetime
from collections import deque
from typing import Optional, Dict, List, Tuple
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QMessageBox,
    QGroupBox, QSplitter, QCheckBox, QRadioButton, QTabWidget,
    QFileDialog, QProgressBar, QSpinBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QTextOption
import pyqtgraph as pg

# ==================== 应用样式 ====================
APP_STYLE = """
QMainWindow, QWidget { 
    background-color: #1a1a20; 
    color: #e0e0e0; 
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
}
QGroupBox { 
    font-weight: bold; 
    font-size: 13px;
    border: 1px solid #2d2d35; 
    border-radius: 8px; 
    margin-top: 10px; 
    padding-top: 14px; 
}
QGroupBox::title { 
    subcontrol-origin: margin; 
    left: 12px; 
    padding: 0 6px; 
    color: #88a0c8; 
    font-size: 12px;
}
QComboBox, QTextEdit, QLineEdit, QSpinBox { 
    background-color: #25252d; 
    border: 1px solid #353540; 
    border-radius: 6px; 
    padding: 8px 12px; 
    color: #e8e8f0; 
    font-size: 13px;
    selection-background-color: #3a506b;
    selection-color: white;
}
QComboBox::drop-down {
    border: none;
    background: transparent;
}
QComboBox QAbstractItemView {
    background-color: #25252d;
    border: 1px solid #353540;
    border-radius: 6px;
    padding: 4px;
    color: #e8e8f0;
    font-size: 13px;
    selection-background-color: #3a506b;
    selection-color: white;
    outline: none;
}
QComboBox QAbstractItemView::item {
    height: 28px;
    padding: 4px 8px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #3a506b;
}
QLabel {
    color: #ccccd8;
    font-size: 13px;
}
QPushButton { 
    background-color: #3a506b; 
    color: white; 
    border: none; 
    border-radius: 6px; 
    padding: 10px 18px; 
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover { 
    background-color: #4a6fa5; 
}
QPushButton:pressed { 
    background-color: #2c3e50; 
}
QPushButton#saveBtn { background-color: #2d6a4f; }
QPushButton#saveBtn:hover { background-color: #3a7a5f; }
QProgressBar { 
    border: 1px solid #353540; 
    border-radius: 8px; 
    background: #25252d; 
    height: 20px;
    text-align: center;
}
QProgressBar::chunk { 
    background: linear-gradient(to right, #00c9a7, #00ff88); 
    border-radius: 8px; 
}
QTextEdit {
    font-family: 'Consolas', 'Monaco', 'Menlo', monospace;
}
QScrollBar:vertical { 
    background: #25252d; 
    width: 10px; 
    border-radius: 4px;
}
QScrollBar::handle:vertical { 
    background: #4a4a5a; 
    border-radius: 4px; 
    min-height: 30px; 
}
QScrollBar::handle:vertical:hover { 
    background: #5a5a6a; 
}
QTabWidget::pane {
    border: 1px solid #2d2d35;
    border-radius: 8px;
    margin-top: -1px;
    background-color: #1e1e24;
}
QTabBar::tab {
    background-color: #25252d;
    color: #a0a0b0;
    padding: 10px 20px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #353540;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #3a506b;
    color: white;
    border-color: #4a6fa5;
}
QRadioButton {
    color: #ccccd8;
    font-size: 13px;
    spacing: 6px;
}
QCheckBox {
    color: #ccccd8;
    font-size: 13px;
    spacing: 6px;
}
"""

# ==================== 循环缓冲区类 ====================
class CircularBuffer:
    """优化的循环缓冲区，避免频繁的内存重分配"""
    
    def __init__(self, max_size: int = 50000):
        self.max_size = max_size
        self.buffer = np.zeros(max_size, dtype=np.uint8)
        self.start_idx = 0
        self.length = 0
    
    def append(self, data: np.ndarray):
        """添加数据到缓冲区"""
        data_len = len(data)
        if data_len == 0:
            return
        
        if data_len >= self.max_size:
            # 数据比缓冲区大，只保留最后的部分
            data = data[-self.max_size:]
            self.buffer[:] = data
            self.start_idx = 0
            self.length = self.max_size
            return
        
        end_idx = self.start_idx + self.length
        # 计算可以追加的空间
        space_available = self.max_size - self.length
        if data_len > space_available:
            # 需要移除老数据腾出空间
            overflow = data_len - space_available
            self.start_idx = (self.start_idx + overflow) % self.max_size
            self.length = self.max_size
        
        # 写入新数据
        for i in range(data_len):
            pos = (end_idx + i) % self.max_size
            self.buffer[pos] = data[i]
        
        self.length = min(self.length + data_len, self.max_size)
    
    def get_data(self) -> np.ndarray:
        """获取顺序的数据数组"""
        if self.length == 0:
            return np.array([], dtype=np.uint8)
        
        end_idx = self.start_idx + self.length
        if end_idx <= self.max_size:
            # 数据没有跨越缓冲区边界
            return self.buffer[self.start_idx:end_idx].copy()
        else:
            # 数据跨越边界，需要拼接
            part1 = self.buffer[self.start_idx:]
            part2 = self.buffer[:end_idx % self.max_size]
            return np.concatenate([part1, part2])
    
    def __len__(self) -> int:
        return self.length
    
    def clear(self):
        """清空缓冲区"""
        self.start_idx = 0
        self.length = 0

# ==================== 串口工作线程 ====================
class SerialWorker(QThread):
    """串口通信工作线程，避免阻塞UI"""
    
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    port_closed = pyqtSignal()
    
    def __init__(self, port_name: str, baudrate: int):
        super().__init__()
        self.port_name = port_name
        self.baudrate = baudrate
        self.running = True
        self.serial_port: Optional[serial.Serial] = None
    
    def run(self):
        """主线程循环"""
        try:
            self.serial_port = serial.Serial(
                self.port_name, 
                self.baudrate, 
                timeout=0.05,
                write_timeout=1.0  # 发送超时
            )
            self.serial_port.flushInput()  # 清空输入缓冲区
            
            while self.running:
                try:
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        if data:
                            self.data_received.emit(data)
                except serial.SerialException as e:
                    if self.running:
                        self.error_occurred.emit(f"串口读取错误: {e}")
                        break
                        
        except Exception as e:
            if self.running:
                self.error_occurred.emit(f"串口连接错误: {e}")
        finally:
            self._safe_close()
    
    def _safe_close(self):
        """安全关闭串口"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
        except Exception:
            pass
    
    def stop(self):
        """停止线程"""
        self.running = False
        self.wait(2000)  # 等待2秒
        
        if self.isRunning():
            self.terminate()
            
        self._safe_close()
        self.port_closed.emit()

# ==================== 随机性分析类 ====================
class RandomnessAnalyzer:
    """随机性统计分析工具类"""
    
    @staticmethod
    def chi_square_test(data: np.ndarray) -> dict:
        """卡方检验 - 检查字节分布均匀性"""
        if len(data) < 256:
            return {"passed": False, "statistic": 0, "msg": "数据量不足256字节"}
        
        observed, _ = np.histogram(data, bins=256, range=(0, 256))
        expected = len(data) / 256
        chi2 = np.sum((observed - expected) ** 2 / expected)
        critical = 310.0  # 自由度255，显著性水平0.05
        passed = chi2 < critical
        
        return {
            "passed": passed,
            "statistic": chi2,
            "msg": f"卡方={chi2:.1f} {'通过' if passed else '不通过'}"
        }
    
    @staticmethod
    def runs_test(data: np.ndarray) -> dict:
        """游程检验 - 检查序列随机性"""
        if len(data) < 20:
            return {"passed": False, "z_score": 0, "msg": "数据量不足20字节"}
        
        median = np.median(data)
        binary = (data > median).astype(int)
        runs = 1 + np.sum(binary[1:] != binary[:-1])
        n1, n2 = np.sum(binary), len(binary) - np.sum(binary)
        
        if n1 == 0 or n2 == 0:
            return {"passed": False, "z_score": 0, "msg": "数据分布极端"}
        
        mu = (2 * n1 * n2) / (n1 + n2) + 1
        sigma = np.sqrt((2 * n1 * n2 * (2 * n1 * n2 - n1 - n2)) / 
                       ((n1 + n2) ** 2 * (n1 + n2 - 1)) + 1e-10)
        
        z = abs(runs - mu) / sigma if sigma > 1e-10 else 0
        passed = z < 2.58  # 99%置信水平
        
        return {
            "passed": passed,
            "z_score": z,
            "msg": f"游程Z={z:.2f} {'通过' if passed else '不通过'}"
        }
    
    @staticmethod
    def autocorrelation_test(data: np.ndarray, max_lag: int = 20) -> dict:
        """自相关检验 - 检查数据相关性"""
        if len(data) < 100:
            return {"passed": True, "max_corr": 0, "msg": "数据量不足，跳过"}
        
        data_norm = (data - np.mean(data)) / (np.std(data) + 1e-10)
        max_lag = min(max_lag, len(data_norm) // 10)
        
        # 向量化计算自相关系数
        lags = np.arange(1, max_lag + 1)
        corr = np.array([np.mean(data_norm[:-lag] * data_norm[lag:]) for lag in lags])
        max_corr = np.max(np.abs(corr)) if len(corr) > 0 else 0
        
        passed = max_corr < 0.1
        
        return {
            "passed": passed,
            "max_corr": max_corr,
            "msg": f"自相关={max_corr:.3f} {'通过' if passed else '不通过'}"
        }
    
    @staticmethod
    def entropy_test(data: np.ndarray) -> dict:
        """信息熵测试 - 测量信息不确定性"""
        if len(data) < 10:
            return {"passed": False, "entropy": 0, "msg": "数据量不足"}
        
        hist, _ = np.histogram(data, bins=256, range=(0, 256))
        probs = hist[hist > 0] / len(data)
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        passed = entropy > 7.5  # 接近理论最大值8
        
        return {
            "passed": passed,
            "entropy": entropy,
            "msg": f"熵值={entropy:.2f}bits {'通过' if passed else '偏低'}"
        }
    
    @staticmethod
    def monobit_test(data: np.ndarray) -> dict:
        """单一比特测试（适用于bit流数据）"""
        if len(data) < 100:
            return {"passed": False, "statistic": 0, "msg": "数据量不足"}
        
        # 将字节转换为比特流
        bits = np.unpackbits(data.astype(np.uint8))
        ones_count = np.sum(bits)
        n = len(bits)
        p = ones_count / n
        
        # 计算统计量
        s = abs(ones_count - n/2) / np.sqrt(n/4)
        
        # 95%置信水平临界值为1.96
        passed = s < 1.96
        
        return {
            "passed": passed,
            "statistic": s,
            "balance": p,
            "msg": f"比特平衡={p:.3f} {'通过' if passed else '不通过'}"
        }
    
    @staticmethod
    def frequency_test(data: np.ndarray) -> dict:
        """频率测试 - 检查0-127与128-255的平衡性"""
        if len(data) < 100:
            return {"passed": False, "statistic": 0, "msg": "数据量不足"}
        
        # 统计小于128和大于等于128的数量
        low_count = np.sum(data < 128)
        high_count = len(data) - low_count
        
        # 计算卡方统计量
        expected = len(data) / 2
        chi2 = ((low_count - expected) ** 2 + (high_count - expected) ** 2) / expected
        passed = chi2 < 3.84  # 95%置信水平，自由度为1
        
        return {
            "passed": passed,
            "statistic": chi2,
            "ratio": low_count / len(data),
            "msg": f"高低比={(low_count/len(data)):.3f} {'通过' if passed else '不通过'}"
        }
    
    @staticmethod  
    def serial_correlation_test(data: np.ndarray) -> dict:
        """串行相关性测试"""
        if len(data) < 100:
            return {"passed": False, "correlation": 0, "msg": "数据量不足"}
        
        # 计算相邻字节的相关系数
        if len(data) > 1:
            x = data[:-1].astype(np.float64)
            y = data[1:].astype(np.float64)
            correlation = np.corrcoef(x, y)[0, 1]
            passed = abs(correlation) < 0.1
        else:
            correlation = 0
            passed = True
            
        return {
            "passed": passed,
            "correlation": correlation,
            "msg": f"相邻相关={correlation:.3f} {'通过' if passed else '不通过'}"
        }
    
    @staticmethod
    def spectral_test(data: np.ndarray) -> dict:
        """频谱测试 - 快速傅里叶变换分析"""
        if len(data) < 128:
            return {"passed": False, "peak_ratio": 0, "msg": "数据量不足128字节"}
        
        # 执行FFT
        fft_data = np.fft.fft(data.astype(np.float64))
        magnitude = np.abs(fft_data[:len(fft_data)//2])  # 只取一半
        
        # 检查是否有明显的峰值
        mean_mag = np.mean(magnitude)
        max_mag = np.max(magnitude)
        peak_ratio = max_mag / mean_mag
        
        # 对于随机数据，峰值不应该太高
        passed = peak_ratio < 10.0
        
        return {
            "passed": passed,
            "peak_ratio": peak_ratio,
            "msg": f"频谱峰值比={peak_ratio:.2f} {'通过' if passed else '可能有周期性'}"
        }
    
    @staticmethod
    def get_statistics(data: np.ndarray) -> Dict[str, float]:
        """计算基本统计信息"""
        if len(data) == 0:
            return {}
        
        return {
            "mean": float(np.mean(data)),
            "std": float(np.std(data)),
            "min": float(np.min(data)),
            "max": float(np.max(data)),
            "range": float(np.max(data) - np.min(data)),
            "median": float(np.median(data)),
            "variance": float(np.var(data)),
            "cv": float(np.std(data) / (np.mean(data) + 1e-10)),  # 变异系数
            "skewness": float(np.mean(((data - np.mean(data)) / (np.std(data) + 1e-10)) ** 3)),  # 偏度
            "kurtosis": float(np.mean(((data - np.mean(data)) / (np.std(data) + 1e-10)) ** 4))   # 峰度
        }
    
    @staticmethod
    def comprehensive_score(results: Dict[str, dict]) -> dict:
        """综合评分算法"""
        score = 0
        
        # 卡方检验评分
        if results["chi_square"]["passed"]:
            score += 20
        elif results["chi_square"].get("statistic", 999) < 350:
            score += 10
        
        # 游程检验评分
        if results["runs"]["passed"]:
            score += 15
        elif results["runs"].get("z_score", 99) < 3.0:
            score += 7
        
        # 自相关检验评分
        if results["autocorr"]["passed"]:
            score += 15
        elif results["autocorr"].get("max_corr", 1) < 0.15:
            score += 7
        
        # 信息熵评分
        entropy = results["entropy"].get("entropy", 0)
        if entropy >= 7.9:
            score += 12
        elif entropy >= 7.5:
            score += 8
        elif entropy >= 7.0:
            score += 5
        
        # 单一比特测试评分
        if results.get("monobit", {}).get("passed", False):
            score += 8
        elif results.get("monobit", {}).get("statistic", 99) < 2.5:
            score += 4
        
        # 频率测试评分
        if results.get("frequency", {}).get("passed", False):
            score += 8
        elif results.get("frequency", {}).get("statistic", 99) < 4.0:
            score += 4
        
        # 串行相关性测试评分
        if results.get("serial_corr", {}).get("passed", False):
            score += 8
        elif abs(results.get("serial_corr", {}).get("correlation", 1)) < 0.15:
            score += 4
        
        # 频谱测试评分
        if results.get("spectral", {}).get("passed", False):
            score += 8
        elif results.get("spectral", {}).get("peak_ratio", 99) < 12.0:
            score += 4
        
        # 确定等级
        if score >= 85:
            level = "优秀"
        elif score >= 70:
            level = "良好"
        elif score >= 50:
            level = "合格"
        else:
            level = "待优化"
        
        # 问题诊断
        issues = []
        if not results["chi_square"]["passed"]:
            issues.append("字节分布不均匀")
        if not results["runs"]["passed"]:
            issues.append("序列存在可预测模式")
        if not results["autocorr"]["passed"]:
            issues.append("相邻数据相关性过高")
        if entropy < 7.5:
            issues.append("信息熵偏低")
        if not results.get("monobit", {}).get("passed", False):
            issues.append("比特平衡性不足")
        if not results.get("frequency", {}).get("passed", False):
            issues.append("高低字节分布不均")
        if not results.get("serial_corr", {}).get("passed", False):
            issues.append("串行相关性过高")
        if not results.get("spectral", {}).get("passed", False):
            issues.append("频谱可能存在周期性")
        
        if not issues:
            issues.append("各项指标符合随机性要求")
        
        return {
            "score": min(100, max(0, score)),
            "level": level,
            "issues": issues
        }

# ==================== 主窗口类 ====================
class MainWindow(QMainWindow):
    """主应用程序窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔬 专业串口随机数分析助手 v2.0")
        self.resize(1350, 900)
        self.setMinimumSize(1000, 700)
        
        # 初始化成员变量
        self.is_open = False
        self.worker: Optional[SerialWorker] = None
        self.data_buffer = CircularBuffer(max_size=100000)  # 使用优化的循环缓冲区
        self.rx_format = "HEX"
        self.tx_format = "HEX"
        self.auto_scroll = True
        self.last_update_time = datetime.now()
        self._last_stats_count = 0
        self._last_stats_time = datetime.now()
        
        # 初始化界面
        self.init_ui()
        self.setStyleSheet(APP_STYLE)
        self.refresh_ports()
        
        # 定时器
        self.analysis_timer = QTimer()
        self.analysis_timer.setInterval(3000)  # 3秒自动分析
        self.analysis_timer.timeout.connect(self.auto_analyze)
        
        # 图表更新定时器（避免过于频繁）
        self.plot_update_timer = QTimer()
        self.plot_update_timer.setInterval(500)  # 500ms更新一次
        self.plot_update_timer.timeout.connect(self.deferred_plot_update)
        self.plot_update_pending = False
    
    def setup_plot(self, plot_widget, xlabel, ylabel, yrange):
        """统一设置图表样式"""
        plot_widget.setBackground("#25252d")
        plot_widget.getAxis("left").setPen("#888")
        plot_widget.getAxis("bottom").setPen("#888")
        plot_widget.showGrid(x=True, y=True, alpha=0.2)
        plot_widget.setLabel("left", ylabel)
        plot_widget.setLabel("bottom", xlabel)
        if yrange:
            plot_widget.setYRange(*yrange)
        
    def init_ui(self):
        """初始化用户界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # ========== 顶部：分页导航 ==========
        self.create_navigation_ui(main_layout)
        
        # ========== 中部：页面堆栈 ==========
        self.create_pages_ui(main_layout)
        
        # ========== 底部：状态栏 ==========
        self.create_status_bar()
        
    def create_navigation_ui(self, parent_layout):
        """创建分页导航UI"""
        nav_group = QGroupBox("功能导航")
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(8, 8, 8, 8)
        
        # 创建导航按钮
        self.nav_buttons = []
        pages = [
            ("串口设置", self.show_serial_page),
            ("通信日志", self.show_log_page),
            ("时域分析", self.show_time_page),
            ("频域分析", self.show_plots_page),
            ("实时统计", self.show_stats_page),
            ("随机性分析", self.show_analysis_page)
        ]
        
        for name, callback in pages:
            btn = QPushButton(f"📡 {name}")
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #25252d;
                    color: #a0a0b0;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 6px;
                    margin-right: 6px;
                    border: 1px solid #353540;
                }
                QPushButton:hover {
                    background-color: #3a506b;
                    color: white;
                }
                QPushButton:checked {
                    background-color: #3a506b;
                    color: white;
                    border: 2px solid #4a6fa5;
                }
            """)
            btn.clicked.connect(callback)
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        nav_group.setLayout(nav_layout)
        parent_layout.addWidget(nav_group)
        
        # 默认选中第一个按钮
        if self.nav_buttons:
            self.nav_buttons[0].setChecked(True)
    
    def create_pages_ui(self, parent_layout):
        """创建页面堆栈UI"""
        # 创建页面堆栈
        self.pages_stack = QTabWidget()
        self.pages_stack.setTabPosition(QTabWidget.TabPosition.North)
        self.pages_stack.setDocumentMode(True)
        self.pages_stack.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #2d2d35;
                border-radius: 8px;
                margin-top: -1px;
                background-color: #1e1e24;
            }
            QTabBar {
                height: 0px;
                qproperty-drawBase: 0;
            }
            QTabBar::tab {
                width: 0px;
                height: 0px;
                margin: 0px;
                padding: 0px;
                border: none;
            }
        """)
        
        # 创建各个页面
        self.create_serial_page()
        self.create_log_page()
        self.create_time_page()
        self.create_plots_page()
        self.create_stats_page()
        self.create_analysis_page()
        
        parent_layout.addWidget(self.pages_stack, 1)
        
        # 默认显示第一个页面
        self.pages_stack.setCurrentIndex(0)
    
    def create_status_bar(self):
        """创建状态栏"""
        status_bar = self.statusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #25252d;
                color: #a0a0b0;
                border-top: 1px solid #353540;
                padding: 4px;
                font-size: 11px;
            }
        """)
        
        # 数据量状态
        self.status_data_count = QLabel("数据量: 0 字节")
        status_bar.addPermanentWidget(self.status_data_count)
        
        # 连接状态
        self.status_connection = QLabel("🔴 未连接")
        status_bar.addPermanentWidget(self.status_connection)
        
        # 实时速率
        self.status_data_rate = QLabel("⚡ 速率: 0 B/s")
        status_bar.addPermanentWidget(self.status_data_rate)
        
    def create_serial_page(self):
        """创建串口设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 使用现有方法创建串口控制UI
        self.create_serial_control_ui(layout)
        
        # 添加底部操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()
        
        self.exit_btn = QPushButton("🚪 退出")
        self.exit_btn.setToolTip("退出应用程序")
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d0493b;
            }
        """)
        self.exit_btn.clicked.connect(self.safe_exit)
        btn_layout.addWidget(self.exit_btn)
        
        layout.addLayout(btn_layout)
        
        self.pages_stack.addTab(page, "")  # 空标签，因为导航栏已经显示
        
    def create_log_page(self):
        """创建通信日志页面（包含聊天日志和发送窗口）"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # 聊天日志
        chat_group = QGroupBox("串口通信日志")
        chat_layout = QVBoxLayout()
        chat_layout.setContentsMargins(6, 6, 6, 6)
        
        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.chat_box.setFont(QFont("Menlo", 9))
        self.chat_box.setStyleSheet("""
            background-color: #25252d; 
            border-radius: 4px; 
            padding: 6px;
            font-family: 'Menlo', 'Consolas', monospace;
        """)
        chat_layout.addWidget(self.chat_box)
        chat_group.setLayout(chat_layout)
        
        layout.addWidget(chat_group, 1)
        
        # 发送区域
        send_group = QGroupBox("发送数据")
        send_group.setMaximumHeight(120)
        send_layout = QVBoxLayout()
        send_layout.setSpacing(6)
        
        # 发送格式选择
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("发送格式:"))
        self.tx_format_group = QHBoxLayout()
        for name in ["HEX", "DEC", "ASCII", "BIN"]:
            btn = QRadioButton(name)
            btn.setToolTip(f"以{name}格式发送数据")
            btn.toggled.connect(lambda checked, n=name: self.set_tx_fmt(n) if checked else None)
            self.tx_format_group.addWidget(btn)
            if name == "HEX":
                btn.setChecked(True)
        fmt_layout.addLayout(self.tx_format_group)
        fmt_layout.addStretch()
        
        send_layout.addLayout(fmt_layout)
        
        # 发送输入框和按钮
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        
        self.send_input = QTextEdit()
        self.send_input.setMaximumHeight(60)
        self.send_input.setFont(QFont("Menlo", 10))
        self.send_input.setPlaceholderText("📝 输入要发送的数据 (支持HEX、DEC、ASCII、BIN格式)")
        
        self.send_btn = QPushButton("📤 发送")
        self.send_btn.setToolTip("发送数据到串口")
        self.send_btn.setMinimumHeight(60)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d6a4f;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #3a7a5f;
            }
            QPushButton:disabled {
                background-color: #3a3a40;
                color: #6a6a70;
            }
        """)
        self.send_btn.clicked.connect(self.send_data)
        
        input_layout.addWidget(self.send_input, 1)
        input_layout.addWidget(self.send_btn)
        
        send_layout.addLayout(input_layout)
        send_group.setLayout(send_layout)
        layout.addWidget(send_group)
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        
        self.save_btn = QPushButton("💾 保存数据")
        self.save_btn.setToolTip("保存接收到的数据到文件")
        self.save_btn.clicked.connect(self.save_data)
        
        self.clear_btn = QPushButton("🗑️ 清空日志")
        self.clear_btn.setToolTip("清空通信日志")
        self.clear_btn.clicked.connect(self.clear_chat_log)
        
        # 选项
        self.auto_scroll_cb = QCheckBox("📜 自动滚动")
        self.auto_scroll_cb.setToolTip("自动滚动到日志最新内容")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.stateChanged.connect(
            lambda: setattr(self, 'auto_scroll', self.auto_scroll_cb.isChecked())
        )
        
        # 接收格式选择
        recv_fmt_layout = QHBoxLayout()
        recv_fmt_layout.addWidget(QLabel("接收格式:"))
        self.rx_format_group = QHBoxLayout()
        for name in ["HEX", "DEC", "ASCII", "BIN"]:
            btn = QRadioButton(name)
            btn.setToolTip(f"以{name}格式显示接收数据")
            btn.toggled.connect(lambda checked, n=name: self.set_rx_fmt(n) if checked else None)
            self.rx_format_group.addWidget(btn)
            if name == "HEX":
                btn.setChecked(True)
        recv_fmt_layout.addLayout(self.rx_format_group)
        
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(self.clear_btn)
        bottom_layout.addWidget(self.auto_scroll_cb)
        bottom_layout.addLayout(recv_fmt_layout)
        bottom_layout.addStretch()
        
        layout.addLayout(bottom_layout)
        
        self.pages_stack.addTab(page, "")  # 空标签，因为导航栏已经显示
        
    def create_serial_control_ui(self, parent_layout):
        """创建串口控制UI"""
        # 串口控制组框
        serial_group = QGroupBox("串口设置")
        serial_group.setStyleSheet("""
            QGroupBox {
                margin-top: 4px;
                padding-top: 12px;
            }
        """)
        serial_layout = QVBoxLayout()
        
        # 第一行：端口和波特率选择
        port_row = QHBoxLayout()
        
        port_row.addWidget(QLabel("端口:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(250)
        port_row.addWidget(self.port_combo, 2)
        
        port_row.addSpacing(10)
        port_row.addWidget(QLabel("波特率:"))
        self.baud_combo = QComboBox()
        self.baud_combo.setMinimumWidth(120)
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", 
                                "115200", "230400", "460800", "921600"])
        self.baud_combo.setCurrentText("115200")
        port_row.addWidget(self.baud_combo, 1)
        
        port_row.addSpacing(20)
        self.refresh_btn = QPushButton("🔁 刷新端口")
        self.refresh_btn.setToolTip("刷新可用串口列表")
        port_row.addWidget(self.refresh_btn)
        
        self.open_btn = QPushButton("🔓 打开串口")
        self.open_btn.setToolTip("打开/关闭串口连接")
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a506b;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #4a6fa5;
            }
        """)
        port_row.addWidget(self.open_btn)
        
        # 状态标签改进
        self.status_label = QLabel("🔴 未连接")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #2d3436;
                color: #e74c3c;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 6px;
                border: 1px solid #444;
                min-width: 120px;
                text-align: center;
            }
        """)
        port_row.addWidget(self.status_label)
        
        port_row.addStretch()
        serial_layout.addLayout(port_row)
        
        # 第二行：格式设置和选项
        fmt_row = QHBoxLayout()
        
        # 接收格式
        fmt_row.addWidget(QLabel("接收格式:"))
        self.rx_format_group = QHBoxLayout()
        for name in ["HEX", "DEC", "ASCII", "BIN"]:
            btn = QRadioButton(name)
            btn.setToolTip(f"以{name}格式显示接收数据")
            btn.toggled.connect(lambda checked, n=name: self.set_rx_fmt(n) if checked else None)
            self.rx_format_group.addWidget(btn)
            if name == "HEX":
                btn.setChecked(True)
        
        fmt_row.addLayout(self.rx_format_group)
        fmt_row.addSpacing(30)
        
        # 发送格式
        fmt_row.addWidget(QLabel("发送格式:"))
        self.tx_format_group = QHBoxLayout()
        for name in ["HEX", "DEC", "ASCII", "BIN"]:
            btn = QRadioButton(name)
            btn.setToolTip(f"以{name}格式发送数据")
            btn.toggled.connect(lambda checked, n=name: self.set_tx_fmt(n) if checked else None)
            self.tx_format_group.addWidget(btn)
            if name == "HEX":
                btn.setChecked(True)
        
        fmt_row.addLayout(self.tx_format_group)
        fmt_row.addSpacing(30)
        
        # 选项
        self.auto_scroll_cb = QCheckBox("📜 自动滚动")
        self.auto_scroll_cb.setToolTip("自动滚动到日志最新内容")
        self.auto_scroll_cb.setChecked(True)
        
        self.auto_analyze_cb = QCheckBox("📊 自动分析")
        self.auto_analyze_cb.setToolTip("自动执行随机性分析")
        self.auto_analyze_cb.setChecked(True)
        self.auto_analyze_cb.stateChanged.connect(self.on_auto_analyze_changed)
        
        fmt_row.addWidget(self.auto_scroll_cb)
        fmt_row.addWidget(self.auto_analyze_cb)
        fmt_row.addStretch()
        
        serial_layout.addLayout(fmt_row)
        serial_group.setLayout(serial_layout)
        parent_layout.addWidget(serial_group)
        
        # 连接信号
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.open_btn.clicked.connect(self.toggle_serial)
        self.auto_scroll_cb.stateChanged.connect(
            lambda: setattr(self, 'auto_scroll', self.auto_scroll_cb.isChecked())
        )
    
    
        
    
    
    # ========== 核心功能方法 ==========
    
    def set_rx_fmt(self, fmt):
        self.rx_format = fmt
    
    def set_tx_fmt(self, fmt):
        self.tx_format = fmt
    
    def on_auto_analyze_changed(self):
        """自动分析复选框状态改变"""
        if self.auto_analyze_cb.isChecked():
            self.analysis_timer.start()
        else:
            self.analysis_timer.stop()
    
    def refresh_ports(self):
        """刷新可用串口列表"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            self.port_combo.addItem("未检测到串口")
            return
        
        for port in sorted(ports, key=lambda x: x.device):
            desc = port.description
            if not desc:
                desc = "未知设备"
            self.port_combo.addItem(f"{port.device} - {desc}")
    
    def toggle_serial(self):
        """打开/关闭串口"""
        if not self.is_open:
            self.open_serial()
        else:
            self.close_serial()
    
    def open_serial(self):
        """打开串口"""
        port_text = self.port_combo.currentText()
        if "未检测到" in port_text:
            QMessageBox.warning(self, "警告", "请选择有效的串口")
            return
        
        # 解析端口名
        parts = port_text.split(" - ")
        port_name = parts[0] if parts else port_text
        
        try:
            baudrate = int(self.baud_combo.currentText())
        except ValueError:
            QMessageBox.warning(self, "警告", "无效的波特率")
            return
        
        # 创建工作线程
        self.worker = SerialWorker(port_name, baudrate)
        self.worker.data_received.connect(self.handle_data)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.port_closed.connect(self.on_port_closed)
        
        try:
            self.worker.start()
            self.is_open = True
            self.open_btn.setText("🔒 关闭串口")
            self.open_btn.setStyleSheet("""
                QPushButton {
                    background-color: #b54444;
                    font-weight: bold;
                    padding: 8px 20px;
                }
                QPushButton:hover {
                    background-color: #c05454;
                }
            """)
            self.status_label.setText(f"🟢 已连接 {port_name}@{baudrate}")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #1e3a2d;
                    color: #00ff88;
                    font-weight: bold;
                    padding: 6px 16px;
                    border-radius: 6px;
                    border: 1px solid #2d6a4f;
                    min-width: 120px;
                    text-align: center;
                }
            """)
            # 更新状态栏的连接状态
            self.status_connection.setText(f"🟢 已连接 {port_name}@{baudrate}")
            
            # 启动相关定时器
            if self.auto_analyze_cb.isChecked():
                self.analysis_timer.start()
            self.stats_timer.start()
            self.plot_update_timer.start()
            
            self.add_system_msg(f"✅ 成功连接到 {port_name} @ {baudrate}bps")
            
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"无法打开串口: {e}")
    
    def close_serial(self):
        """关闭串口"""
        if self.worker:
            self.worker.stop()
        
        self.is_open = False
        self.open_btn.setText("🔓 打开串口")
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a506b;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #4a6fa5;
            }
        """)
        self.status_label.setText("🔴 未连接")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #2d3436;
                color: #e74c3c;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 6px;
                border: 1px solid #444;
                min-width: 120px;
                text-align: center;
            }
        """)
        # 更新状态栏的连接状态
        self.status_connection.setText("🔴 未连接")
        
        # 停止定时器
        self.analysis_timer.stop()
        self.stats_timer.stop()
        self.plot_update_timer.stop()
        
        self.add_system_msg("串口已关闭")
    
    def on_port_closed(self):
        """串口关闭回调"""
        self.is_open = False
        self.open_btn.setText("🔓 打开串口")
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a506b;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #4a6fa5;
            }
        """)
        self.status_label.setText("⚠️ 连接异常")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #3a2a2a;
                color: #f39c12;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 6px;
                border: 1px solid #5a3a3a;
                min-width: 120px;
                text-align: center;
            }
        """)
        # 更新状态栏的连接状态
        self.status_connection.setText("⚠️ 连接异常")
    
    def handle_data(self, data_bytes: bytes):
        """处理接收到的数据"""
        try:
            # 显示数据
            formatted = self.format_display(data_bytes, self.rx_format)
            if formatted.strip():  # 避免显示空白数据
                self.add_chat_message("RX", formatted)
            
            # 更新缓冲区
            new_data = np.frombuffer(data_bytes, dtype=np.uint8)
            self.data_buffer.append(new_data)
            
            # 触发图表更新（延迟执行）
            self.plot_update_pending = True
            
            # 更新统计信息（快速更新）
            self.update_data_count()
            
        except Exception as e:
            self.add_system_msg(f"数据处理错误: {e}")
    
    def deferred_plot_update(self):
        """延迟的图表更新（避免过于频繁）"""
        if self.plot_update_pending:
            try:
                self.update_all_plots()
            except Exception as e:
                # 防止图表更新错误导致程序崩溃
                self.add_system_msg(f"图表更新错误: {str(e)[:50]}...")
            self.plot_update_pending = False
    
    def update_realtime_stats(self):
        """更新实时统计信息"""
        if len(self.data_buffer) == 0:
            return
        
        data = self.data_buffer.get_data()
        
        # 计算基本统计信息
        if len(data) > 0:
            stats = RandomnessAnalyzer.get_statistics(data)
            
            # 更新所有统计标签
            self.data_mean_label.setText(f"📊 平均值: {stats['mean']:.1f}")
            self.data_std_label.setText(f"σ 标准差: {stats['std']:.1f}")
            self.data_range_label.setText(f"↔ 范围: {int(stats['min'])}-{int(stats['max'])}")
            self.data_min_label.setText(f"📉 最小值: {int(stats['min'])}")
            self.data_max_label.setText(f"📈 最大值: {int(stats['max'])}")
            
            # 更新新增的统计标签
            if self.data_median_label:
                self.data_median_label.setText(f"📊 中位数: {stats['median']:.1f}")
            if self.data_variance_label:
                self.data_variance_label.setText(f"📊 方差: {stats['variance']:.1f}")
            if self.data_cv_label:
                self.data_cv_label.setText(f"📊 变异系数: {stats['cv']:.3f}")
            if self.data_skewness_label:
                self.data_skewness_label.setText(f"📊 偏度: {stats['skewness']:.3f}")
            if self.data_kurtosis_label:
                self.data_kurtosis_label.setText(f"📊 峰度: {stats['kurtosis']:.3f}")
        
        # 更新状态栏的数据量显示
        count = len(self.data_buffer)
        self.status_data_count.setText(f"数据量: {count:,} 字节")
        
        # 计算数据接收速率（简化版本）
        # 在实际应用中，可以记录时间和数据量来计算实际速率
        # 这里为简化，显示最近1秒的变化
        current_time = datetime.now()
        
        # 计算简单的增量（这里假设每秒调用一次）
        if hasattr(self, '_last_stats_count') and hasattr(self, '_last_stats_time'):
            time_diff = (current_time - self._last_stats_time).total_seconds()
            if time_diff > 0.1:  # 避免除零
                data_diff = count - self._last_stats_count
                rate = data_diff / time_diff
                self.data_rate_label.setText(f"⚡ 速率: {rate:.0f} B/s")
                # 更新状态栏的速率显示
                self.status_data_rate.setText(f"⚡ 速率: {rate:.0f} B/s")
        
        self._last_stats_count = count
        self._last_stats_time = current_time
    
    def update_data_count(self):
        """更新数据量显示"""
        count = len(self.data_buffer)
        self.data_count_label.setText(f"📊 数据量: {count:,} 字节")
    
    def update_all_plots(self):
        """更新所有图表（已优化）"""
        if len(self.data_buffer) < 2:
            return
        
        data = self.data_buffer.get_data()
        if len(data) < 10:
            return
        
        # 1. 更新时域图
        self.curve_time.setData(data)
        self.plot_time.setXRange(0, len(data))
        
        # 2. 更新直方图
        hist, _ = np.histogram(data, bins=256, range=(0, 256))
        self.bar_hist.setOpts(height=hist)
        
        # 3. 更新散点图（限制点数）
        if len(data) >= 2:
            display_limit = min(5000, len(data)-1)
            x = data[:-1][-display_limit:]
            y = data[1:][-display_limit:]
            self.scatter_plot.setData(x, y)
        
        # 4. 更新自相关图
        self.curve_autocorr.setData([])  # 先清空
        if len(data) > 100:  # 需要更多数据
            try:
                data_norm = (data - np.mean(data)) / (np.std(data) + 1e-10)
                max_lag = min(50, len(data_norm) // 10)
                
                if max_lag >= 10:  # 确保有足够的延迟阶数
                    lags = np.arange(1, max_lag + 1)  # 从1开始，避免lag=0的问题
                    # 向量化计算
                    corr = np.array([np.mean(data_norm[:-lag] * data_norm[lag:]) for lag in lags])
                    self.curve_autocorr.setData(corr, 
                                                pen=pg.mkPen('#9b59b6', width=2),
                                                symbol='o', symbolSize=5, symbolBrush='#9b59b6')
                    # 设置x范围
                    self.plot_autocorr.setXRange(1, max_lag)
            except Exception as e:
                pass  # 忽略自相关计算错误
    
    def send_data(self):
        """发送数据"""
        text = self.send_input.toPlainText().strip()
        if not text:
            return
        
        try:
            data = self.convert_to_bytes(text, self.tx_format)
            
            if self.worker and self.worker.serial_port and self.worker.serial_port.is_open:
                self.worker.serial_port.write(data)
                self.add_chat_message("TX", self.format_display(data, self.tx_format))
                self.send_input.clear()
            else:
                QMessageBox.warning(self, "警告", "串口未打开")
                
        except ValueError as e:
            QMessageBox.critical(self, "发送失败", str(e))
        except serial.SerialException as e:
            QMessageBox.critical(self, "发送失败", f"串口错误: {e}")
    
    def convert_to_bytes(self, text: str, fmt: str) -> bytes:
        """将文本转换为字节数据"""
        if fmt == "ASCII":
            return text.encode('utf-8')
        
        elif fmt == "HEX":
            # 清理HEX字符串
            clean = ''.join(c for c in text if c.isalnum())
            if len(clean) % 2 != 0:
                raise ValueError("HEX长度必须为偶数")
            
            try:
                return bytes.fromhex(clean)
            except ValueError:
                raise ValueError("无效的HEX格式")
        
        elif fmt == "DEC":
            # 处理十进制数字（0-255）
            nums = []
            for part in text.split():
                for num_str in part.split(','):
                    if num_str.strip():
                        try:
                            num = int(num_str.strip())
                            if not 0 <= num <= 255:
                                raise ValueError(f"数字 {num} 超出范围 (0-255)")
                            nums.append(num)
                        except ValueError:
                            raise ValueError(f"无效的数字: {num_str}")
            
            return bytes(nums)
        
        elif fmt == "BIN":
            # 处理二进制字符串
            clean = ''.join(c for c in text if c in '01')
            if len(clean) % 8 != 0:
                raise ValueError("二进制长度必须是8的倍数")
            
            try:
                return bytes([int(clean[i:i+8], 2) for i in range(0, len(clean), 8)])
            except ValueError:
                raise ValueError("无效的二进制格式")
        
        else:
            raise ValueError(f"不支持的格式: {fmt}")
    
    def format_display(self, data: bytes, fmt: str) -> str:
        """格式化数据显示"""
        if fmt == "ASCII":
            try:
                return data.decode('utf-8', errors='replace')
            except:
                return "<解码错误>"
        
        elif fmt == "HEX":
            return data.hex(' ').upper()
        
        elif fmt == "DEC":
            return ' '.join(str(b) for b in data)
        
        elif fmt == "BIN":
            return ' '.join(f"{b:08b}" for b in data)
        
        return ""
    
    def add_chat_message(self, role: str, content: str):
        """添加聊天消息"""
        time_str = datetime.now().strftime("%H:%M:%S")
        
        # 根据角色设置样式
        if role == "RX":
            bg_color = "#2d3436"
            tag = "接收"
            align = "left"
        else:  # TX
            bg_color = "#1e3a5f"
            tag = "发送"
            align = "right"
        
        html = f"""
        <div style='text-align:{align}; margin:4px 0;'>
            <span style='font-size:10px; color:#7f8c8d;'>[{time_str}]</span>
            <div style='
                display:inline-block;
                background:{bg_color};
                color:#ecf0f1;
                padding:6px 10px;
                border-radius:8px;
                max-width:85%;
                word-wrap:break-word;
                font-family:Menlo,monospace;
                font-size:11px;
            '>
                <b style='color:#3498db;'>{tag}</b><br>
                {content}
            </div>
        </div>
        """
        
        self.chat_box.append(html)
        
        # 自动滚动
        if self.auto_scroll:
            self.chat_box.verticalScrollBar().setValue(
                self.chat_box.verticalScrollBar().maximum()
            )
    
    def add_system_msg(self, msg: str):
        """添加系统消息"""
        time_str = datetime.now().strftime("%H:%M:%S")
        html = f"""
        <div style='text-align:center; margin:6px 0;'>
            <span style='
                color:#f39c12;
                font-size:11px;
                background:#333;
                padding:2px 8px;
                border-radius:4px;
            '>
                [{time_str}] {msg}
            </span>
        </div>
        """
        self.chat_box.append(html)
    
    def manual_analyze(self):
        """手动触发分析"""
        self.run_analysis()
    
    def auto_analyze(self):
        """自动分析"""
        if self.auto_analyze_cb.isChecked() and len(self.data_buffer) >= 100:
            self.run_analysis()
    
    def run_analysis(self):
        """执行随机性分析"""
        total = len(self.data_buffer)
        if total < 100:
            self.issues_label.setText("数据量不足 (需要≥100字节)")
            return
        
        range_size = min(self.analyze_range.value(), total)
        analysis_data = self.data_buffer.get_data()[-range_size:]
        
        # 执行所有测试
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
        
        # 计算综合评分
        summary = RandomnessAnalyzer.comprehensive_score(results)
        
        # 更新UI
        score = summary["score"]
        self.score_bar.setValue(score)
        
        # 根据分数设置颜色
        if score >= 75:
            color = "#00ff88"  # 绿色
        elif score >= 60:
            color = "#f39c12"  # 橙色
        else:
            color = "#e74c3c"  # 红色
        
        self.score_bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
        self.score_label.setText(f"评分: {score}/100 [{summary['level']}]")
        
        # 显示问题
        issues_text = "\n".join(f"• {issue}" for issue in summary["issues"])
        self.issues_label.setText(issues_text)
        
        # 日志记录
        test_keys = ["chi_square", "runs", "autocorr", "entropy", "monobit", "frequency", "serial_corr"]
        log_lines = []
        for key in test_keys:
            if key in results and results[key].get("msg"):
                log_lines.append(results[key]["msg"])
        self.add_system_msg(f"分析 {range_size:,} 字节: {' | '.join(log_lines)}")
    
    def save_data(self):
        """保存数据到文件"""
        if len(self.data_buffer) == 0:
            QMessageBox.information(self, "提示", "暂无数据可保存")
            return
        
        # 生成默认文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"random_data_{timestamp}.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存随机数数据",
            default_name,
            "文本文件 (*.txt);;CSV文件 (*.csv);;所有文件 (*)"
        )
        
        if not file_path:
            return
        
        try:
            data = self.data_buffer.get_data()
            fmt = self.rx_format
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # 写入文件头
                f.write("# 随机数数据导出\n")
                f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 数据格式: {fmt}\n")
                f.write(f"# 总字节数: {len(data)}\n")
                f.write(f"# 分析范围: {self.analyze_range.value()} 字节\n")
                f.write("#" * 50 + "\n\n")
                
                # 写入数据
                if fmt == "HEX":
                    bytes_per_line = 16
                    for i in range(0, len(data), bytes_per_line):
                        chunk = data[i:i+bytes_per_line]
                        hex_str = " ".join(f"{b:02X}" for b in chunk)
                        f.write(f"{i:06d}: {hex_str}\n")
                
                elif fmt == "DEC":
                    nums_per_line = 10
                    for i in range(0, len(data), nums_per_line):
                        chunk = data[i:i+nums_per_line]
                        dec_str = " ".join(f"{b:3d}" for b in chunk)
                        f.write(f"{i:06d}: {dec_str}\n")
                
                elif fmt == "BIN":
                    bytes_per_line = 8
                    for i in range(0, len(data), bytes_per_line):
                        chunk = data[i:i+bytes_per_line]
                        bin_str = " ".join(f"{b:08b}" for b in chunk)
                        f.write(f"{i:06d}: {bin_str}\n")
                
                elif fmt == "ASCII":
                    bytes_per_line = 32
                    for i in range(0, len(data), bytes_per_line):
                        chunk = data[i:i+bytes_per_line]
                        ascii_str = "".join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                        f.write(f"{i:06d}: {ascii_str}\n")
            
            self.add_system_msg(f"已保存 {len(data):,} 字节到 {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件时出错: {e}")
    
    def clear_all(self):
        """清空所有数据"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有数据和图表吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 清空缓冲区
        self.data_buffer.clear()
        
        # 清空UI
        self.chat_box.clear()
        self.curve_time.setData([])
        self.bar_hist.setOpts(height=[0]*256)
        self.scatter_plot.setData([], [])
        self.curve_autocorr.setData([])
        
        # 重置分析结果
        self.score_bar.setValue(0)
        self.score_label.setText("评分: --/100")
        self.issues_label.setText("等待数据进行分析...")
        
        # 更新统计显示
        self.update_data_count()
        self.data_mean_label.setText("平均值: --")
        self.data_std_label.setText("标准差: --")
        self.data_range_label.setText("范围: --")
        self.data_rate_label.setText("接收速率: 0 B/s")
        
        self.add_system_msg("已清空所有数据")
    
    def handle_error(self, error_msg: str):
        """处理错误"""
        QMessageBox.critical(self, "串口异常", error_msg)
        self.close_serial()
    
    def safe_exit(self):
        """安全退出程序"""
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出程序吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.close()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.is_open:
            self.close_serial()
        
        # 停止所有定时器
        self.analysis_timer.stop()
        self.stats_timer.stop()
        self.plot_update_timer.stop()
        
        event.accept()
    
    # ========== 页面显示方法 ==========
    
    def show_serial_page(self):
        """显示串口设置页面"""
        self.pages_stack.setCurrentIndex(0)
        self.update_button_states(0)
    
    def show_log_page(self):
        """显示通信日志页面"""
        self.pages_stack.setCurrentIndex(1)
        self.update_button_states(1)
    
    def show_time_page(self):
        """显示时域分析页面"""
        self.pages_stack.setCurrentIndex(2)
        self.update_button_states(2)
    
    def show_plots_page(self):
        """显示频域分析页面"""
        self.pages_stack.setCurrentIndex(3)
        self.update_button_states(3)
    
    def show_stats_page(self):
        """显示实时统计页面"""
        self.pages_stack.setCurrentIndex(4)
        self.update_button_states(4)
    
    def show_analysis_page(self):
        """显示随机性分析页面"""
        self.pages_stack.setCurrentIndex(5)
        self.update_button_states(5)
    
    def update_button_states(self, active_index):
        """更新导航按钮状态"""
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == active_index)
    
    # ========== 其他页面创建方法 ==========
    
    def create_time_page(self):
        """创建时域分析页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 时域图
        time_group = QGroupBox("时域分析图")
        time_layout = QVBoxLayout()
        
        self.plot_time = pg.PlotWidget(title="时域波形")
        self.setup_plot(self.plot_time, "接收序号", "数值(0-255)", (0, 256))
        self.curve_time = self.plot_time.plot(pen=pg.mkPen('#00ff88', width=1.5))
        
        time_layout.addWidget(self.plot_time)
        time_group.setLayout(time_layout)
        layout.addWidget(time_group, 1)
        
        # 直方图
        hist_group = QGroupBox("字节分布直方图")
        hist_layout = QVBoxLayout()
        
        self.plot_hist = pg.PlotWidget(title="字节分布")
        self.setup_plot(self.plot_hist, "字节值", "出现频次", None)
        self.bar_hist = pg.BarGraphItem(
            x=list(range(256)),
            height=[0]*256,
            width=1,
            brush=pg.mkBrush('#4a90e280')
        )
        self.plot_hist.addItem(self.bar_hist)
        
        hist_layout.addWidget(self.plot_hist)
        hist_group.setLayout(hist_layout)
        layout.addWidget(hist_group, 1)
        
        self.pages_stack.addTab(page, "")
    
    def create_plots_page(self):
        """创建频域分析页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 散点图
        scatter_group = QGroupBox("相邻字节相关性散点图")
        scatter_layout = QVBoxLayout()
        
        self.plot_scatter = pg.PlotWidget(title="相邻字节相关性")
        self.setup_plot(self.plot_scatter, "当前字节Xn", "下一字节Xn+1", (0, 256))
        self.scatter_plot = pg.ScatterPlotItem(
            symbol='o',
            size=3,
            brush=pg.mkBrush('#e94b3c80'),
            pen=None
        )
        self.plot_scatter.addItem(self.scatter_plot)
        
        scatter_layout.addWidget(self.plot_scatter)
        scatter_group.setLayout(scatter_layout)
        layout.addWidget(scatter_group, 1)
        
        # 自相关图
        autocorr_group = QGroupBox("自相关分析图")
        autocorr_layout = QVBoxLayout()
        
        self.plot_autocorr = pg.PlotWidget(title="自相关分析")
        self.setup_plot(self.plot_autocorr, "延迟阶数", "相关系数", (-1, 1))
        self.plot_autocorr.setXRange(0, 50)  # 初始x范围
        self.plot_autocorr.addLine(y=0, pen=pg.mkPen('#666', style=Qt.PenStyle.DashLine))
        self.plot_autocorr.addLine(y=0.1, pen=pg.mkPen('#f39c12', style=Qt.PenStyle.DashLine))
        self.plot_autocorr.addLine(y=-0.1, pen=pg.mkPen('#f39c12', style=Qt.PenStyle.DashLine))
        # 初始占位数据
        x = np.arange(1, 51)
        y = np.zeros(50)
        self.curve_autocorr = self.plot_autocorr.plot(
            x, y, 
            pen=pg.mkPen('#9b59b6', width=2),
            symbol='o', symbolSize=5, symbolBrush='#9b59b6',
            name='自相关'
        )
        
        autocorr_layout.addWidget(self.plot_autocorr)
        autocorr_group.setLayout(autocorr_layout)
        layout.addWidget(autocorr_group, 1)
        
        self.pages_stack.addTab(page, "")
    
    def create_stats_page(self):
        """创建实时统计页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        
        stats_group = QGroupBox("📈 实时数据统计")
        stats_group.setStyleSheet("""
            QGroupBox {
                margin-top: 8px;
                padding-top: 14px;
            }
        """)
        stats_layout = QVBoxLayout()
        
        # 统计图表布局（可以添加更多图表）
        chart_layout = QHBoxLayout()
        
        # 统计标签网格
        grid_layout = QGridLayout()
        grid_layout.setSpacing(12)
        
        stat_style = """
            QLabel {
                background-color: #25252d;
                color: #e8e8f0;
                padding: 12px 16px;
                border-radius: 6px;
                border: 1px solid #353540;
                font-weight: 500;
                font-size: 13px;
                min-width: 150px;
                min-height: 40px;
                text-align: left;
            }
        """
        
        self.data_count_label = QLabel("📊 数据量: 0 字节")
        self.data_count_label.setStyleSheet(stat_style)
        self.data_count_label.setToolTip("已接收数据的总字节数")
        grid_layout.addWidget(self.data_count_label, 0, 0)
        
        self.data_rate_label = QLabel("⚡ 速率: 0 B/s")
        self.data_rate_label.setStyleSheet(stat_style)
        self.data_rate_label.setToolTip("数据接收速率")
        grid_layout.addWidget(self.data_rate_label, 0, 1)
        
        self.data_mean_label = QLabel("📊 平均值: --")
        self.data_mean_label.setStyleSheet(stat_style)
        self.data_mean_label.setToolTip("数据的平均值 (0-255)")
        grid_layout.addWidget(self.data_mean_label, 1, 0)
        
        self.data_std_label = QLabel("σ 标准差: --")
        self.data_std_label.setStyleSheet(stat_style)
        self.data_std_label.setToolTip("数据的标准差")
        grid_layout.addWidget(self.data_std_label, 1, 1)
        
        self.data_range_label = QLabel("↔ 范围: --")
        self.data_range_label.setStyleSheet(stat_style)
        self.data_range_label.setToolTip("数据的最小值和最大值范围")
        grid_layout.addWidget(self.data_range_label, 2, 0)
        
        self.data_min_label = QLabel("📉 最小值: --")
        self.data_min_label.setStyleSheet(stat_style)
        self.data_min_label.setToolTip("数据的最小值")
        grid_layout.addWidget(self.data_min_label, 2, 1)
        
        self.data_max_label = QLabel("📈 最大值: --")
        self.data_max_label.setStyleSheet(stat_style)
        self.data_max_label.setToolTip("数据的最大值")
        grid_layout.addWidget(self.data_max_label, 3, 0)
        
        # 更多统计信息
        self.data_median_label = QLabel("📊 中位数: --")
        self.data_median_label.setStyleSheet(stat_style)
        self.data_median_label.setToolTip("数据的中位数")
        grid_layout.addWidget(self.data_median_label, 3, 1)
        
        self.data_variance_label = QLabel("📊 方差: --")
        self.data_variance_label.setStyleSheet(stat_style)
        self.data_variance_label.setToolTip("数据的方差")
        grid_layout.addWidget(self.data_variance_label, 4, 0)
        
        self.data_cv_label = QLabel("📊 变异系数: --")
        self.data_cv_label.setStyleSheet(stat_style)
        self.data_cv_label.setToolTip("数据的变异系数")
        grid_layout.addWidget(self.data_cv_label, 4, 1)
        
        self.data_skewness_label = QLabel("📊 偏度: --")
        self.data_skewness_label.setStyleSheet(stat_style)
        self.data_skewness_label.setToolTip("数据的偏度")
        grid_layout.addWidget(self.data_skewness_label, 5, 0)
        
        self.data_kurtosis_label = QLabel("📊 峰度: --")
        self.data_kurtosis_label.setStyleSheet(stat_style)
        self.data_kurtosis_label.setToolTip("数据的峰度")
        grid_layout.addWidget(self.data_kurtosis_label, 5, 1)
        
        stats_layout.addLayout(grid_layout)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 说明文本
        info_label = QLabel("实时统计信息每秒自动更新，基于所有已接收数据计算。")
        info_label.setStyleSheet("color: #bdc3c7; font-size: 11px; padding: 8px; background: #25252d; border-radius: 6px;")
        layout.addWidget(info_label)
        
        self.pages_stack.addTab(page, "")
    
    def create_analysis_page(self):
        """创建随机性分析页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        
        analysis_group = QGroupBox("随机性分析")
        analysis_layout = QVBoxLayout()
        
        # 参数设置
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("分析最近:"))
        self.analyze_range = QSpinBox()
        self.analyze_range.setRange(100, 100000)
        self.analyze_range.setValue(1000)
        self.analyze_range.setSingleStep(100)
        self.analyze_range.setSuffix(" 字节")
        param_layout.addWidget(self.analyze_range)
        
        param_layout.addSpacing(20)
        param_layout.addWidget(QLabel("自动分析:"))
        self.auto_analyze_cb = QCheckBox("启用")
        self.auto_analyze_cb.setToolTip("自动执行随机性分析")
        self.auto_analyze_cb.setChecked(True)
        self.auto_analyze_cb.stateChanged.connect(self.on_auto_analyze_changed)
        param_layout.addWidget(self.auto_analyze_cb)
        
        param_layout.addStretch()
        analysis_layout.addLayout(param_layout)
        
        # 评分显示
        score_layout = QHBoxLayout()
        self.score_label = QLabel("随机性评分: --/100")
        self.score_label.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setTextVisible(True)
        
        score_layout.addWidget(self.score_label, 2)
        score_layout.addWidget(self.score_bar, 3)
        analysis_layout.addLayout(score_layout)
        
        # 分析按钮
        button_layout = QHBoxLayout()
        self.analyze_btn = QPushButton("📊 立即分析")
        self.analyze_btn.setToolTip("立即分析随机性")
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ab69c6;
            }
        """)
        self.analyze_btn.clicked.connect(self.manual_analyze)
        
        self.clear_all_btn = QPushButton("🗑️ 清空所有数据")
        self.clear_all_btn.setToolTip("清空所有数据和图表")
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f75c4c;
            }
        """)
        self.clear_all_btn.clicked.connect(self.clear_all)
        
        button_layout.addWidget(self.analyze_btn)
        button_layout.addWidget(self.clear_all_btn)
        button_layout.addStretch()
        analysis_layout.addLayout(button_layout)
        
        # 问题诊断
        issues_group = QGroupBox("问题诊断")
        issues_layout = QVBoxLayout()
        
        self.issues_label = QLabel("等待数据进行分析...")
        self.issues_label.setWordWrap(True)
        self.issues_label.setStyleSheet("""
            QLabel {
                color: #bdc3c7;
                padding: 12px;
                background-color: #25252d;
                border-radius: 6px;
                border: 1px solid #353540;
                min-height: 80px;
            }
        """)
        issues_layout.addWidget(self.issues_label)
        issues_group.setLayout(issues_layout)
        analysis_layout.addWidget(issues_group)
        
        # 详细测试结果（可展开）
        details_group = QGroupBox("详细测试结果")
        details_layout = QVBoxLayout()
        
        self.test_details_text = QTextEdit()
        self.test_details_text.setReadOnly(True)
        self.test_details_text.setMaximumHeight(150)
        self.test_details_text.setFont(QFont("Menlo", 9))
        self.test_details_text.setStyleSheet("""
            background-color: #25252d;
            border-radius: 4px;
            padding: 6px;
            font-family: 'Menlo', 'Consolas', monospace;
        """)
        self.test_details_text.setPlaceholderText("点击'立即分析'查看详细的测试结果...")
        details_layout.addWidget(self.test_details_text)
        details_group.setLayout(details_layout)
        analysis_layout.addWidget(details_group)
        
        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)
        
        self.pages_stack.addTab(page, "")
    
    def clear_chat_log(self):
        """清空聊天日志"""
        self.chat_box.clear()
        self.add_system_msg("已清空通信日志")

# ==================== 主程序入口 ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 配置pyqtgraph
    pg.setConfigOptions(
        antialias=True,
        background="#25252d",
        foreground="#e0e0e0"
    )
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())