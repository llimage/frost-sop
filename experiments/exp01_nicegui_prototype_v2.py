# Exp-1 v2: NiceGUI仪表盘原型 - 布局修复版
# 修复: 左右分栏失效、元素拥挤、文字过小
# 运行: python experiments/exp01_nicegui_prototype_v2.py
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
    with open("experiments/results/exp01_metrics_v2.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

# ========== 暗色主题 ==========
ui.dark_mode().enable()

# ========== 模拟数据 ==========
agent_status = {
    "main": {"name": "主Agent", "status": "running", "progress": 80, "cost": 12.50, "action": "审查代码...", "icon": "🤖", "color": "#4F46E5"},
    "audit": {"name": "审计Agent", "status": "idle", "progress": 0, "cost": 3.20, "action": "等待任务", "icon": "🔍", "color": "#DC2626"},
    "dev": {"name": "开发Agent", "status": "waiting", "progress": 0, "cost": 8.30, "action": "等待审查结果", "icon": "💻", "color": "#059669"},
}

status_colors = {
    "idle": "#6B7280", "running": "#22C55E", 
    "waiting": "#F59E0B", "error": "#EF4444", "paused": "#06B6D4"
}
status_texts = {
    "idle": "空闲", "running": "运行中", 
    "waiting": "等待中", "error": "错误", "paused": "已暂停"
}

logs = [
    "14:32 [主Agent] 开始执行: 界面重构专项",
    "14:33 [开发Agent] 生成代码: src/ui/dashboard.py",
    "14:35 [审计Agent] 审查完成: 2警告 1建议",
    "14:36 [开发Agent] 修复警告，重新提交",
    "14:38 [审计Agent] 二次审查通过",
]

# ========== 页面构建 ==========
try:
    # 外层容器: 全屏，flex列布局
    with ui.element('div').classes('w-full h-screen').style('background-color: #0f172a; display: flex; flex-direction: column; padding: 16px; box-sizing: border-box;'):
        
        # ===== 标题区 =====
        with ui.row().classes('w-full items-center justify-between').style('margin-bottom: 16px; flex-shrink: 0;'):
            ui.label("S-O-P V1.0-MVP 实验原型").classes('text-xl font-bold').style('color: #f8fafc;')
            with ui.row().classes('items-center gap-2'):
                ui.element('div').classes('w-3 h-3 rounded-full').style('background-color: #22C55E;')
                ui.label("运行中").style('color: #4ade80; font-size: 14px;')
        
        # ===== KPI卡片区 =====
        with ui.row().classes('w-full gap-4').style('margin-bottom: 16px; flex-shrink: 0;'):
            kpi_data = [
                ("今日任务", "0/0", "#f8fafc"),
                ("运行中Agent", "1", "#22C55E"),
                ("本月Token", "¥23.50/¥300", "#f8fafc"),
                ("下次回顾", "--", "#f8fafc"),
            ]
            for title, value, color in kpi_data:
                with ui.card().classes('flex-1').style('background-color: #1e293b; padding: 16px; border-radius: 8px; border: 1px solid #334155;'):
                    ui.label(title).style('color: #94a3b8; font-size: 13px; margin-bottom: 8px;')
                    ui.label(value).classes('text-2xl font-bold').style(f'color: {color};')
        
        # ===== 主内容区: 左右分栏 =====
        with ui.row().classes('w-full').style('flex-grow: 1; gap: 16px; min-height: 0;'):
            
            # === 左侧: 75% ===
            with ui.column().style('width: 75%; gap: 16px; min-height: 0; overflow-y: auto;'):
                
                # -- Agent网格 (3个卡片横向) --
                with ui.row().classes('w-full gap-4').style('flex-shrink: 0;'):
                    for agent_id, data in agent_status.items():
                        with ui.card().classes('flex-1').style('background-color: #1e293b; padding: 16px; border-radius: 8px; border: 1px solid #334155; min-width: 0;'):
                            # 头部: 图标 + 名称 + 状态灯
                            with ui.row().classes('items-center gap-2').style('margin-bottom: 12px;'):
                                ui.label(data["icon"]).style('font-size: 20px;')
                                ui.label(data["name"]).classes('font-bold').style('color: #f8fafc; font-size: 15px;')
                                ui.element('div').classes('w-3 h-3 rounded-full').style(f'background-color: {status_colors[data["status"]]}; margin-left: auto;')
                            
                            # 状态文本
                            ui.label(status_texts[data['status']]).style(f'color: {status_colors[data["status"]]}; font-size: 13px; margin-bottom: 12px;')
                            
                            # 进度条
                            with ui.row().classes('items-center gap-2').style('margin-bottom: 8px;'):
                                ui.label("进度:").style('color: #64748b; font-size: 12px; width: 36px;')
                                ui.linear_progress(value=data["progress"]/100).classes('flex-grow').style('height: 6px;')
                                ui.label(f"{data['progress']}%").style('color: #64748b; font-size: 12px; width: 32px; text-align: right;')
                            
                            # 成本 + 当前操作
                            ui.label(f"成本: ¥{data['cost']:.2f} | {data['action']}").style('color: #64748b; font-size: 12px;')
                
                # -- 日志面板 --
                with ui.card().classes('w-full').style('background-color: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #334155; flex-shrink: 0;'):
                    ui.label("📋 系统日志").classes('font-bold').style('color: #f8fafc; font-size: 15px; margin-bottom: 12px;')
                    log_container = ui.column().classes('w-full gap-1').style('max-height: 200px; overflow-y: auto;')
                    for log in logs:
                        ui.label(log).style('color: #94a3b8; font-size: 12px; font-family: monospace;')
                
                # -- 任务结果区 --
                with ui.card().classes('w-full').style('background-color: #1e293b; padding: 16px; border-radius: 8px; border: 1px solid #334155; flex-shrink: 0;'):
                    ui.label("📄 任务结果").classes('font-bold').style('color: #f8fafc; font-size: 15px; margin-bottom: 12px;')
                    with ui.column().classes('items-center justify-center w-full').style('padding: 32px 0;'):
                        ui.label("📋").style('font-size: 40px; color: #334155;')
                        ui.label("暂无执行结果").style('color: #64748b; font-size: 14px; margin-top: 8px;')
                        ui.label("在右侧CEO面板输入任务主题").style('color: #475569; font-size: 12px; margin-top: 4px;')
            
            # === 右侧: 25% CEO面板 ===
            with ui.column().style('width: 25%; gap: 16px; min-height: 0;'):
                with ui.card().classes('w-full h-full').style('background-color: #1e293b; padding: 20px; border-radius: 8px; border: 1px solid #334155; display: flex; flex-direction: column;'):
                    
                    # CEO信息
                    with ui.row().classes('items-center gap-3').style('margin-bottom: 20px; flex-shrink: 0;'):
                        ui.label("👤").style('font-size: 28px;')
                        with ui.column():
                            ui.label("老板").classes('font-bold').style('color: #f8fafc; font-size: 16px;')
                            ui.label("创始人 / CEO").style('color: #64748b; font-size: 12px;')
                    
                    ui.element('div').style('height: 1px; background-color: #334155; margin-bottom: 20px; flex-shrink: 0;')
                    
                    # 当前执行计划
                    ui.label("当前执行计划").style('color: #64748b; font-size: 13px; margin-bottom: 8px; flex-shrink: 0;')
                    ui.label("界面重构专项\n进行中").style('color: #f8fafc; font-size: 14px; line-height: 1.6; margin-bottom: 20px; flex-shrink: 0;')
                    
                    ui.element('div').style('height: 1px; background-color: #334155; margin-bottom: 20px; flex-shrink: 0;')
                    
                    # 输入区
                    with ui.column().classes('w-full gap-3').style('flex-shrink: 0;'):
                        input_field = ui.textarea(placeholder="输入指令或任务主题...").classes('w-full').style(
                            'background-color: #0f172a; color: #f8fafc; border: 1px solid #334155; '
                            'border-radius: 6px; padding: 12px; font-size: 14px; resize: none; height: 80px;'
                        )
                        
                        def on_send():
                            val = input_field.value or ""
                            if val.strip():
                                ui.notify(f"指令已发送: {val[:30]}...", type="positive", position="top")
                                logs.append(f"{time.strftime('%H:%M')} [老板] {val}")
                                input_field.set_value("")
                        
                        ui.button("📤 发送指令", on_click=on_send).classes('w-full').style(
                            'background-color: #e94560; color: white; padding: 10px; border-radius: 6px; '
                            'font-size: 14px; border: none; cursor: pointer;'
                        )
                    
                    # 快捷按钮
                    with ui.column().classes('w-full gap-2').style('margin-top: 16px; flex-shrink: 0;'):
                        ui.label("快捷操作").style('color: #64748b; font-size: 12px; margin-bottom: 4px;')
                        shortcuts = [
                            ("📊 进度如何?", "进度如何?"),
                            ("💰 成本正常吗?", "成本正常吗?"),
                            ("📝 查看日志", "查看日志"),
                        ]
                        for label, cmd in shortcuts:
                            ui.button(label, on_click=lambda c=cmd: ui.notify(f"发送: {c}", position="top")).classes('w-full').style(
                                'background-color: #0f172a; color: #94a3b8; padding: 8px; border-radius: 6px; '
                                'font-size: 12px; border: 1px solid #334155; cursor: pointer;'
                            )
    
    metrics["build_time"] = time.time() - metrics["start_time"]
    record_metric("status", "build_success_v2")
    
except Exception as e:
    metrics["errors"].append(str(e))
    record_metric("status", "build_failed_v2")
    raise

# ========== 启动服务器 ==========
print(f"[Exp-1 v2] UI构建时间: {metrics['build_time']:.3f}秒")
print(f"[Exp-1 v2] 请在浏览器打开: http://localhost:8501")
print(f"[Exp-1 v2] 按 Ctrl+C 停止服务器")

ui.run(title="S-O-P Prototype v2", port=8501, reload=False, show=False)
