"""
app.py - Solo-Ops-Platform 入口（V3.0 NiceGUI版）
技术栈迁移：Streamlit → NiceGUI
保留所有业务逻辑，只重写UI渲染层
"""

import os

# ============================================================
# 检测是否在测试环境下运行
# ============================================================
_IS_TESTING = os.environ.get('PYTEST_CURRENT_TEST') is not None or \
              os.environ.get('FROST_TESTING') == '1'

def create_ui():
    """创建NiceGUI UI（仅在不测试时调用）"""
    from nicegui import ui
    
    # ============================================================
    # 步骤一：全局配置
    # ============================================================
    ui.dark_mode(True)  # 深色主题
    
    # 自定义CSS
    ui.add_head_html('''
    <style>
        .nicegui-content {
            background-color: #0F172A !important;
        }
        body {
            background-color: #0F172A !important;
        }
        .q-card {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }
        .q-card__section {
            color: #F1F5F9 !important;
        }
        .text-caption {
            color: #64748B !important;
        }
        .text-h4 {
            color: #F1F5F9 !important;
            font-size: 2rem !important;
            font-weight: bold !important;
        }
        .text-h6 {
            color: #F1F5F9 !important;
        }
        .q-header {
            background-color: #1E293B !important;
            color: #F1F5F9 !important;
            border-bottom: 1px solid #334155 !important;
        }
        .q-tabs {
            background-color: #1E293B !important;
        }
        .q-tab--active {
            color: #F59E0B !important;
        }
        .q-tab {
            color: #CBD5E1 !important;
        }
        .q-log {
            background-color: #0F172A !important;
            color: #10B981 !important;
            font-family: 'Courier New', monospace !important;
        }
        .border-l-4 {
            border-left-width: 4px !important;
        }
        .border-yellow-500 {
            border-left-color: #F59E0B !important;
        }
        .border-blue-500 {
            border-left-color: #3B82F6 !important;
        }
        .border-green-500 {
            border-left-color: #10B981 !important;
        }
        .border-purple-500 {
            border-left-color: #8B5CF6 !important;
        }
    </style>
    ''')
    
    # ============================================================
    # 步骤二：顶部导航栏
    # ============================================================
    with ui.header(elevated=True).classes('bg-gray-900 text-white'):
        with ui.row().classes('w-full items-center justify-between'):
            # 左侧：Logo + 标题
            with ui.row().classes('items-center gap-2'):
                ui.label('🏰').classes('text-2xl')
                with ui.column().classes('gap-0'):
                    ui.label('S-O-P').classes('text-lg font-bold')
                    ui.label('一人公司AI指挥平台').classes('text-xs text-gray-500')
            
            # 右侧：状态灯 + 版本号
            with ui.row().classes('items-center gap-4'):
                with ui.badge(color='green').classes('px-3 py-1'):
                    ui.label('● 就绪').classes('text-xs')
                ui.label('V3.0').classes('text-xs text-gray-500')
    
    # ============================================================
    # 步骤三：页面路由（使用标签页）
    # ============================================================
    with ui.tabs().classes('w-full bg-gray-800') as tabs:
        tab_home = ui.tab('🏠 指挥中心')
        tab_arsenal = ui.tab('🏛️ 兵器库')
        tab_health = ui.tab('📊 健康度')
        tab_tasks = ui.tab('📋 任务队列')
        tab_logs = ui.tab('📝 执行日志')
    
    # 创建标签页面板容器
    with ui.tab_panels(tabs, value=tab_home).classes('w-full bg-gray-900'):
        
        # ============================================================
        # 页面1：指挥中心
        # ============================================================
        with ui.tab_panel(tab_home):
            # KPI卡片区
            ui.label('关键指标').classes('text-lg font-bold mt-4 mb-2')
            with ui.row().classes('w-full gap-4'):
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('今日任务').classes('text-caption')
                        ui.label('3').classes('text-h4')
                        ui.label('↑ 1').classes('text-caption text-green-500')
                
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('运行中Agent').classes('text-caption')
                        ui.label('2').classes('text-h4')
                        ui.label('0').classes('text-caption')
                
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('本月Token').classes('text-caption')
                        ui.label('¥12.5').classes('text-h4')
                        ui.label('预算80%').classes('text-caption text-yellow-500')
                
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('下次回顾').classes('text-caption')
                        ui.label('3天后').classes('text-h4')
            
            # 家族状态卡片区
            ui.label('家族状态').classes('text-lg font-bold mt-6 mb-2')
            with ui.row().classes('w-full gap-4'):
                # 君主
                with ui.card().classes('flex-1 border-l-4 border-yellow-500'):
                    with ui.card_section():
                        ui.label('君主').classes('text-caption')
                        ui.label('🟢 在线').classes('text-h6')
                        ui.label('gen=0').classes('text-caption')
                
                # 祖辈
                with ui.card().classes('flex-1 border-l-4 border-blue-500'):
                    with ui.card_section():
                        ui.label('祖辈').classes('text-caption')
                        ui.label('🟢 就绪').classes('text-h6')
                        ui.label('gen=0').classes('text-caption')
                
                # 军师
                with ui.card().classes('flex-1 border-l-4 border-green-500'):
                    with ui.card_section():
                        ui.label('军师').classes('text-caption')
                        ui.label('🟢 就绪').classes('text-h6')
                        ui.label('待调用').classes('text-caption')
                
                # 长老
                with ui.card().classes('flex-1 border-l-4 border-purple-500'):
                    with ui.card_section():
                        ui.label('长老').classes('text-caption')
                        ui.label('🟢 监控中').classes('text-h6')
                        ui.label('审计就绪').classes('text-caption')
            
            # 指挥面板
            ui.label('💬 指挥面板').classes('text-lg font-bold mt-6 mb-2')
            
            # 任务输入框
            task_input = ui.textarea(label='输入任务描述', 
                                     placeholder='用自然语言描述你想让AI完成的任务...').classes('w-full')
            
            # 快捷按钮 + 执行按钮
            with ui.row().classes('w-full gap-2 mt-2'):
                ui.button('🆕 新功能开发', 
                         on_click=lambda: task_input.set_value('给项目添加用户认证功能')).classes('flex-1')
                ui.button('🐛 Bug修复', 
                         on_click=lambda: task_input.set_value('修复登录页面的样式错乱问题')).classes('flex-1')
                ui.button('📊 周期回顾', 
                         on_click=lambda: task_input.set_value('回顾本周的开发任务完成情况')).classes('flex-1')
                ui.button('🚀 执行任务', 
                         color='amber',
                         on_click=lambda: ui.notify(f'任务已提交：{task_input.value}')).classes('flex-1')
        
        # ============================================================
        # 页面2：兵器库
        # ============================================================
        with ui.tab_panel(tab_arsenal):
            ui.label('🏛️ 兵器库').classes('text-lg font-bold mt-4 mb-2')
            
            # 统计卡片
            with ui.row().classes('w-full gap-4'):
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('武器总数').classes('text-caption')
                        ui.label('17').classes('text-h4')
                
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('可配发').classes('text-caption')
                        ui.label('12').classes('text-h4')
                
                with ui.card().classes('flex-1'):
                    with ui.card_section():
                        ui.label('待验证').classes('text-caption')
                        ui.label('3').classes('text-h4')
            
            # 分类筛选
            weapon_category = ui.select(
                label='分类筛选', 
                options=['全部', '技能武器', 'SOP模板', '情报武器', '免疫规则', '平台绑定', '基因种子'],
                value='全部'
            ).classes('w-full mt-4')
            
            # 武器列表（示例数据）
            ui.label('武器列表').classes('text-lg font-bold mt-4 mb-2')
            
            weapons = [
                {'name': '需求分析Skill', 'type': '技能武器', 'score': 85, 'status': '精良'},
                {'name': '代码生成Skill', 'type': '技能武器', 'score': 92, 'status': '精良'},
                {'name': '测试验证Skill', 'type': '技能武器', 'score': 78, 'status': '良好'},
                {'name': 'DEV-001.yaml', 'type': 'SOP模板', 'score': 88, 'status': '精良'},
            ]
            
            for weapon in weapons:
                with ui.expansion(weapon['name'], icon='description').classes('w-full mb-2'):
                    with ui.card().classes('w-full'):
                        with ui.card_section():
                            ui.label(f"类型：{weapon['type']}").classes('text-caption')
                            ui.label(f"健康评分：{weapon['score']}").classes('text-caption')
                            
                            if weapon['score'] >= 80:
                                ui.badge('精良', color='green')
                            elif weapon['score'] >= 50:
                                ui.badge('良好', color='blue')
                            else:
                                ui.badge('待优化', color='red')
        
        # ============================================================
        # 页面3：健康度
        # ============================================================
        with ui.tab_panel(tab_health):
            ui.label('📊 家族健康度').classes('text-lg font-bold mt-4 mb-2')
            
            # 四维健康度卡片
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
            
            # 手动触发审计按钮
            ui.button('🔍 手动触发审计', 
                     on_click=lambda: ui.notify('审计已启动，请稍候...')).classes('mt-4')
            
            # 最近审计报告
            ui.label('最近审计报告').classes('text-lg font-bold mt-6 mb-2')
            with ui.card().classes('w-full'):
                with ui.card_section():
                    ui.label('审计时间：2026-06-27 14:30').classes('text-caption')
                    ui.label('审计结果：家族健康度良好，未发现重大问题。').classes('mt-2')
        
        # ============================================================
        # 页面4：任务队列
        # ============================================================
        with ui.tab_panel(tab_tasks):
            ui.label('📋 任务队列').classes('text-lg font-bold mt-4 mb-2')
            
            with ui.row().classes('w-full gap-4'):
                # 待执行
                with ui.column().classes('flex-1'):
                    ui.label('⏳ 待执行').classes('text-bold mb-2')
                    with ui.card().classes('w-full p-4'):
                        ui.label('暂无待执行任务').classes('text-caption text-center')
                
                # 执行中
                with ui.column().classes('flex-1'):
                    ui.label('🔄 执行中').classes('text-bold mb-2')
                    with ui.card().classes('w-full p-4'):
                        ui.label('暂无执行中任务').classes('text-caption text-center')
                
                # 已完成
                with ui.column().classes('flex-1'):
                    ui.label('✅ 已完成').classes('text-bold mb-2')
                    with ui.card().classes('w-full p-4'):
                        ui.label('暂无已完成任务').classes('text-caption text-center')
        
        # ============================================================
        # 页面5：执行日志
        # ============================================================
        with ui.tab_panel(tab_logs):
            ui.label('📝 执行日志').classes('text-lg font-bold mt-4 mb-2')
            
            # 深色终端风格日志
            log = ui.log(max_lines=100).classes('w-full h-96 text-green-400').style(
                'background-color: #0F172A; font-family: monospace; border: 1px solid #334155; border-radius: 6px;'
            )
            
            # 示例日志
            log.push('[12:00:01] 祖辈: 开始拆解任务...')
            log.push('[12:00:03] 祖辈: 拆解完成，分配1个父辈')
            log.push('[12:00:05] 父辈: 搜索SOP模板...')
            log.push('[12:00:08] 合规校验: ✅ 通过')
            log.push('[12:00:10] 父辈: 内化SOP，共5个阶段')
            log.push('[12:00:12] 孙辈: 执行「需求分析」')
    
    # 启动应用
    ui.run(
        title='S-O-P | 一人公司AI指挥平台',
        favicon='🏰',
        port=8080,
        reload=False,
        show=False  # 不自动打开浏览器
    )

# ============================================================
# 主程序入口
# ============================================================
if __name__ == '__main__' and not _IS_TESTING:
    create_ui()
