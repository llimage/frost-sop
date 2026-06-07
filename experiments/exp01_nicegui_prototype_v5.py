# Exp-1 v5: NiceGUI仪表盘原型 - 右侧聊天界面版
# 改动: 右侧=老板与主Agent对话记录+聊天框 | 日程放单独tab页(占位)
# 运行: python experiments/exp01_nicegui_prototype_v5.py
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
    with open("experiments/results/exp01_metrics_v5.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

# ========== 暗色主题 ==========
ui.dark_mode().enable()

# 颜色常量
BG_PAGE = "#0B1120"
BG_CARD = "#151E32"
BG_CHAT_ME = "#1E3A5F"    # 老板消息背景
BG_CHAT_AI = "#1E293B"   # Agent消息背景
BORDER = "#1E293B"
TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"
ACCENT_BLUE = "#3B82F6"
STATUS_RUN = "#22C55E"
STATUS_WAIT = "#F59E0B"
STATUS_IDLE = "#6B7280"

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
    "14:40 [主Agent] 阶段3完成，进入阶段4",
    "14:42 [开发Agent] 运行单元测试: 5/5通过",
    "14:45 [审计Agent] 最终审计通过，准备封板",
]

agent_comm = [
    {"from": "主Agent", "to": "开发Agent", "content": "请实现情绪日记模块，SQLite存储+NiceGUI表单", "time": "14:32"},
    {"from": "开发Agent", "to": "审计Agent", "content": "请审查 src/ui/dashboard.py 代码", "time": "14:33"},
    {"from": "审计Agent", "to": "开发Agent", "content": "审查结果: 1个SQL注入风险，建议用参数化查询", "time": "14:35"},
    {"from": "开发Agent", "to": "审计Agent", "content": "已修复，使用sqlite3参数化查询，请复查", "time": "14:36"},
    {"from": "审计Agent", "to": "开发Agent", "content": "复查通过，无安全问题", "time": "14:38"},
    {"from": "主Agent", "to": "老板", "content": "DEV-001 阶段3(代码实现)已完成，请确认进入阶段4?", "time": "14:40", "highlight": True},
]

# 老板与主Agent的对话记录
chat_history = [
    {"sender": "ai", "name": "主Agent", "content": "老板好！我是主Agent，负责协调所有Agent完成任务。当前正在执行'界面重构专项'，已进入阶段3/5。有什么可以帮您的？", "time": "14:00"},
    {"sender": "me", "name": "老板", "content": "进度如何了？", "time": "14:05"},
    {"sender": "ai", "name": "主Agent", "content": "当前进度: 阶段3(代码实现)进行中，开发Agent正在生成dashboard.py，预计10分钟完成。审计Agent已待命。", "time": "14:06"},
    {"sender": "me", "name": "老板", "content": "成本正常吗？", "time": "14:10"},
    {"sender": "ai", "name": "主Agent", "content": "本月已消耗 ¥23.50 / ¥300 (7.8%)，远低于预警线(80%)。本地模型为主，仅代码审查使用了少量DeepSeek API。", "time": "14:11"},
    {"sender": "ai", "name": "主Agent", "content": "DEV-001 阶段3(代码实现)已完成。开发Agent已生成情绪日记模块代码，审计Agent审查通过(0警告)。\n\n请确认进入阶段4(测试验证)或驳回修改？", "time": "14:40", "highlight": True},
]

# ========== 页面构建 ==========
try:
    with ui.element('div').style(f'background-color: {BG_PAGE}; display: flex; flex-direction: column; height: 100vh; overflow: hidden;'):
        
        # ===== 顶部标题栏 =====
        with ui.row().classes('w-full items-center justify-between').style('padding: 12px 24px; flex-shrink: 0; border-bottom: 1px solid ' + BORDER + ';'):
            with ui.row().classes('items-center gap-3'):
                ui.label("◉").style(f'color: {ACCENT_BLUE}; font-size: 20px;')
                ui.label("Solo-Ops-Platform").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 18px;')
                with ui.row().classes('gap-4').style('margin-left: 32px;'):
                    for nav in ["仪表盘", "任务", "Agent", "成本", "日程", "设置"]:
                        is_active = nav == "仪表盘"
                        ui.label(nav).style(f'color: {TEXT_PRIMARY if is_active else TEXT_SECONDARY}; font-size: 14px; cursor: pointer; {"font-weight: 500;" if is_active else ""}')
            with ui.row().classes('items-center gap-2'):
                ui.element('div').classes('w-2 h-2 rounded-full').style(f'background-color: {STATUS_RUN};')
                ui.label("运行中").style(f'color: {STATUS_RUN}; font-size: 13px;')
        
        # ===== 主内容区: 左右分栏 =====
        with ui.row().classes('w-full').style('flex-grow: 1; min-height: 0; overflow: hidden;'):
            
            # === 左侧: 75% 工作区 ===
            with ui.column().style(f'width: 75%; height: 100%; overflow-y: auto; padding: 16px 20px; gap: 14px; box-sizing: border-box;'):
                
                # -- KPI卡片 (4个等大小，紧凑) --
                with ui.row().classes('w-full gap-3').style('flex-shrink: 0;'):
                    kpi_items = [
                        ("0", "/0", "今日任务"),
                        ("1", "", "运行中Agent"),
                        ("¥23.50", "/¥300", "本月Token"),
                        ("--", "", "下次回顾"),
                    ]
                    for big, small, label in kpi_items:
                        with ui.card().classes('flex-1').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px; min-height: 70px; display: flex; flex-direction: column; justify-content: center;'):
                            with ui.row().classes('items-baseline gap-1'):
                                ui.label(big).classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 26px;')
                                ui.label(small).style(f'color: {TEXT_SECONDARY}; font-size: 13px;')
                            ui.label(label).style(f'color: {TEXT_MUTED}; font-size: 11px; margin-top: 2px;')
                
                # -- 预算消耗条 --
                with ui.card().classes('w-full').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 10px 14px; flex-shrink: 0;'):
                    with ui.row().classes('w-full items-center justify-between').style('margin-bottom: 6px;'):
                        ui.label("预算消耗").style(f'color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 500;')
                        with ui.row().classes('items-center gap-3'):
                            ui.label("本地: ¥0").style(f'color: {TEXT_MUTED}; font-size: 11px;')
                            ui.label("DeepSeek: ¥12.50").style(f'color: {TEXT_MUTED}; font-size: 11px;')
                            ui.label("总计: ¥23.50 / ¥300").style(f'color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500;')
                            ui.label("剩余: ¥276.50").style(f'color: {STATUS_RUN}; font-size: 11px;')
                    with ui.element('div').classes('w-full').style(f'height: 5px; background-color: {BG_PAGE}; border-radius: 3px; overflow: hidden;'):
                        ui.element('div').style(f'width: 7.8%; height: 100%; background-color: {ACCENT_BLUE}; border-radius: 3px;')
                    with ui.row().classes('w-full items-center justify-between').style('margin-top: 3px;'):
                        ui.label("7.8% 已使用").style(f'color: {TEXT_MUTED}; font-size: 11px;')
                        ui.label("80% 预警线").style(f'color: {STATUS_WAIT}; font-size: 11px;')
                
                # -- AI Agent 团队 (3个横向卡片) --
                with ui.row().classes('w-full gap-3').style('flex-shrink: 0;'):
                    for agent in agents:
                        status_color = status_colors[agent["status"]]
                        with ui.card().classes('flex-1').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px; position: relative; overflow: hidden;'):
                            ui.element('div').style(f'position: absolute; top: 0; left: 0; right: 0; height: 3px; background-color: {status_color};')
                            with ui.row().classes('items-center gap-2').style('margin-bottom: 6px;'):
                                ui.label(agent["icon"]).style('font-size: 22px;')
                                with ui.column().style('gap: 0px;'):
                                    ui.label(agent["name"]).classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 13px;')
                                    ui.label(agent["role"]).style(f'color: {TEXT_MUTED}; font-size: 11px;')
                                ui.element('div').classes('w-2 h-2 rounded-full').style(f'background-color: {status_color}; margin-left: auto;')
                            ui.label(status_texts[agent["status"]]).style(f'color: {status_color}; font-size: 11px; font-weight: 500; margin-bottom: 6px;')
                            with ui.element('div').classes('w-full').style(f'height: 4px; background-color: {BG_PAGE}; border-radius: 2px; overflow: hidden; margin-bottom: 6px;'):
                                ui.element('div').style(f'width: {agent["progress"]}%; height: 100%; background-color: {status_color}; border-radius: 2px;')
                            with ui.row().classes('items-center justify-between'):
                                ui.label(f"¥{agent['cost']:.2f}").style(f'color: {TEXT_MUTED}; font-size: 11px;')
                                ui.label(agent["action"]).style(f'color: {TEXT_SECONDARY}; font-size: 11px;')
                
                # -- 实时日志 (左侧整列) --
                with ui.card().classes('w-full').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px 14px; flex-shrink: 0;'):
                    ui.label("📋 实时日志").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 13px; margin-bottom: 8px;')
                    log_container = ui.column().classes('w-full gap-1').style('max-height: 160px; overflow-y: auto;')
                    for log in logs:
                        ui.label(log).style(f'color: {TEXT_SECONDARY}; font-size: 11px; font-family: monospace; line-height: 1.5;')
                
                # -- Agent协同讨论 --
                with ui.card().classes('w-full').style(f'background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px 14px; flex-shrink: 0;'):
                    with ui.row().classes('items-center gap-2').style('margin-bottom: 8px;'):
                        ui.label("🤝").style('font-size: 14px;')
                        ui.label("Agent 协同讨论").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 13px;')
                    comm_container = ui.column().classes('w-full gap-2').style('max-height: 150px; overflow-y: auto;')
                    for msg in agent_comm:
                        highlight = msg.get("highlight", False)
                        bg = "rgba(59, 130, 246, 0.08)" if highlight else "transparent"
                        border_left = f"2px solid {ACCENT_BLUE}" if highlight else "none"
                        with ui.row().classes('w-full items-start gap-2').style(f'padding: 6px 8px; border-radius: 4px; background-color: {bg}; border-left: {border_left};'):
                            ui.label(f"{msg['time']}").style(f'color: {TEXT_MUTED}; font-size: 10px; width: 36px; flex-shrink: 0;')
                            with ui.column().style('gap: 1px;'):
                                ui.label(f"[{msg['from']}] → [{msg['to']}]").style(f'color: {TEXT_SECONDARY}; font-size: 10px; font-weight: 500;')
                                ui.label(msg["content"]).style(f'color: {TEXT_PRIMARY if highlight else TEXT_SECONDARY}; font-size: 11px; line-height: 1.4;')
            
            # === 右侧: 25% 聊天面板 ===
            with ui.column().style(f'width: 25%; height: 100%; overflow: hidden; box-sizing: border-box; border-left: 1px solid {BORDER};'):
                
                # -- CEO Agent 头部信息 --
                with ui.row().classes('w-full items-center gap-3').style(f'padding: 14px 16px; flex-shrink: 0; border-bottom: 1px solid {BORDER};'):
                    ui.label("🤖").style('font-size: 28px;')
                    with ui.column().style('gap: 2px;'):
                        ui.label("CEO Agent").classes('font-bold').style(f'color: {TEXT_PRIMARY}; font-size: 14px;')
                        with ui.row().classes('items-center gap-2'):
                            ui.element('div').classes('w-2 h-2 rounded-full').style(f'background-color: {STATUS_RUN};')
                            ui.label("监控中").style(f'color: {STATUS_RUN}; font-size: 11px;')
                    ui.label("主Agent").style(f'color: {TEXT_MUTED}; font-size: 11px; margin-left: auto;')
                
                # -- 对话记录区 (可滚动) --
                chat_scroll = ui.column().classes('w-full').style(f'flex-grow: 1; overflow-y: auto; padding: 12px 14px; gap: 10px;')
                
                with chat_scroll:
                    for msg in chat_history:
                        is_me = msg["sender"] == "me"
                        bg_color = BG_CHAT_ME if is_me else BG_CHAT_AI
                        name_color = ACCENT_BLUE if is_me else TEXT_SECONDARY
                        align = "flex-end" if is_me else "flex-start"
                        
                        with ui.column().classes('w-full').style(f'align-items: {align};'):
                            with ui.column().style(f'background-color: {bg_color}; border-radius: 10px; padding: 10px 12px; max-width: 90%; gap: 4px;'):
                                with ui.row().classes('items-center gap-2'):
                                    ui.label(msg["name"]).style(f'color: {name_color}; font-size: 11px; font-weight: 500;')
                                    ui.label(msg["time"]).style(f'color: {TEXT_MUTED}; font-size: 10px;')
                                ui.label(msg["content"]).style(f'color: {TEXT_PRIMARY}; font-size: 12px; line-height: 1.5; white-space: pre-wrap;')
                                
                                # 如果是高亮消息(需要决策)，加按钮
                                if msg.get("highlight"):
                                    with ui.row().classes('gap-2').style('margin-top: 6px;'):
                                        ui.button("✓ 确认", on_click=lambda: ui.notify("已确认进入阶段4", type="positive", position="top")).style(
                                            f'background-color: {STATUS_RUN}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; border: none; cursor: pointer;'
                                        )
                                        ui.button("✗ 驳回", on_click=lambda: ui.notify("已驳回，返回修改", type="warning", position="top")).style(
                                            f'background-color: transparent; color: {TEXT_SECONDARY}; padding: 4px 10px; border-radius: 4px; font-size: 11px; border: 1px solid {BORDER}; cursor: pointer;'
                                        )
                
                # -- 输入区 (固定在底部) --
                with ui.column().classes('w-full').style(f'padding: 10px 14px; flex-shrink: 0; border-top: 1px solid {BORDER}; gap: 8px;'):
                    
                    input_field = ui.textarea(placeholder="和 CEO Agent 对话...").classes('w-full').style(
                        f'background-color: {BG_PAGE}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; '
                        f'border-radius: 8px; padding: 8px 10px; font-size: 12px; resize: none; height: 50px;'
                    )
                    
                    def on_send():
                        val = input_field.value or ""
                        if val.strip():
                            ui.notify(f"已发送: {val[:30]}...", type="positive", position="top")
                            input_field.set_value("")
                    
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label("").style('font-size: 10px;')  # spacer
                        ui.button("📤 发送", on_click=on_send).style(
                            f'background-color: {ACCENT_BLUE}; color: white; padding: 6px 14px; border-radius: 6px; font-size: 12px; border: none; cursor: pointer;'
                        )
                    
                    # 快捷按钮
                    with ui.row().classes('w-full gap-2').style('flex-wrap: wrap;'):
                        for label in ["进度如何?", "成本正常吗?", "查看日志"]:
                            ui.button(label, on_click=lambda c=label: ui.notify(f"发送: {c}", position="top")).style(
                                f'background-color: {BG_PAGE}; color: {TEXT_SECONDARY}; padding: 4px 8px; '
                                f'border-radius: 4px; font-size: 11px; border: 1px solid {BORDER}; cursor: pointer;'
                            )
    
    metrics["build_time"] = time.time() - metrics["start_time"]
    record_metric("status", "build_success_v5")
    
except Exception as e:
    metrics["errors"].append(str(e))
    record_metric("status", "build_failed_v5")
    raise

# ========== 启动服务器 ==========
print(f"[Exp-1 v5] UI构建时间: {metrics['build_time']:.3f}秒")
print(f"[Exp-1 v5] 请在浏览器打开: http://localhost:8501")
print(f"[Exp-1 v5] 按 Ctrl+C 停止服务器")

ui.run(title="S-O-P Prototype v5", port=8501, reload=False, show=False)
