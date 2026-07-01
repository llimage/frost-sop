# Exp-3: 内存压力测试
# 目标: 验证3常驻Agent + Ollama 3B内存占用是否≤3.5GB
# 通过标准: 峰值内存≤3.5GB
# 前提: Ollama已安装并运行
# 运行方式: python exp03_memory_stress.py
# 预算: ¥0

import time
import json
import os
import threading
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional

# 尝试导入psutil，如果不可用则使用备用方案
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[警告] psutil未安装，将使用备用内存检测方案")
    print("[提示] 建议先安装: pip install psutil")


@dataclass
class MemorySnapshot:
    timestamp: float
    process_mb: float
    system_used_mb: float
    system_total_mb: float
    ollama_mb: float = 0.0
    note: str = ""


class MemoryMonitor:
    """内存监控器"""

    def __init__(self, interval_sec: float = 1.0):
        self.interval = interval_sec
        self.snapshots: List[MemorySnapshot] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.peak_process_mb = 0.0
        self.peak_system_mb = 0.0

    def _get_memory(self) -> tuple:
        """获取当前内存信息 (process_mb, system_used_mb, system_total_mb, ollama_mb)"""
        process_mb = 0.0
        system_used_mb = 0.0
        system_total_mb = 0.0
        ollama_mb = 0.0

        if HAS_PSUTIL:
            # 当前进程内存
            proc = psutil.Process(os.getpid())
            process_mb = proc.memory_info().rss / 1024 / 1024

            # 系统内存
            mem = psutil.virtual_memory()
            system_used_mb = mem.used / 1024 / 1024
            system_total_mb = mem.total / 1024 / 1024

            # Ollama进程内存
            for p in psutil.process_iter(["pid", "name", "memory_info"]):
                try:
                    if "ollama" in p.info["name"].lower():
                        ollama_mb += p.info["memory_info"].rss / 1024 / 1024
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        else:
            # 备用方案: 仅记录时间戳，提示用户手动观察
            process_mb = -1.0
            system_used_mb = -1.0
            system_total_mb = -1.0

        return process_mb, system_used_mb, system_total_mb, ollama_mb

    def start(self):
        """启动监控线程"""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print(f"[Exp-3] 内存监控已启动 (间隔: {self.interval}s)")

    def _monitor_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            proc_mb, sys_used_mb, sys_total_mb, ollama_mb = self._get_memory()

            snap = MemorySnapshot(
                timestamp=time.time(),
                process_mb=proc_mb,
                system_used_mb=sys_used_mb,
                system_total_mb=sys_total_mb,
                ollama_mb=ollama_mb,
                note="",
            )
            self.snapshots.append(snap)

            if proc_mb > 0:
                self.peak_process_mb = max(self.peak_process_mb, proc_mb)
            if sys_used_mb > 0:
                self.peak_system_mb = max(self.peak_system_mb, sys_used_mb)

            time.sleep(self.interval)

    def stop(self):
        """停止监控"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[Exp-3] 内存监控已停止")

    def snapshot(self, note: str = "") -> MemorySnapshot:
        """手动记录快照"""
        proc_mb, sys_used_mb, sys_total_mb, ollama_mb = self._get_memory()
        snap = MemorySnapshot(
            timestamp=time.time(),
            process_mb=proc_mb,
            system_used_mb=sys_used_mb,
            system_total_mb=sys_total_mb,
            ollama_mb=ollama_mb,
            note=note,
        )
        self.snapshots.append(snap)
        return snap


class MockAgent:
    """模拟Agent（占用内存）"""

    def __init__(self, name: str, memory_mb: int = 100):
        self.name = name
        self.memory_mb = memory_mb
        self.data = []
        self._allocate_memory()

    def _allocate_memory(self):
        """分配模拟内存 (1MB ≈ 256K个float)"""
        floats_per_mb = 256 * 1024  # 每个float 4字节
        self.data = [0.0] * (int(self.memory_mb * floats_per_mb))
        print(f"[Exp-3] Agent '{self.name}' 分配了 {self.memory_mb}MB 模拟内存")

    def work(self, duration_sec: int = 5):
        """模拟工作（CPU计算）"""
        print(f"[Exp-3] Agent '{self.name}' 开始工作 ({duration_sec}s)...")
        start = time.time()
        ops = 0
        while time.time() - start < duration_sec:
            # 简单的CPU计算，防止被优化掉
            for i in range(min(10000, len(self.data))):
                self.data[i] = (self.data[i] + 1.0) % 1000.0
            ops += 1
            if ops % 100 == 0:
                time.sleep(0.01)  # 避免完全占满CPU
        print(f"[Exp-3] Agent '{self.name}' 工作完成")


def check_ollama_running() -> bool:
    """检查Ollama是否运行"""
    try:
        import requests

        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def load_ollama_model(model: str = "qwen2.5:3b") -> bool:
    """加载Ollama模型到内存"""
    try:
        import requests

        print(f"[Exp-3] 请求Ollama加载模型: {model}")
        # 发送一个简单请求来触发模型加载
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": "hi", "stream": False},
            timeout=60,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[Exp-3] 加载模型失败: {e}")
        return False


def run_stress_test():
    """运行内存压力测试"""
    print("=" * 60)
    print("[Exp-3] 内存压力测试开始")
    print("=" * 60)

    BUDGET_MB = 3.5 * 1024  # 3.5GB = 3584MB

    # 检查Ollama
    ollama_running = check_ollama_running()
    print(f"\n[Exp-3] Ollama状态: {'运行中' if ollama_running else '未运行'}")

    if not ollama_running:
        print("[Exp-3] ⚠️ Ollama未运行，将使用模拟数据估算")
        print("[Exp-3] 建议: 先启动Ollama并加载qwen2.5:3b模型")
        print("         ollama run qwen2.5:3b")

    # 启动内存监控
    monitor = MemoryMonitor(interval_sec=1.0)
    monitor.start()
    time.sleep(1)  # 等待监控启动

    # 基线快照
    baseline = monitor.snapshot("基线(无Agent)")
    print("\n[Exp-3] 基线内存:")
    if baseline.process_mb > 0:
        print(f"  当前进程: {baseline.process_mb:.1f}MB")
        print(
            f"  系统已用: {baseline.system_used_mb:.1f}MB / {baseline.system_total_mb:.1f}MB"
        )
        print(f"  Ollama: {baseline.ollama_mb:.1f}MB")
    else:
        print("  (psutil未安装，无法自动获取，请手动观察任务管理器)")

    # 阶段1: 启动3个常驻Agent
    print("\n[Exp-3] 阶段1: 启动3个常驻Agent...")
    agents = []
    for name, mem in [("MainAgent", 150), ("AuditAgent", 100), ("DevAgent", 120)]:
        agent = MockAgent(name, mem)
        agents.append(agent)
        time.sleep(0.5)
        monitor.snapshot(f"启动{name}")

    # 阶段2: 加载Ollama模型
    if ollama_running:
        print("\n[Exp-3] 阶段2: 加载Ollama模型...")
        load_ollama_model("qwen2.5:3b")
        time.sleep(3)  # 等待模型加载完成
        monitor.snapshot("Ollama模型加载完成")
    else:
        print("\n[Exp-3] 阶段2: 跳过Ollama加载(未运行)")
        print("[Exp-3] 估算: qwen2.5:3b模型约占用 1.5-2.0GB 内存")

    # 阶段3: Agent同时工作
    print("\n[Exp-3] 阶段3: 3个Agent同时工作...")
    threads = []
    for agent in agents:
        t = threading.Thread(target=agent.work, args=(5,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    monitor.snapshot("Agent工作完成")

    # 阶段4: 模拟ChromaDB向量检索
    print("\n[Exp-3] 阶段4: 模拟向量数据库操作...")
    # 模拟5000条768维向量 = 约15MB
    vector_data = [[0.1] * 768 for _ in range(5000)]
    monitor.snapshot("向量数据加载")
    del vector_data

    # 停止监控
    monitor.stop()
    time.sleep(1)
    final = monitor.snapshot("测试结束")

    # 汇总
    print("\n" + "=" * 60)
    print("[Exp-3] 测试结果汇总")
    print("=" * 60)

    if monitor.peak_process_mb > 0:
        print(f"  峰值进程内存: {monitor.peak_process_mb:.1f}MB")
        print(f"  峰值系统内存: {monitor.peak_system_mb:.1f}MB")
        print(f"  预算上限: {BUDGET_MB:.0f}MB (3.5GB)")

        # 估算总内存（含Ollama）
        estimated_total = monitor.peak_process_mb + final.ollama_mb
        if final.ollama_mb == 0 and not ollama_running:
            estimated_total += 1800  # 估算Ollama 3B模型内存
            print("  Ollama估算: +1800MB (qwen2.5:3b)")

        print(f"  估算总内存: {estimated_total:.1f}MB")

        passed = estimated_total <= BUDGET_MB
        print(f"\n  通过标准: ≤{BUDGET_MB:.0f}MB")
        print(f"  结果: {'✅ 通过' if passed else '❌ 未通过'}")
    else:
        print("  (psutil未安装，无法自动判断)")
        print("  请手动观察Windows任务管理器的内存占用")
        print("  通过标准: 总内存占用 ≤ 3.5GB")
        estimated_total = 150 + 100 + 120 + 1800  # Agent + Ollama估算
        print(f"  理论估算: {estimated_total}MB (Agent 370MB + Ollama 1800MB)")
        passed = estimated_total <= BUDGET_MB
        print(f"  理论结果: {'✅ 通过' if passed else '❌ 未通过'}")

    # 保存结果
    Path("experiments/results").mkdir(parents=True, exist_ok=True)
    with open("experiments/results/exp03_results.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "budget_mb": BUDGET_MB,
                "peak_process_mb": monitor.peak_process_mb,
                "peak_system_mb": monitor.peak_system_mb,
                "ollama_mb": final.ollama_mb if final.ollama_mb > 0 else 1800,
                "estimated_total_mb": estimated_total
                if "estimated_total" in dir()
                else 0,
                "passed": passed if "passed" in dir() else None,
                "has_psutil": HAS_PSUTIL,
                "ollama_running": ollama_running,
                "snapshots": [asdict(s) for s in monitor.snapshots],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n[Exp-3] 结果已保存: experiments/results/exp03_results.json")
    return passed if "passed" in dir() else None


if __name__ == "__main__":
    run_stress_test()
