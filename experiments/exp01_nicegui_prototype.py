# Exp-1: NiceGUI 仪表盘原型验证
# 目标: 验证NiceGUI能否构建满意的单页仪表盘
# 通过标准: 页面加载<2秒, 暗色主题可接受, 组件不卡顿
# 运行方式: python exp01_nicegui_prototype.py
# 然后在浏览器打开 http://localhost:8501

import time
import json
from pathlib import Path
from nicegui import ui

# ========== 实验指标记录 ==========
metrics = {"start_time": time.time(), "build_time": 0, "errors": []}


def record_metric(key, value):
    metrics[key] = value
    Path("experiments/results").mkdir(parents=True, exist_ok=True)
    with open("experiments/results/exp01_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)


# ========== 暗色主题 ==========
ui.dark_mode().enable()

# ========== 模拟数据 ==========
agent_status = {
    "agent_main": {
        "status": "running",
        "progress": 80,
        "cost": 12.50,
        "action": "审查代码...",
        "icon": "🤖",
    },
    "agent_audit": {
        "status": "idle",
        "progress": 0,
        "cost": 3.20,
        "action": "等待任务",
        "icon": "🔍",
    },
    "agent_dev": {
        "status": "waiting",
        "progress": 0,
        "cost": 8.30,
        "action": "等待审查结果",
        "icon": "💻",
    },
}

status_colors = {
    "idle": "#6c757d",
    "running": "#28a745",
    "waiting": "#ffc107",
    "error": "#dc3545",
    "paused": "#17a2b8",
}
status_texts = {
    "idle": "空闲",
    "running": "运行中",
    "waiting": "等待中",
    "error": "错误",
    "paused": "已暂停",
}

logs = [
    "14:32 [Agent_Main] 开始执行: 界面重构专项",
    "14:33 [Agent_Dev] 生成代码: src/ui/dashboard.py",
    "14:35 [Agent_Audit] 审查完成: 2警告 1建议",
    "14:36 [Agent_Dev] 修复警告，重新提交",
    "14:38 [Agent_Audit] 二次审查通过",
]

# ========== 页面构建 ==========
try:
    with ui.column().classes("w-full h-screen bg-gray-900 text-white p-4 gap-4"):
        # 标题区
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("S-O-P V1.0-MVP 实验原型").classes("text-xl font-bold")
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("w-3 h-3 rounded-full bg-green-500")
                ui.label("运行中").classes("text-green-400")

        # KPI卡片区
        with ui.row().classes("w-full gap-4"):
            kpi_data = [
                ("今日任务", "0/0", "white"),
                ("运行中Agent", "1", "#28a745"),
                ("本月Token", "¥23.50/¥300", "white"),
                ("下次回顾", "--", "white"),
            ]
            for title, value, color in kpi_data:
                with ui.card().classes(
                    "bg-gray-800 p-4 flex-1 rounded-lg border border-gray-700"
                ):
                    ui.label(title).classes("text-gray-400 text-sm")
                    ui.label(value).classes("text-2xl font-bold mt-2").style(
                        f"color: {color};"
                    )

        # 主内容区: 左侧75% + 右侧25%
        with ui.row().classes("w-full flex-grow gap-4"):
            # 左侧
            with ui.column().classes("w-3/4 gap-4"):
                # Agent网格 (3个卡片)
                with ui.row().classes("w-full gap-4"):
                    for agent_id, data in agent_status.items():
                        with ui.card().classes(
                            "bg-gray-800 p-4 flex-1 rounded-lg border border-gray-700"
                        ):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(data["icon"]).classes("text-2xl")
                                ui.label(f"Agent_{agent_id}").classes("font-bold")
                                ui.element("div").classes("w-3 h-3 rounded-full").style(
                                    f"background-color: {status_colors[data['status']]};"
                                )
                            ui.label(status_texts[data["status"]]).classes(
                                "text-gray-400 text-sm mt-2"
                            )
                            with ui.row().classes("items-center gap-2 mt-2"):
                                ui.label("进度:").classes("text-xs text-gray-500")
                                ui.linear_progress(
                                    value=data["progress"] / 100
                                ).classes("flex-grow")
                                ui.label(f"{data['progress']}%").classes(
                                    "text-xs text-gray-500 w-10 text-right"
                                )
                            ui.label(
                                f"成本: ¥{data['cost']:.2f} | {data['action']}"
                            ).classes("text-gray-500 text-xs mt-2")

                # 日志面板
                with ui.card().classes(
                    "bg-gray-900 p-4 rounded-lg border border-gray-700"
                ):
                    ui.label("📋 系统日志").classes("font-bold mb-2")
                    log_container = ui.column().classes("w-full gap-1")
                    for log in logs:
                        ui.label(log).classes("text-xs font-mono text-gray-400")

                # 任务结果区
                with ui.card().classes(
                    "bg-gray-800 p-4 rounded-lg border border-gray-700 min-h-32"
                ):
                    ui.label("📄 任务结果").classes("font-bold mb-2")
                    with ui.column().classes("items-center justify-center w-full h-32"):
                        ui.icon("📋").classes("text-4xl text-gray-600")
                        ui.label("暂无执行结果").classes("text-gray-500 mt-2")
                        ui.label("在右侧CEO面板输入任务主题").classes(
                            "text-gray-600 text-xs"
                        )

            # 右侧: CEO面板
            with ui.column().classes("w-1/4"):
                with ui.card().classes(
                    "bg-gray-800 p-4 rounded-lg border border-gray-700 h-full"
                ):
                    with ui.row().classes("items-center gap-2 mb-4"):
                        ui.label("👤").classes("text-2xl")
                        with ui.column():
                            ui.label("老板").classes("font-bold")
                            ui.label("创始人/CEO").classes("text-xs text-gray-400")
                    ui.separator().classes("bg-gray-700")
                    ui.label("当前执行计划").classes("text-sm text-gray-400 mt-4")
                    ui.label("界面重构专项\n进行中").classes("text-sm mt-2")
                    ui.separator().classes("bg-gray-700 mt-4")

                    input_field = ui.input(placeholder="输入指令...").classes(
                        "w-full mt-4 bg-gray-700 text-white border border-gray-600 rounded p-2"
                    )

                    def on_send():
                        ui.notify(f"指令已发送: {input_field.value}", type="positive")
                        logs.append(
                            f"{time.strftime('%H:%M')} [用户] {input_field.value}"
                        )
                        input_field.set_value("")

                    ui.button("📤 发送指令", on_click=on_send).classes(
                        "w-full mt-2 bg-red-500 text-white py-2 rounded hover:bg-red-400"
                    )

                    ui.label("快捷操作").classes("text-xs text-gray-400 mt-4")
                    shortcuts = [
                        ("📊 进度如何?", "进度如何?"),
                        ("💰 成本正常吗?", "成本正常吗?"),
                        ("📝 查看日志", "查看日志"),
                    ]
                    for label, cmd in shortcuts:
                        ui.button(
                            label, on_click=lambda c=cmd: ui.notify(f"发送: {c}")
                        ).classes(
                            "w-full text-xs bg-gray-700 text-gray-400 py-1 rounded mt-1 hover:bg-gray-600"
                        )

    metrics["build_time"] = time.time() - metrics["start_time"]
    record_metric("status", "build_success")

except Exception as e:
    metrics["errors"].append(str(e))
    record_metric("status", "build_failed")
    raise

# ========== 启动服务器 ==========
print(f"[Exp-1] UI构建时间: {metrics['build_time']:.3f}秒")
print("[Exp-1] 请在浏览器打开: http://localhost:8501")
print("[Exp-1] 按 Ctrl+C 停止服务器")

ui.run(title="S-O-P Exp-1 Prototype", port=8501, reload=False, show=False)
