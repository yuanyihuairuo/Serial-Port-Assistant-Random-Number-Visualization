"""随机数质量分析核心算法（无 UI 依赖）。

从旧版 `serial_random_optimized.py` 提取并独立成模块，仅依赖 numpy。
所有测试均返回 dict 结果，可在任意后端 / 前端复用。
"""
from __future__ import annotations

from typing import Dict

import numpy as np


# ==================== 循环缓冲区 ====================
class CircularBuffer:
    """基于 numpy 的定长循环缓冲区，用于保存接收的字节。

    限制内存占用并支持大容量数据；`get_recent_data` 用于图表降采样展示。
    """

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
        if start < self.max_size:
            return np.concatenate([self.buffer[start:], self.buffer[:end_idx % self.max_size]])
        start_rel = start - self.max_size
        return self.buffer[start_rel:end_idx % self.max_size].copy()

    def __len__(self) -> int:
        return self.length

    def clear(self):
        self.start_idx = 0
        self.length = 0


# ==================== 随机性测试 ====================
class RandomnessAnalyzer:
    """字节级随机性测试套件（每项返回通过/未通过 + 统计量 + 说明）。"""

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
        return {"passed": passed, "max_corr": float(max_corr), "msg": f"自相关={max_corr:.3f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def entropy_test(data: np.ndarray) -> dict:
        if len(data) < 10:
            return {"passed": False, "entropy": 0, "msg": "数据量不足"}
        hist, _ = np.histogram(data, bins=256, range=(0, 256))
        probs = hist[hist > 0] / len(data)
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        passed = entropy > 7.5
        return {"passed": passed, "entropy": float(entropy), "msg": f"熵值={entropy:.2f}bits {'通过' if passed else '偏低'}"}

    @staticmethod
    def monobit_test(data: np.ndarray) -> dict:
        if len(data) < 100:
            return {"passed": False, "statistic": 0, "msg": "数据量不足"}
        bits = np.unpackbits(data.astype(np.uint8))
        ones_count = np.sum(bits)
        n = len(bits)
        s = abs(ones_count - n / 2) / np.sqrt(n / 4)
        passed = s < 1.96
        return {"passed": passed, "statistic": float(s), "balance": float(ones_count / n), "msg": f"比特平衡={ones_count/n:.3f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def frequency_test(data: np.ndarray) -> dict:
        if len(data) < 100:
            return {"passed": False, "statistic": 0, "msg": "数据量不足"}
        low_count = np.sum(data < 128)
        expected = len(data) / 2
        chi2 = ((low_count - expected) ** 2 + (len(data) - low_count - expected) ** 2) / expected
        passed = chi2 < 3.84
        return {"passed": passed, "statistic": float(chi2), "ratio": float(low_count / len(data)), "msg": f"高低比={low_count/len(data):.3f} {'通过' if passed else '不通过'}"}

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
        return {"passed": passed, "correlation": float(correlation), "msg": f"相邻相关={correlation:.3f} {'通过' if passed else '不通过'}"}

    @staticmethod
    def spectral_test(data: np.ndarray) -> dict:
        if len(data) < 128:
            return {"passed": False, "peak_ratio": 0, "msg": "数据量不足128字节"}
        fft_data = np.fft.fft(data.astype(np.float64))
        magnitude = np.abs(fft_data[:len(fft_data) // 2])
        mean_mag = np.mean(magnitude)
        max_mag = np.max(magnitude)
        peak_ratio = max_mag / mean_mag if mean_mag > 0 else 0
        passed = peak_ratio < 10.0
        return {"passed": passed, "peak_ratio": float(peak_ratio), "msg": f"频谱峰值比={peak_ratio:.2f} {'通过' if passed else '可能有周期性'}"}

    @staticmethod
    def get_statistics(data: np.ndarray) -> Dict[str, float]:
        if len(data) == 0:
            return {}
        mean = float(np.mean(data))
        std = float(np.std(data))
        return {
            "mean": mean, "std": std,
            "min": float(np.min(data)), "max": float(np.max(data)),
            "range": float(np.max(data) - np.min(data)), "median": float(np.median(data)),
            "variance": float(np.var(data)),
            "cv": float(np.std(data) / (mean + 1e-10)),
            "skewness": float(np.mean(((data - mean) / (std + 1e-10)) ** 3)),
            "kurtosis": float(np.mean(((data - mean) / (std + 1e-10)) ** 4)),
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
        return {"score": int(min(100, max(0, score))), "level": level, "issues": issues}


# ==================== 全套分析 ====================
def run_full_analysis(data: np.ndarray) -> dict:
    """运行完整随机性分析并返回所有结果 + 综合评分。"""
    results = {
        "chi_square": RandomnessAnalyzer.chi_square_test(data),
        "runs": RandomnessAnalyzer.runs_test(data),
        "autocorr": RandomnessAnalyzer.autocorrelation_test(data),
        "entropy": RandomnessAnalyzer.entropy_test(data),
        "monobit": RandomnessAnalyzer.monobit_test(data),
        "frequency": RandomnessAnalyzer.frequency_test(data),
        "serial_corr": RandomnessAnalyzer.serial_correlation_test(data),
        "spectral": RandomnessAnalyzer.spectral_test(data),
    }
    summary = RandomnessAnalyzer.comprehensive_score(results)
    return {"results": results, "summary": summary, "statistics": RandomnessAnalyzer.get_statistics(data)}


def build_chart_data(buffer: CircularBuffer,
                     time_points: int = 2000,
                     scatter_points: int = 3000,
                     max_lag: int = 50) -> dict:
    """由循环缓冲一键构建四张图所需的数据（时域/直方图/散点/自相关）。"""
    out = {"time": [], "hist": [], "scatter_x": [], "scatter_y": [], "autocorr": []}
    if len(buffer) < 2:
        return out

    all_data = buffer.get_data()

    # 时域（降采样）
    time_data = buffer.get_recent_data(time_points)
    if len(time_data) >= 10:
        out["time"].extend((time_data / 255.0).tolist())

    # 直方图（归一化）
    hist, _ = np.histogram(all_data, bins=256, range=(0, 256))
    max_count = max(int(np.max(hist)), 1)
    out["hist"].extend((hist / max_count).tolist())

    # 相邻散点（降采样）
    if len(all_data) >= 2:
        limit = min(scatter_points, len(all_data) - 1)
        x = all_data[-limit - 1:-1] / 255.0
        y = all_data[-limit:] / 255.0
        out["scatter_x"].extend(x.tolist())
        out["scatter_y"].extend(y.tolist())

    # 自相关
    if len(all_data) > 100:
        sample = all_data[-5000:] if len(all_data) > 5000 else all_data
        data_norm = (sample - np.mean(sample)) / (np.std(sample) + 1e-10)
        lag_limit = min(max_lag, len(data_norm) // 10)
        if lag_limit >= 10:
            lags = np.arange(1, lag_limit + 1)
            corr = np.array([np.mean(data_norm[:-lag] * data_norm[lag:]) for lag in lags])
            out["autocorr"].extend(corr.tolist())

    return out
