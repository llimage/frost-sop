# S-O-P 验证实验说明

## 实验目标

验证3个关键假设（来自02.1系统架构设计）：

| 假设ID | 假设内容 | 验证实验 | 不成立回退 |
|--------|---------|---------|-----------|
| TA-001 | NiceGUI能做出满意仪表盘 | Exp-1 | 切换Flutter，重写前端 |
| TA-002 | Ollama 3B覆盖率≥60% | Exp-2 | 升级模型或增加预算 |
| TA-003 | 3Agent+Ollama内存≤3.5GB | Exp-3 | 减Agent或升级硬件 |

## 实验清单

### Exp-1: NiceGUI仪表盘原型
- **文件**: `exp01_nicegui_prototype.py`
- **运行**: `python experiments/exp01_nicegui_prototype.py`
- **验证**: 浏览器打开 http://localhost:8501
- **通过标准**: 页面加载<2秒，暗色主题可接受，组件不卡顿
- **预算**: ¥0

### Exp-2: Ollama 3B覆盖率测试
- **文件**: `exp02_ollama_benchmark.py`
- **前提**: Ollama已安装并运行，`qwen2.5:3b`已下载
- **运行**: `python experiments/exp02_ollama_benchmark.py`
- **通过标准**: 8种任务类型中≥5种可用本地完成（质量≥3/5）
- **预算**: ¥0-5（如需云端fallback）

### Exp-3: 内存压力测试
- **文件**: `exp03_memory_stress.py`
- **前提**: Ollama已安装并运行（可选，未运行时用估算值）
- **运行**: `python experiments/exp03_memory_stress.py`
- **通过标准**: 峰值内存≤3.5GB
- **预算**: ¥0

## 前置准备

### 1. 安装Ollama（Windows）
```bash
# 下载安装: https://ollama.com/download/windows
# 安装后，在PowerShell/CMD中:
ollama --version
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

### 2. 安装Python依赖
```bash
# 在项目根目录
pip install nicegui psutil requests
```

### 3. 启动Ollama服务
```bash
ollama serve
```

## 执行顺序

建议按顺序执行：
1. **先跑Exp-1**（不依赖Ollama，验证前端可行性）
2. **安装Ollama后跑Exp-2**（验证AI能力）
3. **最后跑Exp-3**（验证内存，需要Exp-2的Ollama环境）

## 结果查看

每个实验会自动保存结果到 `experiments/results/`：
- `exp01_metrics.json` —— NiceGUI构建时间和状态
- `exp02_results.json` —— Ollama 8任务测试结果
- `exp03_results.json` —— 内存压力测试数据

## 总预算控制

3个实验总预算：**¥100以内**
- Exp-1: ¥0
- Exp-2: ¥0-5（仅当3B明显不行时需要fallback到云端验证）
- Exp-3: ¥0
