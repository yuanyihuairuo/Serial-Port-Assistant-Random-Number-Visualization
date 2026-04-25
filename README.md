# 串口助手 & 随机数分析工具

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.x-green)](https://www.riverbankcomputing.com/software/pyqt/)
[![pyqtgraph](https://img.shields.io/badge/pyqtgraph-0.13%2B-orange)](http://www.pyqtgraph.com/)

一个功能强大的串口通信与随机数质量分析工具，支持多种数据格式、实时图表、统计测试和硬件随机数评估。

A powerful serial communication and random number quality analysis tool supporting multiple data formats, real-time charts, statistical tests, and hardware random number evaluation.

---

## 📋 目录 / Table of Contents

- [串口助手 \& 随机数分析工具](#串口助手--随机数分析工具)
  - [📋 目录 / Table of Contents](#-目录--table-of-contents)
  - [✨ 功能特点 / Features](#-功能特点--features)
    - [串口通信 / Serial Communication](#串口通信--serial-communication)
    - [随机数分析 / Random Number Analysis](#随机数分析--random-number-analysis)
    - [可视化 / Visualization](#可视化--visualization)
  - [💻 系统要求 / System Requirements](#-系统要求--system-requirements)
  - [📦 安装 / Installation](#-安装--installation)
  - [🚀 快速开始 / Quick Start](#-快速开始--quick-start)
    - [串口通信模式 / Serial Communication Mode](#串口通信模式--serial-communication-mode)
    - [随机数分析模式 / Random Number Analysis Mode](#随机数分析模式--random-number-analysis-mode)
  - [📖 使用指南 / User Guide](#-使用指南--user-guide)
    - [数据格式示例 / Data Format Examples](#数据格式示例--data-format-examples)
    - [快捷键 / Shortcut Keys](#快捷键--shortcut-keys)
  - [🔬 随机数测试说明 / Random Number Tests](#-随机数测试说明--random-number-tests)
    - [评分体系 / Scoring System](#评分体系--scoring-system)
    - [评分等级 / Score Levels](#评分等级--score-levels)
  - [❓ 常见问题 / FAQ](#-常见问题--faq)
  - [🔧 技术细节 / Technical Details](#-技术细节--technical-details)
    - [核心算法 / Core Algorithms](#核心算法--core-algorithms)
    - [性能优化 / Performance Optimizations](#性能优化--performance-optimizations)
    - [缓冲区配置 / Buffer Configuration](#缓冲区配置--buffer-configuration)
  - [🙏 致谢 / Acknowledgments](#-致谢--acknowledgments)

---

## ✨ 功能特点 / Features

### 串口通信 / Serial Communication

| 功能 / Feature | 说明 / Description |
| -------------- | ----------------- |
| 🔌 自动扫描端口 / Auto Scan | 自动检测可用串口设备 / Automatically detect available serial ports |
| ⚡ 多波特率支持 / Multiple Baud Rates | 9600 ~ 921600 bps |
| 📊 灵活参数配置 / Flexible Parameters | 数据位(5-8)、校验位(N/E/O/M/S)、停止位(1/1.5/2) / Data bits, Parity, Stop bits |
| 📡 多种数据格式 / Multiple Data Formats | ASCII / HEX / DEC / BIN |
| 🔄 累积模式 / Accumulation Mode | 智能合并连续数据包 / Smart merging of continuous data packets |
| 🤖 自动发送 / Auto Send | 定时自动发送数据 / Timed automatic data transmission |
| 💾 数据导出 / Data Export | 保存接收数据为文本文件 / Save received data as text files |

### 随机数分析 / Random Number Analysis

| 测试项目 / Test | 说明 / Description |
| --------------- | ------------------ |
| 📊 卡方检验 / Chi-Square Test | 检测字节分布均匀性 / Detect byte distribution uniformity |
| 🔄 游程检验 / Runs Test | 检测序列随机性模式 / Detect randomness patterns in sequences |
| 📈 自相关分析 / Autocorrelation | 检测数据间相关性 / Detect correlations between data points |
| 🔢 信息熵 / Information Entropy | 衡量数据不确定性 / Measure data uncertainty |
| ⚖️ 单比特检验 / Single Bit Test | 比特平衡性测试 / Bit balance testing |
| 📐 频率检验 / Frequency Test | 高低字节分布测试 / High/low byte distribution testing |
| 🔗 串行相关 / Serial Correlation | 相邻字节相关性 / Adjacent byte correlation |
| 🎵 频谱分析 / Spectral Analysis | 检测周期性模式 / Detect periodic patterns |

### 可视化 / Visualization

- 📉 实时时域波形图 / Real-time time domain waveform
- 📊 字节分布直方图 / Byte distribution histogram
- 🔵 相邻字节相关性散点图 / Adjacent byte correlation scatter plot
- 📐 自相关系数曲线图 / Autocorrelation coefficient curve
- 🎯 综合评分与改进建议 / Overall score with improvement suggestions

---

## 💻 系统要求 / System Requirements

| 项目 / Item | 要求 / Requirement |
| ----------- | ------------------ |
| 操作系统 / OS | Windows 7+ / Linux / macOS |
| Python | 3.8 或更高版本 / 3.8 or higher |
| 内存 / RAM | 512 MB+ (推荐 1 GB / 1 GB recommended) |
| 硬件 / Hardware | 可用串口 (USB转串口/物理串口) / Available serial port (USB-to-serial / physical serial) |
| 驱动 / Drivers | CH340 / CP2102 / FTDI 等 / etc. |

---

## 📦 安装 / Installation

```bash
# 克隆仓库 / Clone repository
git clone https://github.com/yuanyihuairuo/Serial-Port-Assistant-Random-Number-Visualization.git

# 安装依赖 / Install dependencies

# 运行程序 / Run the program
python serial_analyzer.py
```

**requirements.txt:**
```
PyQt6>=6.4.0
pyqtgraph>=0.13.0
pyserial>=3.5
numpy>=1.21.0
```

---

## 🚀 快速开始 / Quick Start

### 串口通信模式 / Serial Communication Mode

1. 选择正确的串口号和波特率，点击 **连接串口** / Select the correct COM port and baud rate, click **Connect Serial Port**
2. 在底部输入框输入内容，选择格式 (ASCII/HEX)，点击 **发送** / Enter data in the bottom input box, select format (ASCII/HEX), click **Send**
3. 接收数据自动显示在终端区域 / Received data automatically displays in the terminal area

### 随机数分析模式 / Random Number Analysis Mode

1. 点击顶部下拉菜单，切换到 **随机数分析** 页面 / Click the top dropdown menu to switch to **Random Number Analysis** page
2. 确保已接收 ≥100 字节数据 / Ensure at least 100 bytes of data have been received
3. 点击 **立即分析** 或等待自动分析 / Click **Analyze Now** or wait for auto-analysis
4. 查看综合评分和图表结果 / View the overall score and chart results

---

## 📖 使用指南 / User Guide

### 数据格式示例 / Data Format Examples

| 格式 / Format | 输入示例 / Input Example | 说明 / Description |
| ------------- | ------------------------ | ------------------ |
| ASCII | `Hello` | 直接发送文本 / Send text directly |
| HEX | `48 65 6C 6C 6F` | 十六进制字节 / Hexadecimal bytes |
| DEC | `72 101 108 108 111` | 十进制字节 / Decimal bytes |
| BIN | `01001000 01100101` | 二进制字节 / Binary bytes |

### 快捷键 / Shortcut Keys

| 操作 / Action | 快捷键 / Shortcut |
| ------------- | ----------------- |
| 发送数据 / Send Data | `Ctrl + Enter` |
| 清空接收区 / Clear Receive Area | `Ctrl + R` |
| 清空发送区 / Clear Send Area | `Ctrl + T` |
| 切换连接 / Toggle Connection | `Ctrl + C` |

---

## 🔬 随机数测试说明 / Random Number Tests

### 评分体系 / Scoring System

| 测试项目 / Test | 分值 / Score | 通过标准 / Passing Criteria |
| --------------- | ------------ | --------------------------- |
| 卡方检验 / Chi-Square Test | 20 | χ² < 310 |
| 游程检验 / Runs Test | 15 | \|z\| < 2.58 |
| 自相关 / Autocorrelation | 15 | 最大\|r\| < 0.1 / Max \|r\| < 0.1 |
| 信息熵 / Information Entropy | 12 | 熵值 > 7.5 bits / Entropy > 7.5 bits |
| 单比特检验 / Single Bit Test | 8 | z < 1.96 |
| 频率检验 / Frequency Test | 8 | χ² < 3.84 |
| 串行相关 / Serial Correlation | 8 | \|ρ\| < 0.1 |
| 频谱分析 / Spectral Analysis | 8 | 峰值比 < 10 / Peak ratio < 10 |

### 评分等级 / Score Levels

| 分数 / Score | 等级 / Level | 说明 / Description |
| ------------ | ------------ | ------------------ |
| 85-100 | 优秀 / Excellent | 适合密码学应用 / Suitable for cryptographic applications |
| 70-84 | 良好 / Good | 随机性良好 / Good randomness |
| 50-69 | 合格 / Acceptable | 满足基本要求 / Meets basic requirements |
| 0-49 | 待优化 / Needs Improvement | 存在明显模式 / Obvious patterns exist |

---

## ❓ 常见问题 / FAQ

<details>
<summary><b>提示"未检测到串口"怎么办？ / What if "No serial port detected"?</b></summary>

- 检查串口线连接 / Check serial cable connection
- 安装对应驱动程序 (CH340 / CP210x / FTDI) / Install corresponding drivers
- Linux用户执行：`sudo usermod -a -G dialout $USER` / Linux users run: `sudo usermod -a -G dialout $USER`
</details>

<details>
<summary><b>数据接收出现乱码？ / Receiving garbled data?</b></summary>

- 检查波特率、数据位、校验位是否与设备匹配 / Check if baud rate, data bits, parity match the device
- 尝试切换 ASCII/HEX 显示格式 / Try switching ASCII/HEX display format
</details>

<details>
<summary><b>随机数分析提示数据量不足？ / Random number analysis shows insufficient data?</b></summary>

- 确保已接收至少 100 字节数据 / Ensure at least 100 bytes of data have been received
- 可使用累积模式或增加发送次数 / Use accumulation mode or increase send count
</details>

<details>
<summary><b>图表显示卡顿？ / Charts are lagging?</b></summary>

- 程序已做性能优化，可关闭不使用的图表标签页 / Performance optimizations are implemented, close unused chart tabs
- 减少分析数据量（调整分析范围）/ Reduce the amount of data for analysis (adjust analysis range)
</details>

---

## 🔧 技术细节 / Technical Details

### 核心算法 / Core Algorithms

| 测试 / Test | 公式 / Formula |
| ----------- | -------------- |
| 卡方检验 / Chi-Square Test | χ² = Σ((O_i - E)² / E) |
| 游程检验 / Runs Test | z = (runs - μ) / σ |
| 信息熵 / Information Entropy | H = -Σ(p_i × log₂(p_i)) |
| 自相关 / Autocorrelation | r(k) = Σ((x_t - μ)(x_{t+k} - μ)) / (n × σ²) |

### 性能优化 / Performance Optimizations

- **循环缓冲区 / Circular Buffer**：限制内存占用，支持大容量数据 / Limit memory usage, support large data volumes
- **延迟渲染 / Deferred Rendering**：分离数据接收与 UI 更新 / Separate data reception from UI updates
- **数据采样 / Data Sampling**：大数据集自动降采样展示 / Automatic downsampling for large datasets
- **异步串口 / Asynchronous Serial**：独立线程处理，防止界面卡顿 / Independent thread processing to prevent UI freezing

### 缓冲区配置 / Buffer Configuration

| 参数 / Parameter | 限制 / Limit |
| ---------------- | ------------ |
| 最大容量 / Maximum Capacity | 100,000 字节 / bytes |
| 时域显示 / Time Domain Display | ≤ 2,000 点 / points |
| 散点图 / Scatter Plot | ≤ 3,000 点 / points |
| 自相关 / Autocorrelation | ≤ 50 阶 / orders |

---

## 🙏 致谢 / Acknowledgments

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架 / GUI Framework
- [pyqtgraph](http://www.pyqtgraph.com/) - 实时图表库 / Real-time Chart Library
- [pyserial](https://github.com/pyserial/pyserial) - 串口通信库 / Serial Communication Library
- [NumPy](https://numpy.org/) - 数值计算库 / Numerical Computing Library

---

**⭐ 如果这个项目对你有帮助，请给个 Star！ / If this project helps you, please give it a Star!**