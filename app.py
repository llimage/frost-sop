"""
app.py - Solo-Ops-Platform 入口（V3.0 NiceGUI版）
执行任务按钮已接入 FastAPI 后端，真实触发 SOP 流程。
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# ============================================================
# 检测是否在测试环境下运行
# ============================================================
_IS_TESTING = os.environ.get('PYTEST_CURRENT_TEST') is not None or \
              os.environ.get('FROST_TESTING') == '1'

API_BASE = "http://localhost:8000"

SOP_TEMPLATES = {
    "DEV-001": "新功能开发 (5阶段)",
    "DEV-002": "Bug修复 (4阶段)",
    "STR-001": "项目立项 (5阶段)",
    "STR-002": "自进化验证 (4阶段)",
    "MT-001":  "内容发布 (4阶段)",
    "OPS-001": "财务月结 (3阶段)",
    "OPS-006": "知识资产管理 (4阶段)",
}

def create_ui():
    """创建NiceGUI UI（仅在不测试时调用）"""
    from nicegui import ui
    
    # ============================================================
    # 全局状态
    # ============================================================
    state = {"is_running": False}
    
    # ============================================================
    # 步骤一：全局配置
    # ============================================================
    ui.dark_mode(True)
    
    ui.add_head_html('''
    <style>
        .nicegui-content { background-color: #0F172A !important; }
        body { background-color: #0F172A !important; }
        .q-card {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }
        .q-card__section { color: #F1F5F9 !important; }
        .text-caption { color: #64748B !important; }
        .text-h4 { color: #F1F5F9 !important; font-size: 2rem !important; font-weight: bold !important; }
        .text-h6 { color: #F1F5F9 !important; }
        .q-header { background-color: #1E293B !important; color: #F1F5F9 !important; border-bottom: 1px solid #334155 !important; }
        .q-tabs { background-color: #1E293B !important; }
        .q-tab--active { color: #F59E0B !important; }
        .q-tab { color: #CBD5E1 !important; }
        .q-log {
            background-color: #0F172A !important;
            color: #10B981 !important;
            font-family: 'Courier New', monospace !important;
        }
        .border-l-4 { border-left-width: 4px !important; }
        .border-yellow-500 { border-left-color: #F59E0B !important; }
        .border-blue-500 { border-left-color: #3B82F6 !important; }
        .border-green-500 { border-left-color: #10B981 !important; }
        .border-purple-500 { border-left-color: #8B5CF6 !important; }
    </style>
    ''')
    
    # ============================================================
    # 步骤二：顶部导航栏
    # ============================================================
    with ui.header(elevated=True).classes('bg-gray-900 text-white'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-2'):
                ui.label('🏰').classes('text-2xl')
                with ui.column().classes('gap-0'):
                    ui.label('S-O-P').classes('text-lg font-bold')
                    ui.label('一人公司AI指挥平台').classes('text-xs text-gray-500')
            with ui.row().classes('items-center gap-4'):
                with ui.badge(color='green').classes('px-3 py-1'):
                    ui.label('● 就绪').classes('text-xs')
                ui.label('V3.0').classes('text-xs text-gray-500')
    
    # ============================================================
    # 步骤三：页面路由
    # ============================================================
    with ui.tabs().classes('w-full bg-gray-800') as tabs:
        tab_home = ui.tab('🏠 指挥中心')
        tab_arsenal = ui.tab('🏛️ 兵器库')
        tab_health = ui.tab('📊 健康度')
        tab_tasks = ui.tab('📋 任务队列')
        tab_logs = ui.tab('📝 执行日志')
    
    with ui.tab_panels(tabs, value=tab_home).classes('w-full bg-gray-900'):
        
        # ============================================================
        # 页面1：指挥中心
        # ============================================================
        with ui.tab_panel(tab_home):
            # KPI卡片区
            ui.label('关键指标').classes('text-lg font-bold mt-4 mb-2')
            kpi_row = ui.row().classes('w-full gap-4')
            
            # 家族状态卡片区
            ui.label('家族状态').classes('text-lg font-bold mt-6 mb-2')
            with ui.row().classes('w-full gap-4'):
                with ui.card().classes('flex-1 border-l-4 border-yellow-500'):
                    with ui.card_section():
                        ui.label('君主').classes('text-caption')
                        ui.label('🟢 在线').classes('text-h6')
                        ui.label('gen=0').classes('text-caption')
                with ui.card().classes('flex-1 border-l-4 border-blue-500'):
                    with ui.card_section():
                        ui.label('祖辈').classes('text-caption')
                        ui.label('🟢 就绪').classes('text-h6')
                        ui.label('gen=0').classes('text-caption')
                with ui.card().classes('flex-1 border-l-4 border-green-500'):
                    with ui.card_section():
                        ui.label('军师').classes('text-caption')
                        ui.label('🟢 就绪').classes('text-h6')
                        ui.label('待调用').classes('text-caption')
                with ui.card().classes('flex-1 border-l-4 border-purple-500'):
                    with ui.card_section():
                        ui.label('长老').classes('text-caption')
                        ui.label('🟢 监控中').classes('text-h6')
                        ui.label('审计就绪').classes('text-caption')
            
            # ============================================================
            # 指挥面板（核心交互区）
            # ============================================================
            ui.label('💬 指挥面板').classes('text-lg font-bold mt-6 mb-2')
            
            # SOP 模板选择器
            with ui.row().classes('w-full gap-4 mb-2'):
                sop_select = ui.select(
                    label='选择 SOP 模板',
                    options=SOP_TEMPLATES,
                    value='DEV-001',
                ).classes('flex-1')
                
                real_llm_toggle = ui.switch(
                    '真实 LLM (DeepSeek)',
                    value=False,
                )
            
            # 任务输入框
            task_input = ui.textarea(
                label='输入任务描述',
                placeholder='用自然语言描述你想让AI完成的任务...',
            ).classes('w-full')
            
            # 快捷按钮 + 执行按钮
            with ui.row().classes('w-full gap-2 mt-2'):
                ui.button('🆕 新功能开发',
                         on_click=lambda: (task_input.set_value('给项目添加用户认证功能'), sop_select.set_value('DEV-001'))
                ).classes('flex-1')
                ui.button('🐛 Bug修复',
                         on_click=lambda: (task_input.set_value('修复登录页面的样式错乱问题'), sop_select.set_value('DEV-002'))
                ).classes('flex-1')
                ui.button('📋 项目立项',
                         on_click=lambda: (task_input.set_value('调研AI Agent记忆系统并立项'), sop_select.set_value('STR-001'))
                ).classes('flex-1')
                ui.button('📝 内容发布',
                         on_click=lambda: (task_input.set_value('撰写本周技术周报'), sop_select.set_value('MT-001'))
                ).classes('flex-1')
            
            # 执行按钮
            execute_btn = ui.button(
                '🚀 执行任务',
                color='amber',
                on_click=lambda: asyncio.create_task(_execute_task()),
            ).classes('w-full mt-2')
            
            # 实时日志区域（指挥中心内嵌）
            ui.label('执行日志').classes('text-lg font-bold mt-4 mb-2')
            home_log = ui.log(max_lines=200).classes('w-full h-64 text-green-400').style(
                'background-color: #0F172A; font-family: monospace; border: 1px solid #334155; border-radius: 6px;'
            )
            
            def _push_log(msg):
                ts = datetime.now().strftime('%H:%M:%S')
                home_log.push(f'[{ts}] {msg}')
            
            async def _execute_task():
                if state["is_running"]:
                    ui.notify('已有任务在执行中，请等待完成', type='warning')
                    return
                
                desc = task_input.value.strip()
                if not desc:
                    ui.notify('请输入任务描述', type='warning')
                    return
                
                state["is_running"] = True
                execute_btn.text = '⏳ 执行中...'
                execute_btn.disable()
                
                sop_id = sop_select.value
                use_real = real_llm_toggle.value
                sop_name = SOP_TEMPLATES.get(sop_id, sop_id)
                
                _push_log(f'=== 任务启动 ===')
                _push_log(f'  描述: {desc[:100]}')
                _push_log(f'  SOP: {sop_id} ({sop_name})')
                _push_log(f'  LLM: {"真实 DeepSeek API" if use_real else "Mock 模式"}')
                _push_log(f'  正在调用 FastAPI 后端...')
                
                try:
                    import requests
                    
                    def _call_api():
                        resp = requests.post(
                            f'{API_BASE}/api/tasks',
                            json={
                                'description': desc,
                                'sop_id': sop_id,
                                'project_id': 'default',
                                'use_real_llm': use_real,
                            },
                            timeout=300,
                        )
                        resp.raise_for_status()
                        return resp.json()
                    
                    result = await asyncio.to_thread(_call_api)
                    
                    status = result.get('status', 'unknown')
                    task_id = result.get('task_id', '?')
                    message = result.get('message', '')
                    stages = result.get('stages', [])
                    
                    _push_log(f'=== 执行完毕 ===')
                    _push_log(f'  任务ID: {task_id}')
                    _push_log(f'  状态: {status}')
                    _push_log(f'  消息: {message}')
                    _push_log(f'  阶段数: {len(stages)}')
                    
                    for s in stages:
                        sname = s.get('stage_name', '?')
                        sorder = s.get('stage_order', '?')
                        sstatus = s.get('status', '?')
                        soutput = s.get('output', '') or ''
                        _push_log(f'  阶段{sorder}: {sname} [{sstatus}]')
                        if soutput:
                            # 截取前 300 字符显示
                            preview = soutput[:300].replace('\n', ' ')
                            _push_log(f'    产出: {preview}')
                    
                    if status == 'completed':
                        ui.notify(f'任务完成: {message}', type='positive')
                    else:
                        ui.notify(f'任务失败: {message}', type='negative')
                    
                    # 刷新任务队列
                    await _refresh_tasks()
                    
                except requests.exceptions.ConnectionError:
                    _push_log('[ERROR] 无法连接 FastAPI 后端 (localhost:8000)')
                    _push_log('  请确认 FastAPI 服务已启动')
                    ui.notify('FastAPI 后端未启动，请先启动后端', type='negative')
                except requests.exceptions.Timeout:
                    _push_log('[ERROR] 请求超时 (300秒)')
                    ui.notify('请求超时，可能是 LLM 调用时间过长', type='negative')
                except Exception as e:
                    _push_log(f'[ERROR] {e}')
                    ui.notify(f'执行失败: {e}', type='negative')
                finally:
                    state["is_running"] = False
                    execute_btn.text = '🚀 执行任务'
                    execute_btn.enable()
            
            # 初始化时加载 KPI
            async def _load_kpi():
                try:
                    import requests
                    def _fetch():
                        r = requests.get(f'{API_BASE}/api/tasks?limit=100', timeout=10)
                        r.raise_for_status()
                        return r.json()
                    tasks = await asyncio.to_thread(_fetch)
                    
                    total = len(tasks)
                    completed = len([t for t in tasks if t.get('status') == 'completed'])
                    running = len([t for t in tasks if t.get('status') == 'running'])
                    failed = len([t for t in tasks if t.get('status') == 'failed'])
                    
                    kpi_row.clear()
                    with kpi_row:
                        with ui.card().classes('flex-1'):
                            with ui.card_section():
                                ui.label('总任务数').classes('text-caption')
                                ui.label(str(total)).classes('text-h4')
                        with ui.card().classes('flex-1'):
                            with ui.card_section():
                                ui.label('已完成').classes('text-caption')
                                ui.label(str(completed)).classes('text-h4')
                                ui.label(f'完成率 {completed*100//max(total,1)}%').classes('text-caption text-green-500')
                        with ui.card().classes('flex-1'):
                            with ui.card_section():
                                ui.label('运行中').classes('text-caption')
                                ui.label(str(running)).classes('text-h4')
                        with ui.card().classes('flex-1'):
                            with ui.card_section():
                                ui.label('失败').classes('text-caption')
                                ui.label(str(failed)).classes('text-h4')
                                if failed > 0:
                                    ui.label('需关注').classes('text-caption text-red-500')
                except Exception:
                    kpi_row.clear()
                    with kpi_row:
                        with ui.card().classes('flex-1'):
                            with ui.card_section():
                                ui.label('后端未连接').classes('text-caption')
                                ui.label('--').classes('text-h4')
                                ui.label('请启动 FastAPI').classes('text-caption text-yellow-500')
            
            # 页面加载后异步刷新 KPI
            ui.timer(0.5, lambda: asyncio.create_task(_load_kpi()), once=True)
        
        # ============================================================
        # 页面2：兵器库
        # ============================================================
        with ui.tab_panel(tab_arsenal):
            ui.label('🏛️ 兵器库').classes('text-lg font-bold mt-4 mb-2')
            
            with ui.row().classes('w-full gap-4'):
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('SOP 模板').classes('text-caption')
                        ui.label(str(len(SOP_TEMPLATES))).classes('text-h4')
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('技能基因').classes('text-caption')
                        ui.label('--').classes('text-h4')
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('宪法规则').classes('text-caption')
                        ui.label('--').classes('text-h4')
            
            ui.label('SOP 模板列表').classes('text-lg font-bold mt-4 mb-2')
            
            for sop_id, sop_name in SOP_TEMPLATES.items():
                with ui.expansion(f'{sop_id} - {sop_name}', icon='description').classes('w-full mb-2'):
                    with ui.card().classes('w-full'):
                        with ui.card_section():
                            ui.label(f'模板ID: {sop_id}').classes('text-caption')
                            ui.label(f'名称: {sop_name}').classes('text-caption')
                            ui.badge('已验证', color='green').classes('mt-2')
        
        # ============================================================
        # 页面3：健康度
        # ============================================================
        with ui.tab_panel(tab_health):
            ui.label('📊 家族健康度').classes('text-lg font-bold mt-4 mb-2')
            
            with ui.row().classes('w-full gap-4'):
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('财务健康').classes('text-caption')
                        ui.label('85%').classes('text-h4')
                        ui.label('🟢 健康').classes('text-caption text-green-500')
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('运营健康').classes('text-caption')
                        ui.label('72%').classes('text-h4')
                        ui.label('🟡 关注').classes('text-caption text-yellow-500')
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('治理健康').classes('text-caption')
                        ui.label('90%').classes('text-h4')
                        ui.label('🟢 健康').classes('text-caption text-green-500')
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('客户健康').classes('text-caption')
                        ui.label('68%').classes('text-h4')
                        ui.label('🟡 关注').classes('text-caption text-yellow-500')
            
            ui.button('🔍 手动触发审计',
                     on_click=lambda: ui.notify('审计已启动，请稍候...')).classes('mt-4')
            
            ui.label('最近审计报告').classes('text-lg font-bold mt-6 mb-2')
            with ui.card().classes('w-full'):
                with ui.card_section():
                    ui.label('审计时间：2026-06-27 14:30').classes('text-caption')
                    ui.label('审计结果：家族健康度良好，未发现重大问题。').classes('mt-2')
        
        # ============================================================
        # 页面4：任务队列（从 API 加载真实数据）
        # ============================================================
        with ui.tab_panel(tab_tasks):
            ui.label('📋 任务队列').classes('text-lg font-bold mt-4 mb-2')
            
            tasks_container = ui.column().classes('w-full gap-2')
            refresh_btn = ui.button('🔄 刷新', on_click=lambda: asyncio.create_task(_refresh_tasks()))
            
            async def _refresh_tasks():
                try:
                    import requests
                    def _fetch():
                        r = requests.get(f'{API_BASE}/api/tasks?limit=20', timeout=10)
                        r.raise_for_status()
                        return r.json()
                    tasks_data = await asyncio.to_thread(_fetch)
                    
                    tasks_container.clear()
                    if not tasks_data:
                        with tasks_container:
                            ui.label('暂无任务记录').classes('text-caption text-center')
                        return
                    
                    with tasks_container:
                        for t in tasks_data:
                            status = t.get('status', '?')
                            title = t.get('title', '?')[:50]
                            task_id = t.get('id', '?')
                            created = t.get('created_at', '?')[:19]
                            summary = t.get('result_summary', '') or ''
                            
                            # 状态颜色
                            if status == 'completed':
                                color = 'green'
                                icon = '✅'
                            elif status == 'running':
                                color = 'blue'
                                icon = '🔄'
                            elif status == 'failed':
                                color = 'red'
                                icon = '❌'
                            else:
                                color = 'gray'
                                icon = '⏳'
                            
                            with ui.card().classes('w-full'):
                                with ui.card_section().classes('flex items-center gap-3'):
                                    ui.label(icon).classes('text-xl')
                                    with ui.column().classes('flex-1 gap-0'):
                                        ui.label(title).classes('text-sm font-bold')
                                        ui.label(f'ID: {task_id} | {created}').classes('text-caption')
                                        if summary:
                                            ui.label(summary[:80]).classes('text-caption text-gray-400')
                                    ui.badge(status, color=color)
                except Exception as e:
                    tasks_container.clear()
                    with tasks_container:
                        ui.label(f'加载失败: {e}').classes('text-caption text-red-500')
            
            # 页面加载时刷新
            ui.timer(0.5, lambda: asyncio.create_task(_refresh_tasks()), once=True)
        
        # ============================================================
        # 页面5：执行日志
        # ============================================================
        with ui.tab_panel(tab_logs):
            ui.label('📝 执行日志').classes('text-lg font-bold mt-4 mb-2')
            
            log = ui.log(max_lines=500).classes('w-full h-96 text-green-400').style(
                'background-color: #0F172A; font-family: monospace; border: 1px solid #334155; border-radius: 6px;'
            )
            
            log.push('[系统] S-O-P V3.0 驾驶舱已启动')
            log.push('[系统] FastAPI 后端: http://localhost:8000')
            log.push('[系统] 指挥中心 → 输入任务 → 选择 SOP → 点击执行')
            log.push('[系统] 日志将实时显示在指挥中心面板')
    
    # 启动应用
    ui.run(
        title='S-O-P | 一人公司AI指挥平台',
        favicon='🏰',
        port=8080,
        reload=False,
        show=False,
    )

# ============================================================
# 主程序入口
# ============================================================
if __name__ == '__main__' and not _IS_TESTING:
    create_ui()
