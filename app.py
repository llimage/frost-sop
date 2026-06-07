"""
app.py - Solo-Ops-Platform 入口（V0.10.0 仪表盘版）
"""
import streamlit as st

from frontend_v2.styles import inject_styles
from frontend_v2.state import init_state, get_current_page, set_current_page
from frontend_v2.pages.dashboard import render_dashboard
from frontend_v2.pages.history import render_history
from frontend_v2.pages.knowledge import render_knowledge
from frontend_v2.pages.settings import render_settings

st.set_page_config(
    page_title="Solo-Ops-Platform · 一人公司指挥平台",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed",  # 关键：收起侧栏
)

# 注入全局样式
inject_styles()

# 初始化状态
init_state()

# 顶部导航（返回当前页面）
from frontend_v2.components.navbar import render_navbar
current_page = render_navbar()

# 如果导航切换了页面，更新状态
if current_page != get_current_page():
    set_current_page(current_page)
    st.rerun()

# 根据当前页面渲染内容
if current_page == "dashboard":
    render_dashboard()
elif current_page == "history":
    render_history()
elif current_page == "knowledge":
    render_knowledge()
elif current_page == "settings":
    render_settings()
