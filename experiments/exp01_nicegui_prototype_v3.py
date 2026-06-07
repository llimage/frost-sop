# Exp-1 v3: NiceGUI仪表盘原型 - 陈杨布局风格
# 布局特征: KPI大卡片 + 预算条 + Agent网格 + 右侧CEO面板 + 底部日志
# 配色: 暗色主题(深蓝黑)
# 运行: python experiments/exp01_nicegui_prototype_v3.py
# 浏览器: http://localhost:8501

import time
import json
from pathlib import Path
from nicegui import ui, app

# ========== 实验指标记录 ==========
metrics = {"start_time": time.time(), "build_time": 0, "errors": []}

def record_metric(key, value):
    metrics[key] = value
    Path("experiments/results").mkdir(parents=True, exist_ok=True)
    with open("experiments/results/exp01_metrics_v3.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

# ========== 暗色主题 ==========
ui.dark_mode().enable()

# 颜色常量
BG_PAGE = "#0B1120"       # 页面背景(深蓝黑)
BG_CARD = "#151E32"       # 卡片背景
BG_CARD_HOVER = "#1A2744" # 卡片悬停
BORDER = "#1E293B"        # 边框
TEXT_PRIMARY = "#F1F5F9"  # 主文字(白)
TEXT_SECONDARY = "#94A3B8" # 次要文字(灰)
TEXT_MUTED = "#64748B"    # 弱化文字
ACCENT_BLUE = "#3B82F6"   # 强调蓝
STATUS_RUN = "#22C55E"    # 运行中-绿
STATUS_WAIT = "#F59E0B"   # 等待-黄
STATUS_IDLE = "#6B7280"   # 空闲-灰

# ========== 模拟数据 ==========
agents = [
    {"id": "main", "name": "主Agent", "role": "调度中枢", "status": "running", "progress": 80, "cost": 12.50, "action": "审查代码...", "icon": "🤖", "model": "本地"},
    {"id": "audit", "name": "审计Agent", "role": "封板裁决", "status": "idle", "progress": 0, "cost": 3.20, "action": "等待任务", "icon": "🔍", "model": "本地"},
    {"id": "dev", "name": "开发Agent", "role": "代码实现", "status": "waiting", "progress": 0, "cost": 8.30, "action": "等待审查结果", "icon": "💻", "model": "云端"},
]

status_colors = {"idle": STATUS_IDLE, "running": STATUS_RUN, "waiting": STATUS_WAIT, "error": "#EF4444"}
status_texts = {"idle": "空闲", "running": "运行中", "waiting": "等待中", "error": "错误"}

logs = [
    "14:32 [主Agent] 开始执行: 界面重构专项",
    "14:33 [开发Agent] 生成代码: src/ui/dashboard.py",
    "14:35 [审计Agent] 审查完成: 2警告 1建议",
    "14:36 [开发Agent] 修复警告，重新提交",
    "14:38 [审计Agent] 二次审查通过",
]

# ========== 页面构建 ==========
try:
    # 外层: 全屏flex列
    with ui.element('div').style(f'background-color: {BG_PAGE}; display: flex; flex-direction: column; height: 100vh; overflow: hidden;'):
        
        # ===== 顶部标题栏 =====
        with ui.row().classes('w-full items-center justify-between').style('padding: 16px 24px; flex-shrink: 0; border-bottom: 1px solid ' + BORDER + ';'):
            with ui.row().classes('items-center gap-3'):
                ui.label("◉").style(f'color: {ACCENT_BLUE}; font-size: 20px;')
                ui.label("Solo-Ops-Platform").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 18px;')
                with ui.row().classes('gap-4').style('margin-left: 32px;'):
                    for nav in ["仪表盘", "任务", "Agent", "成本", "设置"]:
                        ui.label(nav).style(f'color: {TEXT_SECONDARY if nav != "仪表盘" else TEXT_PRIMARY}; font-size: 14px; cursor: pointer;')
            with ui.row().classes('items-center gap-2'):
                ui.element('div').classes('w-2 h-2 rounded-full').style(f'background-color: {STATUS_RUN};')
                ui.label("运行中").style(f'color: {STATUS_RUN}; font-size: 13px;')
        
        # ===== 主内容区: 左右分栏 =====
        with ui.row().classes('w-full').style('flex-grow: 1; min-height: 0; overflow: hidden;'):
            
            # === 左侧: 75% 工作区 ===
            with ui.column().style(f'width: 75%; height: 100%; overflow-y: auto; padding: 20px 24px; gap: 20px; box-sizing: border-box;'):
                
                # -- 标题区 --
                with ui.column().style('gap: 4px; margin-bottom: 8px;'):
                    ui.label("公司仪表盘").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 22px;')
                    ui.label("心域探险项目 - 进行中").style(f'color: {TEXT_SECONDARY}; font-size: 14px;')
                
                # -- KPI大卡片 (4个横向) --
                with ui.row().classes('w-full gap-4').style('margin-bottom: 4px;'):
                    kpi_items = [
                        ("0", "/0 今日任务", "步骤"),
                        ("1", "agents 运行中", "Agent"),
                        ("¥23.50", "/¥300 本月Token", "已消耗"),
                        ("--", "下次回顾", ""),
                    ]
                    for big, small, unit in kpi_items:
                        with ui.card().classes('flex-1').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 20px;'):
                            with ui.row().classes('items-baseline gap-1'):
                                ui.label(big).classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 32px;')
                                ui.label(small).style(f'color: {TEXT_SECONDARY}; font-size: 13px;')
                            if unit:
                                ui.label(unit).style(f'color: {TEXT_MUTED}; font-size: 12px; margin-top: 4px;')
                
                # -- 预算消耗条 --
                with ui.card().classes('w-full').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 16px 20px;'):
                    with ui.row().classes('w-full items-center justify-between').style('margin-bottom: 10px;'):
                        ui.label("预算消耗").style(f'color: {TEXT_SECONDARY}; font-size: 14px; font-weight: 500;')
                        with ui.row().classes('items-center gap-3'):
                            ui.label("本地: ¥0").style(f'color: {TEXT_MUTED}; font-size: 12px;')
                            ui.label("DeepSeek: ¥12.50").style(f'color: {TEXT_MUTED}; font-size: 12px;')
                            ui.label("总计: ¥23.50 / ¥300").style(f'color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 500;')
                            ui.label("剩余: ¥276.50").style(f'color: {STATUS_RUN}; font-size: 12px;')
                    # 进度条
                    with ui.element('div').classes('w-full').style(f'height: 8px; background-color: {BG_PAGE}; border-radius: 4px; overflow: hidden;'):
                        ui.element('div').style(f'width: 7.8%; height: 100%; background-color: {ACCENT_BLUE}; border-radius: 4px;')
                    with ui.row().classes('w-full items-center justify-between').style('margin-top: 6px;'):
                        ui.label("7.8% 已使用").style(f'color: {TEXT_MUTED}; font-size: 12px;')
                        ui.label("80% 预警线").style(f'color: {STATUS_WAIT}; font-size: 12px;')
                
                # -- AI Agent 团队 (3个横向卡片) --
                with ui.column().classes('w-full').style('gap: 12px;'):
                    ui.label("AI Agent 团队").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 16px; margin-bottom: 4px;')
                    
                    with ui.row().classes('w-full gap-4'):
                        for agent in agents:
                            status_color = status_colors[agent["status"]]
                            with ui.card().classes('flex-1').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 16px; position: relative; overflow: hidden;'):
                                # 顶部状态条
                                ui.element('div').style(f'position: absolute; top: 0; left: 0; right: 0; height: 3px; background-color: {status_color};')
                                
                                with ui.row().classes('items-center gap-3').style('margin-bottom: 12px;'):
                                    ui.label(agent["icon"]).style('font-size: 28px;')
                                    with ui.column().style('gap: 2px;'):
                                        ui.label(agent["name"]).classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 15px;')
                                        ui.label(agent["role"]).style(f'color: {TEXT_MUTED}; font-size: 12px;')
                                    ui.element('div').classes('w-2 h-2 rounded-full').style(f'background-color: {status_color}; margin-left: auto;')
                                
                                ui.label(status_texts[agent["status"]]).style(f'color: {status_color}; font-size: 13px; font-weight: 500; margin-bottom: 10px;')
                                
                                # 进度条
                                with ui.element('div').classes('w-full').style(f'height: 6px; background-color: {BG_PAGE}; border-radius: 3px; overflow: hidden; margin-bottom: 10px;'):
                                    ui.element('div').style(f'width: {agent["progress"]}%; height: 100%; background-color: {status_color}; border-radius: 3px;')
                                
                                with ui.row().classes('items-center justify-between'):
                                    ui.label(f"¥{agent['cost']:.2f}").style(f'color: {TEXT_MUTED}; font-size: 12px;')
                                    ui.label(agent["action"]).style(f'color: {TEXT_SECONDARY}; font-size: 12px;')
                
                # -- 实时日志 --
                with ui.card().classes('w-full').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 16px 20px;'):
                    ui.label("📋 实时日志").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 15px; margin-bottom: 12px;')
                    log_container = ui.column().classes('w-full gap-2').style('max-height: 160px; overflow-y: auto;')
                    for log in logs:
                        ui.label(log).style(f'color: {TEXT_SECONDARY}; font-size: 13px; font-family: monospace;')
            
            # === 右侧: 25% CEO面板 ===
            with ui.column().style(f'width: 25%; height: 100%; overflow-y: auto; padding: 20px 24px 20px 0; gap: 16px; box-sizing: border-box; border-left: 1px solid {BORDER};'):
                
                # -- CEO Agent 信息 --
                with ui.card().classes('w-full').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 16px;'):
                    with ui.row().classes('items-center gap-3').style('margin-bottom: 8px;'):
                        ui.label("👤").style('font-size: 32px;')
                        with ui.column().style('gap: 2px;'):
                            ui.label("CEO Agent").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 15px;')
                            with ui.row().classes('items-center gap-2'):
                                ui.element('div').classes('w-2 h-2 rounded-full').style(f'background-color: {STATUS_RUN};')
                                ui.label("监控中").style(f'color: {STATUS_RUN}; font-size: 12px;')
                    ui.label("执行计划已启动。Tech Researcher 正在调研制造业案例，预计 8 分钟完成。如有调整请告知。").style(f'color: {TEXT_SECONDARY}; font-size: 13px; line-height: 1.6;')
                
                # -- 执行计划详情 --
                with ui.card().classes('w-full').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 16px;'):
                    ui.label("当前执行计划").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 14px; margin-bottom: 10px;')
                    with ui.column().classes('w-full gap-3'):
                        for step, done in [("1. 需求讨论", True), ("2. 设计评审", True), ("3. 代码实现", True), ("4. 测试验证", False), ("5. 审计封板", False)]:
                            color = STATUS_RUN if done else TEXT_MUTED
                            icon = "✓" if done else "○"
                            ui.label(f"{icon} {step}").style(f'color: {color}; font-size: 13px;')
                
                # -- 对话输入区 (固定在右侧底部) --
                with ui.card().classes('w-full').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 16px; margin-top: auto;'):
                    ui.label("和 CEO Agent 对话").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 14px; margin-bottom: 10px;')
                    
                    input_field = ui.textarea(placeholder="输入指令或任务主题...").classes('w-full').style(
                        f'background-color: {BG_PAGE}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; '
                        f'border-radius: 8px; padding: 10px; font-size: 13px; resize: none; height: 70px;'
                    )
                    
                    def on_send():
                        val = input_field.value or ""
                        if val.strip():
                            ui.notify(f"指令已发送: {val[:30]}...", type="positive", position="top")
                            logs.append(f"{time.strftime('%H:%M')} [老板] {val}")
                            input_field.set_value("")
                    
                    with ui.row().classes('w-full items-center justify-between').style('margin-top: 10px;'):
                        ui.label("").style('font-size: 12px;')  # spacer
                        ui.button("📤", on_click=on_send).style(
                            f'background-color: {ACCENT_BLUE}; color: white; width: 36px; height: 36px; '
                            f'border-radius: 8px; border: none; font-size: 16px; cursor: pointer;'
                        )
                    
                    # 快捷按钮
                    with ui.row().classes('w-full gap-2').style('margin-top: 10px; flex-wrap: wrap;'):
                        shortcuts = [
                            ("进度如何?", "📊"),
                            ("成本正常吗?", "💰"),
                            ("查看日志", "📝"),
                        ]
                        for label, icon in shortcuts:
                            ui.button(f"{icon} {label}", on_click=lambda c=label: ui.notify(f"发送: {c}", position="top")).style(
                                f'background-color: {BG_PAGE}; color: {TEXT_SECONDARY}; padding: 6px 10px; '
                                f'border-radius: 6px; font-size: 12px; border: 1px solid {BORDER}; cursor: pointer;'
                            )
    
    metrics["build_time"] = time.time() - metrics["start_time"]
    record_metric("status", "build_success_v3")
    
except Exception as e:
    metrics["errors"].append(str(e))
    record_metric("status", "build_failed_v3")
    raise

# ========== 启动服务器 ==========
print(f"[Exp-1 v3] UI构建时间: {metrics['build_time']:.3f}秒")
print(f"[Exp-1 v3] 请在浏览器打开: http://localhost:8501")
print(f"[Exp-1 v3] 按 Ctrl+C 停止服务器")

ui.run(title="S-O-P Prototype v3", port=8501, reload=False, show=False)
