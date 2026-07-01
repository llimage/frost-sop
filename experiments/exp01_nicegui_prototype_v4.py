# Exp-1 v4: NiceGUI仪表盘原型 - 布局精修版
# 改动: 去掉公司仪表盘标题 | KPI卡片统一紧凑 | 日志放左侧整列 | 原日志位放Agent协同 | 右侧加日程
# 运行: python experiments/exp01_nicegui_prototype_v4.py
# 浏览器: http://localhost:8501

import time
import json
from pathlib import Path
from nicegui import ui

# ========== 实验指标记录 ==========
metrics = {"start_time": time.time(), "build_time": 0, "errors": []}


def record_metric(key, value):
    metrics[key] = value
    Path("experiments/results").mkdir(parents=True, exist_ok=True)
    with open("experiments/results/exp01_metrics_v4.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)


# ========== 暗色主题 ==========
ui.dark_mode().enable()

# 颜色常量
BG_PAGE = "#0B1120"
BG_CARD = "#151E32"
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
    {
        "id": "main",
        "name": "主Agent",
        "role": "调度中枢",
        "status": "running",
        "progress": 80,
        "cost": 12.50,
        "action": "审查代码...",
        "icon": "🤖",
        "model": "本地",
    },
    {
        "id": "audit",
        "name": "审计Agent",
        "role": "封板裁决",
        "status": "idle",
        "progress": 0,
        "cost": 3.20,
        "action": "等待任务",
        "icon": "🔍",
        "model": "本地",
    },
    {
        "id": "dev",
        "name": "开发Agent",
        "role": "代码实现",
        "status": "waiting",
        "progress": 0,
        "cost": 8.30,
        "action": "等待审查结果",
        "icon": "💻",
        "model": "云端",
    },
]

status_colors = {
    "idle": STATUS_IDLE,
    "running": STATUS_RUN,
    "waiting": STATUS_WAIT,
    "error": "#EF4444",
}
status_texts = {
    "idle": "空闲",
    "running": "运行中",
    "waiting": "等待中",
    "error": "错误",
}

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
    {
        "from": "主Agent",
        "to": "开发Agent",
        "content": "请实现情绪日记模块，SQLite存储+NiceGUI表单",
        "time": "14:32",
    },
    {
        "from": "开发Agent",
        "to": "审计Agent",
        "content": "请审查 src/ui/dashboard.py 代码",
        "time": "14:33",
    },
    {
        "from": "审计Agent",
        "to": "开发Agent",
        "content": "审查结果: 1个SQL注入风险，建议用参数化查询",
        "time": "14:35",
    },
    {
        "from": "开发Agent",
        "to": "审计Agent",
        "content": "已修复，使用sqlite3参数化查询，请复查",
        "time": "14:36",
    },
    {
        "from": "审计Agent",
        "to": "开发Agent",
        "content": "复查通过，无安全问题",
        "time": "14:38",
    },
    {
        "from": "主Agent",
        "to": "老板",
        "content": "DEV-001 阶段3(代码实现)已完成，请确认进入阶段4?",
        "time": "14:40",
        "highlight": True,
    },
]

schedule_items = [
    {"time": "今天 14:00", "title": "项目进度回顾", "type": "project"},
    {"time": "明天 10:00", "title": "代码评审会议", "type": "review"},
    {"time": "周五 16:00", "title": "月度成本复盘", "type": "cost"},
]

# ========== 页面构建 ==========
try:
    with ui.element("div").style(
        f"background-color: {BG_PAGE}; display: flex; flex-direction: column; height: 100vh; overflow: hidden;"
    ):
        # ===== 顶部标题栏 =====
        with (
            ui.row()
            .classes("w-full items-center justify-between")
            .style(
                "padding: 12px 24px; flex-shrink: 0; border-bottom: 1px solid "
                + BORDER
                + ";"
            )
        ):
            with ui.row().classes("items-center gap-3"):
                ui.label("◉").style(f"color: {ACCENT_BLUE}; font-size: 20px;")
                ui.label("Solo-Ops-Platform").classes("font-bold").style(
                    f"color: {TEXT_PRIMARY}; font-size: 18px;"
                )
                with ui.row().classes("gap-4").style("margin-left: 32px;"):
                    for nav in ["仪表盘", "任务", "Agent", "成本", "设置"]:
                        ui.label(nav).style(
                            f"color: {TEXT_SECONDARY if nav != '仪表盘' else TEXT_PRIMARY}; font-size: 14px; cursor: pointer;"
                        )
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("w-2 h-2 rounded-full").style(
                    f"background-color: {STATUS_RUN};"
                )
                ui.label("运行中").style(f"color: {STATUS_RUN}; font-size: 13px;")

        # ===== 主内容区: 左右分栏 =====
        with (
            ui.row()
            .classes("w-full")
            .style("flex-grow: 1; min-height: 0; overflow: hidden;")
        ):
            # === 左侧: 75% 工作区 ===
            with ui.column().style(
                "width: 75%; height: 100%; overflow-y: auto; padding: 16px 20px; gap: 16px; box-sizing: border-box;"
            ):
                # -- KPI卡片 (4个等大小，紧凑) --
                with ui.row().classes("w-full gap-3").style("flex-shrink: 0;"):
                    kpi_items = [
                        ("0", "/0", "今日任务"),
                        ("1", "", "运行中Agent"),
                        ("¥23.50", "/¥300", "本月Token"),
                        ("--", "", "下次回顾"),
                    ]
                    for big, small, label in kpi_items:
                        with (
                            ui.card()
                            .classes("flex-1")
                            .style(
                                f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 16px; min-height: 80px; display: flex; flex-direction: column; justify-content: center;"
                            )
                        ):
                            with ui.row().classes("items-baseline gap-1"):
                                ui.label(big).classes("font-bold").style(
                                    f"color: {TEXT_PRIMARY}; font-size: 28px;"
                                )
                                ui.label(small).style(
                                    f"color: {TEXT_SECONDARY}; font-size: 14px;"
                                )
                            ui.label(label).style(
                                f"color: {TEXT_MUTED}; font-size: 12px; margin-top: 4px;"
                            )

                # -- 预算消耗条 --
                with (
                    ui.card()
                    .classes("w-full")
                    .style(
                        f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px 16px; flex-shrink: 0;"
                    )
                ):
                    with (
                        ui.row()
                        .classes("w-full items-center justify-between")
                        .style("margin-bottom: 8px;")
                    ):
                        ui.label("预算消耗").style(
                            f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 500;"
                        )
                        with ui.row().classes("items-center gap-3"):
                            ui.label("本地: ¥0").style(
                                f"color: {TEXT_MUTED}; font-size: 11px;"
                            )
                            ui.label("DeepSeek: ¥12.50").style(
                                f"color: {TEXT_MUTED}; font-size: 11px;"
                            )
                            ui.label("总计: ¥23.50 / ¥300").style(
                                f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500;"
                            )
                            ui.label("剩余: ¥276.50").style(
                                f"color: {STATUS_RUN}; font-size: 11px;"
                            )
                    with (
                        ui.element("div")
                        .classes("w-full")
                        .style(
                            f"height: 6px; background-color: {BG_PAGE}; border-radius: 3px; overflow: hidden;"
                        )
                    ):
                        ui.element("div").style(
                            f"width: 7.8%; height: 100%; background-color: {ACCENT_BLUE}; border-radius: 3px;"
                        )
                    with (
                        ui.row()
                        .classes("w-full items-center justify-between")
                        .style("margin-top: 4px;")
                    ):
                        ui.label("7.8% 已使用").style(
                            f"color: {TEXT_MUTED}; font-size: 11px;"
                        )
                        ui.label("80% 预警线").style(
                            f"color: {STATUS_WAIT}; font-size: 11px;"
                        )

                # -- AI Agent 团队 (3个横向卡片) --
                with ui.row().classes("w-full gap-3").style("flex-shrink: 0;"):
                    for agent in agents:
                        status_color = status_colors[agent["status"]]
                        with (
                            ui.card()
                            .classes("flex-1")
                            .style(
                                f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px; position: relative; overflow: hidden;"
                            )
                        ):
                            ui.element("div").style(
                                f"position: absolute; top: 0; left: 0; right: 0; height: 3px; background-color: {status_color};"
                            )
                            with (
                                ui.row()
                                .classes("items-center gap-2")
                                .style("margin-bottom: 8px;")
                            ):
                                ui.label(agent["icon"]).style("font-size: 24px;")
                                with ui.column().style("gap: 0px;"):
                                    ui.label(agent["name"]).classes("font-bold").style(
                                        f"color: {TEXT_PRIMARY}; font-size: 14px;"
                                    )
                                    ui.label(agent["role"]).style(
                                        f"color: {TEXT_MUTED}; font-size: 11px;"
                                    )
                                ui.element("div").classes("w-2 h-2 rounded-full").style(
                                    f"background-color: {status_color}; margin-left: auto;"
                                )
                            ui.label(status_texts[agent["status"]]).style(
                                f"color: {status_color}; font-size: 12px; font-weight: 500; margin-bottom: 8px;"
                            )
                            with (
                                ui.element("div")
                                .classes("w-full")
                                .style(
                                    f"height: 4px; background-color: {BG_PAGE}; border-radius: 2px; overflow: hidden; margin-bottom: 8px;"
                                )
                            ):
                                ui.element("div").style(
                                    f"width: {agent['progress']}%; height: 100%; background-color: {status_color}; border-radius: 2px;"
                                )
                            with ui.row().classes("items-center justify-between"):
                                ui.label(f"¥{agent['cost']:.2f}").style(
                                    f"color: {TEXT_MUTED}; font-size: 11px;"
                                )
                                ui.label(agent["action"]).style(
                                    f"color: {TEXT_SECONDARY}; font-size: 11px;"
                                )

                # -- 实时日志 (左侧整列，高度更大) --
                with (
                    ui.card()
                    .classes("w-full")
                    .style(
                        f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px 16px; flex-shrink: 0;"
                    )
                ):
                    ui.label("📋 实时日志").classes("font-bold").style(
                        f"color: {TEXT_PRIMARY}; font-size: 14px; margin-bottom: 10px;"
                    )
                    log_container = (
                        ui.column()
                        .classes("w-full gap-2")
                        .style("max-height: 200px; overflow-y: auto;")
                    )
                    for log in logs:
                        ui.label(log).style(
                            f"color: {TEXT_SECONDARY}; font-size: 12px; font-family: monospace; line-height: 1.5;"
                        )

                # -- Agent协同讨论 (原日志位置) --
                with (
                    ui.card()
                    .classes("w-full")
                    .style(
                        f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px 16px; flex-shrink: 0;"
                    )
                ):
                    with (
                        ui.row()
                        .classes("items-center gap-2")
                        .style("margin-bottom: 10px;")
                    ):
                        ui.label("🤝").style("font-size: 16px;")
                        ui.label("Agent 协同讨论").classes("font-bold").style(
                            f"color: {TEXT_PRIMARY}; font-size: 14px;"
                        )
                    comm_container = (
                        ui.column()
                        .classes("w-full gap-3")
                        .style("max-height: 180px; overflow-y: auto;")
                    )
                    for msg in agent_comm:
                        highlight = msg.get("highlight", False)
                        bg = "rgba(59, 130, 246, 0.1)" if highlight else "transparent"
                        border_left = (
                            f"3px solid {ACCENT_BLUE}"
                            if highlight
                            else f"1px solid {BORDER}"
                        )
                        with (
                            ui.row()
                            .classes("w-full items-start gap-2")
                            .style(
                                f"padding: 8px 10px; border-radius: 6px; background-color: {bg}; border-left: {border_left};"
                            )
                        ):
                            ui.label(f"{msg['time']}").style(
                                f"color: {TEXT_MUTED}; font-size: 11px; width: 40px; flex-shrink: 0;"
                            )
                            with ui.column().style("gap: 2px;"):
                                ui.label(f"[{msg['from']}] → [{msg['to']}]").style(
                                    f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: 500;"
                                )
                                ui.label(msg["content"]).style(
                                    f"color: {TEXT_PRIMARY if highlight else TEXT_SECONDARY}; font-size: 12px; line-height: 1.4;"
                                )

            # === 右侧: 25% CEO面板 ===
            with ui.column().style(
                f"width: 25%; height: 100%; overflow-y: auto; padding: 16px 20px 16px 0; gap: 14px; box-sizing: border-box; border-left: 1px solid {BORDER};"
            ):
                # -- CEO Agent 信息 --
                with (
                    ui.card()
                    .classes("w-full")
                    .style(
                        f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;"
                    )
                ):
                    with (
                        ui.row()
                        .classes("items-center gap-3")
                        .style("margin-bottom: 8px;")
                    ):
                        ui.label("👤").style("font-size: 28px;")
                        with ui.column().style("gap: 2px;"):
                            ui.label("CEO Agent").classes("font-bold").style(
                                f"color: {TEXT_PRIMARY}; font-size: 14px;"
                            )
                            with ui.row().classes("items-center gap-2"):
                                ui.element("div").classes("w-2 h-2 rounded-full").style(
                                    f"background-color: {STATUS_RUN};"
                                )
                                ui.label("监控中").style(
                                    f"color: {STATUS_RUN}; font-size: 11px;"
                                )
                    ui.label(
                        "执行计划已启动。开发Agent正在实现情绪日记模块，预计 15 分钟完成。如有调整请告知。"
                    ).style(
                        f"color: {TEXT_SECONDARY}; font-size: 12px; line-height: 1.5;"
                    )

                # -- 执行计划步骤 --
                with (
                    ui.card()
                    .classes("w-full")
                    .style(
                        f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;"
                    )
                ):
                    ui.label("执行计划").classes("font-bold").style(
                        f"color: {TEXT_PRIMARY}; font-size: 13px; margin-bottom: 10px;"
                    )
                    with ui.column().classes("w-full gap-2"):
                        for step, done in [
                            ("1. 需求讨论", True),
                            ("2. 设计评审", True),
                            ("3. 代码实现", True),
                            ("4. 测试验证", False),
                            ("5. 审计封板", False),
                        ]:
                            color = STATUS_RUN if done else TEXT_MUTED
                            icon = "✓" if done else "○"
                            ui.label(f"{icon} {step}").style(
                                f"color: {color}; font-size: 12px;"
                            )

                # -- 对话输入区 --
                with (
                    ui.card()
                    .classes("w-full")
                    .style(
                        f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;"
                    )
                ):
                    ui.label("和 CEO Agent 对话").classes("font-bold").style(
                        f"color: {TEXT_PRIMARY}; font-size: 13px; margin-bottom: 10px;"
                    )
                    input_field = (
                        ui.textarea(placeholder="输入指令或任务主题...")
                        .classes("w-full")
                        .style(
                            f"background-color: {BG_PAGE}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; "
                            f"border-radius: 6px; padding: 10px; font-size: 12px; resize: none; height: 60px;"
                        )
                    )

                    def on_send():
                        val = input_field.value or ""
                        if val.strip():
                            ui.notify(
                                f"指令已发送: {val[:30]}...",
                                type="positive",
                                position="top",
                            )
                            logs.append(f"{time.strftime('%H:%M')} [老板] {val}")
                            input_field.set_value("")

                    with (
                        ui.row()
                        .classes("w-full items-center justify-end")
                        .style("margin-top: 8px;")
                    ):
                        ui.button("📤", on_click=on_send).style(
                            f"background-color: {ACCENT_BLUE}; color: white; width: 32px; height: 32px; "
                            f"border-radius: 6px; border: none; font-size: 14px; cursor: pointer;"
                        )
                    with (
                        ui.row()
                        .classes("w-full gap-2")
                        .style("margin-top: 10px; flex-wrap: wrap;")
                    ):
                        for label in ["进度如何?", "成本正常吗?", "查看日志"]:
                            ui.button(
                                label,
                                on_click=lambda c=label: ui.notify(
                                    f"发送: {c}", position="top"
                                ),
                            ).style(
                                f"background-color: {BG_PAGE}; color: {TEXT_SECONDARY}; padding: 4px 8px; "
                                f"border-radius: 4px; font-size: 11px; border: 1px solid {BORDER}; cursor: pointer;"
                            )

                # -- 日程提醒 (填充右侧空白) --
                with (
                    ui.card()
                    .classes("w-full")
                    .style(
                        f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;"
                    )
                ):
                    with (
                        ui.row()
                        .classes("items-center gap-2")
                        .style("margin-bottom: 10px;")
                    ):
                        ui.label("📅").style("font-size: 16px;")
                        ui.label("日程提醒").classes("font-bold").style(
                            f"color: {TEXT_PRIMARY}; font-size: 13px;"
                        )
                    with ui.column().classes("w-full gap-3"):
                        for item in schedule_items:
                            type_color = {
                                "project": ACCENT_BLUE,
                                "review": STATUS_WAIT,
                                "cost": STATUS_RUN,
                            }
                            color = type_color.get(item["type"], TEXT_MUTED)
                            with ui.row().classes("items-start gap-2"):
                                ui.element("div").classes("w-1 h-1 rounded-full").style(
                                    f"background-color: {color}; margin-top: 6px; flex-shrink: 0;"
                                )
                                with ui.column().style("gap: 1px;"):
                                    ui.label(item["time"]).style(
                                        f"color: {TEXT_MUTED}; font-size: 11px;"
                                    )
                                    ui.label(item["title"]).style(
                                        f"color: {TEXT_SECONDARY}; font-size: 12px;"
                                    )

    metrics["build_time"] = time.time() - metrics["start_time"]
    record_metric("status", "build_success_v4")

except Exception as e:
    metrics["errors"].append(str(e))
    record_metric("status", "build_failed_v4")
    raise

# ========== 启动服务器 ==========
print(f"[Exp-1 v4] UI构建时间: {metrics['build_time']:.3f}秒")
print("[Exp-1 v4] 请在浏览器打开: http://localhost:8501")
print("[Exp-1 v4] 按 Ctrl+C 停止服务器")

ui.run(title="S-O-P Prototype v4", port=8501, reload=False, show=False)
