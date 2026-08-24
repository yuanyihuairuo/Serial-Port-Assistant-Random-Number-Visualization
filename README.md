# ⚡ 串口助手 · 随机数分析 (V2.0 Web)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](https://fastapi.tiangolo.com/)
[![Vue3](https://img.shields.io/badge/Vue-3-42b883)](https://vuejs.org/)
[![ECharts](https://img.shields.io/badge/ECharts-5-aa344d)](https://echarts.apache.org/)

一个功能强大的**串口通信 + 随机数质量分析**工具，采用 **现代 Web UI**（Vue 3 + ECharts）+ **Python 后端**（FastAPI + WebSocket + pyserial）架构。

支持多种数据格式、实时流式图表、统计测试与硬件随机数评估。

---

## 🎨 为什么重构为 Web UI？

旧版为 `serial_random_optimized.py`（PyQt6 单文件，1500 行）。本次将其重构为**前后端分离**的现代架构：

- **UI 层不再是 Python**：使用 Vue 3 + ECharts 构建现代深色毛玻璃界面，视觉效果与现代 AI Agent 工具一致。
- **实时数据流**：串口数据通过 WebSocket 实时推送到前端，图表与终端毫秒级更新。
- **模块化后端**：串口服务、随机性分析、缓冲、Web 接口各自独立成模块，便于维护与扩展。
- **零前端构建**：Vue/ECharts 以本地文件形式内置（`frontend/vendor/`），无需 Node/npm，离线可用。

---

## 📋 目录结构

```
serial_random_optimized.py   # 旧版 PyQt6 单文件（已修复，仅供历史参考）
backend/
  main.py            # FastAPI 应用：REST + WebSocket + 静态资源服务 + 广播循环
  serial_service.py  # 串口收发线程（真实串口 / 模拟源），循环缓冲，线程安全
  analysis.py        # 随机性测试套件 + 循环缓冲（复用自旧版，仅依赖 numpy）
frontend/
  index.html         # 页面结构（Vue 模板）
  app.js             # 前端逻辑：WebSocket、ECharts 渲染、状态管理
  style.css          # 现代深色玻璃拟态主题
  vendor/            # 本地内置的 Vue3 / ECharts（离线可用）
run.py               # 启动脚本（自动打开浏览器）
start.sh             # 一键启动（Linux / macOS 终端）
start.command        # 一键启动（macOS 双击）
requirements.txt
```

---

## 💻 环境要求 / Requirements

| 项目 | 要求 |
|------|------|
| Python | 3.10 或更高 |
| 浏览器 | 任意现代浏览器（Chrome / Edge / Safari） |
| 硬件 | 可选：USB 转串口 / 物理串口（无硬件可用「模拟」数据源体验） |

---

## 🚀 一键启动 / One-Click Start

无需手动安装，双击即可运行：

- **macOS**：双击 `start.command`（若提示权限，先在终端执行 `chmod +x start.command`）
- **Linux / macOS 终端**：执行 `./start.sh`

脚本会自动创建虚拟环境、安装依赖、启动服务并**自动打开浏览器**。

```bash
# 手动启动（自动打开浏览器）
.venv/bin/python run.py
# 指定端口 / 不自动打开浏览器
.venv/bin/python run.py --port 8080 --no-browser
```

打开浏览器访问 **http://127.0.0.1:8000**。

> 首次打开默认处于「演示」模式，无需串口即可体验完整分析；
> 在侧边栏选择不同**演示图案**即可观察评分变化；连接真实设备时选择「串口」并配置参数。

---

## 🧪 演示模式 / Demo Mode

**无需任何串口硬件**即可展示软件全部功能。切换到「演示」数据源后，可选择不同数据图案，观察随机性分析的差异：

| 图案 | 特征 | 预期评分 |
|------|------|----------|
| 均匀随机 | 随机性佳 | 优秀 / 良好 |
| 正弦波形 | 强周期性 | 待优化 |
| 偏置分布 | 熵偏低 | 待优化 |
| 重复序列 | 可预测 | 待优化 |
| 线性递增 | 全可预测 | 待优化 |
| 高低交替 | 串行相关 | 待优化 |

切换图案后自动重连并清空缓冲，评分会随图案实时变化，直观展示分析器的判别能力。

---

## ✨ 功能特点 / Features

### 串口通信
- 🔌 自动扫描可用串口设备
- ⚡ 多波特率（9600 ~ 921600）、数据位 / 校验位 / 停止位可配
- 📡 多种收发格式：ASCII / HEX / DEC / BIN
- 🤖 定时自动发送
- 💾 数据导出为文本
- 🧪 **演示模式**：无需硬件即可切换多图案展示全链路

### 接收区滚动
- 📜 **内部滚动 + 自动跟随**：接收区独立滚动，底部发送/控制面板始终可见
- ⬇ 上滑即暂停自动滚动，显示「回到底部」按钮，点击恢复跟随

### 随机数分析（实时）
- 📊 卡方检验 / 游程检验 / 信息熵 / 自相关
- ⚖️ 单比特检验 / 频率检验 / 串行相关 / 频谱分析
- 🎯 综合评分（0-100）+ 等级 + 改进建议
- 📈 实时统计（均值/标准差/极值/范围/变异系数/中位数/峰度）

### 可视化（ECharts 实时图表）
- 📉 时域波形
- 📊 字节分布直方图
- 🔵 相邻字节相关性散点图
- 📐 自相关系数曲线（含 ±0.1 参考线）

---

## 🔌 API 一览 / REST & WebSocket

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ports` | 扫描串口 |
| GET | `/api/status` | 当前连接状态 |
| POST | `/api/open` | 打开串口（`mode: serial/sim`） |
| POST | `/api/close` | 关闭串口 |
| POST | `/api/send` | 发送数据（`data + fmt`） |
| POST | `/api/analyze` | 立即分析（`size` 字节） |
| POST | `/api/clear` | 清空缓冲 |
| WS  | `/ws` | 实时推送 `rx` / `update` / `analysis` |

---

## 🔬 评分体系 / Scoring

| 测试 | 分值 | 通过标准 |
|------|------|----------|
| 卡方检验 | 20 | χ² < 310 |
| 游程检验 | 15 | \|z\| < 2.58 |
| 自相关 | 15 | 最大\|r\| < 0.1 |
| 信息熵 | 12 | 熵值 > 7.5 bits |
| 单比特检验 | 8 | z < 1.96 |
| 频率检验 | 8 | χ² < 3.84 |
| 串行相关 | 8 | \|ρ\| < 0.1 |
| 频谱分析 | 8 | 峰值比 < 10 |

**等级**：85-100 优秀 · 70-84 良好 · 50-69 合格 · 0-49 待优化。

---

## 🙏 致谢 / Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - 异步 Web 后端
- [Vue 3](https://vuejs.org/) - 前端框架
- [Apache ECharts](https://echarts.apache.org/) - 实时图表
- [pyserial](https://github.com/pyserial/pyserial) - 串口通信
- [NumPy](https://numpy.org/) - 数值计算
