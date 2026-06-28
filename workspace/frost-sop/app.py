"""
FROST-SOP 家族AI指挥平台（F11 项目工作台）
PHILOSOPHY: 表现层与核心层完全解耦。
工作台是新界面+旧数据，不破坏现有架构。

版本: F11 (Project Workbench)
"""
import streamlit as st
import sys
import os
from datetime import datetime
import json

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stores.constitution import create_constitution_store
from stores.asset import create_asset_store
from agents.ancestor import create_ancestor
from agents.parent import create_parent
from agents.elder import create_elder, subscribe_elder_to_events
from core.store import Store
from core.store import AssetStore
from core.sop import SOP
from core.db import get_db
from core.cost import get_cost_tracker
from core.workbench import (
    ensure_workbench_migrations,
    get_project_defaults,
    get_project_by_mode,
    get_recommended_task,
    get_today_review,
    generate_daily_narrative,
    save_daily_review,
)

# ================================================================
# 页面配置 — 专业 SaaS 后台风格
# ================================================================
st.set_page_config(
    page_title="FROST-SOP | 家族AI指挥平台",
    page_icon="◈",
    layout="wide",
)

# ================================================================
# CSS 注入 — 专业 SaaS 后台视觉设计规范
# 色调：中性冷灰底色，蓝色强调，拒绝暖色和花哨渐变
# ================================================================


def inject_css():
    """注入全局CSS样式——专业SaaS后台风格"""
    st.markdown("""
    <style>
    /* === 全局底色 === */
    .stApp {
        background-color: #F4F6F8;
    }
    .main .block-container {
        padding: 0;
        max-width: 100%;
        background-color: #F4F6F8;
    }

    /* === 顶部导航栏 === */
    .saas-navbar {
        background: #1E293B;
        color: #E2E8F0;
        padding: 0 24px;
        height: 52px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid #334155;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .saas-navbar .brand {
        font-size: 15px;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: 0.5px;
        white-space: nowrap;
    }
    .saas-navbar .brand-sub {
        font-size: 11px;
        color: #94A3B8;
        font-weight: 400;
        margin-left: 8px;
    }
    .saas-navbar .nav-links {
        display: flex;
        gap: 4px;
        align-items: center;
    }
    .saas-navbar .nav-link {
        padding: 6px 16px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
        color: #CBD5E1;
        cursor: pointer;
        transition: all 0.15s;
    }
    .saas-navbar .nav-link:hover {
        background: #334155;
        color: #F8FAFC;
    }
    .saas-navbar .nav-link.active {
        background: #3B82F6;
        color: #FFFFFF;
    }
    .saas-navbar .nav-right {
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .saas-navbar .user-avatar {
        width: 32px;
        height: 32px;
        border-radius: 6px;
        background: #6366F1;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        font-weight: 700;
    }
    .saas-navbar .task-badge {
        font-size: 12px;
        color: #94A3B8;
        padding: 4px 10px;
        background: #0F172A;
        border-radius: 12px;
    }

    /* === 主内容区 === */
    .saas-content {
        padding: 20px 24px;
    }

    /* === KPI 卡片 === */
    .saas-stat-card {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 16px 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .saas-stat-card .stat-label {
        font-size: 11px;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .saas-stat-card .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: #0F172A;
        font-family: 'SF Mono', 'Consolas', monospace;
    }
    .saas-stat-card .stat-delta {
        font-size: 12px;
        color: #64748B;
        margin-top: 2px;
    }

    /* === 项目概览卡片 === */
    .saas-project-header {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 16px 20px;
        border: 1px solid #E2E8F0;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .saas-project-header .project-title {
        font-size: 17px;
        font-weight: 700;
        color: #0F172A;
    }
    .saas-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
    }
    .saas-badge-active {
        background: #DBEAFE;
        color: #1D4ED8;
    }
    .saas-badge-monitoring {
        background: #F0FDF4;
        color: #166534;
    }
    .saas-badge-running {
        background: #FEF3C7;
        color: #92400E;
    }
    .saas-badge-completed {
        background: #DCFCE7;
        color: #166534;
    }
    .saas-badge-waiting {
        background: #F1F5F9;
        color: #475569;
    }
    .saas-badge-standby {
        background: #F8FAFC;
        color: #94A3B8;
    }

    /* === 成本条 === */
    .saas-cost-bar {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 16px 20px;
        border: 1px solid #E2E8F0;
        margin-bottom: 16px;
    }
    .saas-cost-bar .cost-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .saas-progress {
        height: 14px;
        border-radius: 7px;
        background: #F1F5F9;
        overflow: hidden;
    }
    .saas-progress-fill {
        height: 14px;
        border-radius: 7px;
        background: #3B82F6;
        transition: width 0.4s ease;
    }
    .saas-progress-fill.warning {
        background: #F59E0B;
    }
    .saas-progress-fill.danger {
        background: #EF4444;
    }

    /* === AI 员工卡片 === */
    .saas-agent-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }
    @media (max-width: 900px) {
        .saas-agent-grid {
            grid-template-columns: 1fr;
        }
    }
    .saas-agent-card {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 14px 16px;
        border: 1px solid #E2E8F0;
        transition: box-shadow 0.15s;
    }
    .saas-agent-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .saas-agent-card .agent-name {
        font-size: 14px;
        font-weight: 600;
        color: #0F172A;
        margin-bottom: 4px;
    }
    .saas-agent-card .agent-role {
        font-size: 11px;
        color: #64748B;
        margin-bottom: 6px;
    }
    .saas-agent-card .agent-meta {
        font-size: 11px;
        color: #94A3B8;
    }
    .saas-status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    .saas-status-dot.running { background: #3B82F6; animation: pulse 1.5s infinite; }
    .saas-status-dot.completed { background: #22C55E; }
    .saas-status-dot.waiting { background: #F59E0B; }
    .saas-status-dot.standby { background: #94A3B8; }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }
    .saas-depends {
        font-size: 10px;
        color: #94A3B8;
        font-style: italic;
        margin-top: 2px;
    }

    /* === 侧边栏/对话面板 === */
    .saas-panel {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #E2E8F0;
        margin-bottom: 12px;
    }
    .saas-panel-title {
        font-size: 12px;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 10px;
    }
    .saas-quick-cmd {
        display: inline-block;
        padding: 4px 10px;
        margin: 2px 4px;
        border-radius: 4px;
        font-size: 11px;
        background: #F1F5F9;
        color: #475569;
        cursor: pointer;
        border: 1px solid #E2E8F0;
        transition: all 0.15s;
    }
    .saas-quick-cmd:hover {
        background: #3B82F6;
        color: #FFFFFF;
        border-color: #3B82F6;
    }

    /* === 日志窗口 === */
    .saas-log-window {
        background: #0F172A;
        border-radius: 8px;
        padding: 12px 16px;
        font-family: 'SF Mono', 'Consolas', 'Courier New', monospace;
        font-size: 12px;
        color: #E2E8F0;
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid #1E293B;
    }
    .saas-log-line {
        padding: 2px 0;
        border-bottom: 1px solid rgba(255,255,255,0.04);
    }
    .saas-log-time { color: #64748B; }
    .saas-log-info { color: #94A3B8; }
    .saas-log-success { color: #4ADE80; }
    .saas-log-warn { color: #FBBF24; }
    .saas-log-error { color: #F87171; }

    /* === 日终回顾 === */
    .daily-review-panel {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }

    /* === Streamlit 原生元素覆盖 === */
    div[data-testid="stHorizontalBlock"] {
        gap: 12px;
    }
    .stButton > button {
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #3B82F6 !important;
    }
    div[data-testid="stMetric"] {
        background: transparent;
        border-radius: 0;
        padding: 0;
        border: none;
        box-shadow: none;
    }
    section[data-testid="stSidebar"] {
        background-color: #F8FAFC;
    }
    section[data-testid="stSidebar"] .stButton > button {
        text-align: left;
        justify-content: flex-start;
        background: transparent;
        border: none;
        color: #475569;
        font-weight: 500;
        padding: 6px 12px;
        border-radius: 6px;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: #E2E8F0;
        color: #0F172A;
    }

    /* === 移动端适配 === */
    @media (max-width: 768px) {
        .saas-content { padding: 12px; }
        .saas-navbar { padding: 0 12px; height: 44px; }
        .saas-navbar .nav-link { padding: 4px 10px; font-size: 12px; }
        .saas-navbar .brand { font-size: 13px; }
        .saas-agent-grid { grid-template-columns: 1fr; }
    }
    </style>
    """, unsafe_allow_html=True)


# ================================================================
# 移动端检测
# ================================================================
def is_mobile():
    """检测是否为移动端访问"""
    # Streamlit 没有直接的用户代理检测，通过查询参数模拟
    return st.query_params.get("mobile", "") == "1"


# ================================================================
# 会话状态初始化
# ================================================================
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.ancestor = None
    st.session_state.constitution_store = None
    st.session_state.asset_store = None
    st.session_state.logs = []
    st.session_state.task_count = 0
    st.session_state.total_tokens = 0
    st.session_state.tasks = {}
    st.session_state.task_id_counter = 0
    st.session_state.cost_log = []
    st.session_state.saved_config = None
    st.session_state.config_loaded = False

    # F11 工作台状态
    st.session_state.wb_mode = "dev"  # dev / create / client
    st.session_state.wb_view = "dashboard"  # dashboard / project_detail / daily_review
    st.session_state.wb_active_project = None
    st.session_state.wb_daily_review_dismissed = False
    st.session_state.wb_alt_index = 0  # 备选任务索引
    st.session_state.wb_nav = "dashboard"  # 导航激活项
    
    # V4.0 P1: 驾驶舱动态面板
    st.session_state.panel_templates = {}  # 面板模板库
    st.session_state.dynamic_panels = []  # 当前动态面板列表
    st.session_state.suggested_panels = []  # 军师建议的面板配置


def add_log(message: str, level: str = "info"):
    """追加日志到会话状态"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append({
        "time": timestamp,
        "message": message,
        "level": level,
    })


# F8 决策对话框渲染函数
def render_decision_dialog():
    """渲染决策对话框"""
    from core.decision_manager import get_decision_manager
    from core.notifier import check_decision_timeout, send_timeout_notification

    try:
        decision_manager = get_decision_manager()
        pending = decision_manager.get_pending_decision()
        if pending is None:
            return

        decision_id = pending["id"]
        question = pending["question"]
        options = json.loads(pending["options_json"]) if isinstance(
            pending["options_json"], str) else pending["options_json"]
        created_at = pending.get("created_at")

        # —— 清理残留决策：超过 24 小时的 pending 决策自动取消 ——
        if created_at:
            try:
                from datetime import timedelta
                created_dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                if now - created_dt > timedelta(hours=24):
                    try:
                        db = get_db()
                        cursor = db.get_connection().cursor()
                        cursor.execute(
                            "UPDATE decision_points SET status='auto_cancelled', "
                            "user_note='上次会话残留决策，已自动关闭', responded_at=? WHERE id=?",
                            (now.strftime("%Y-%m-%d %H:%M:%S"), str(decision_id))
                        )
                        db.get_connection().commit()
                    except Exception:
                        pass
                    add_log(f"🔄 自动清理残留决策: {decision_id} (创建于 {created_at})", level="info")
                    return  # 不弹出对话框
            except Exception:
                pass  # 解析失败就正常弹出

        # —— 英→中 fallback 映射 ——
        LABEL_MAP = {
            "confirm": "确认", "reject": "驳回", "modify": "修改",
            "approve": "批准", "deny": "拒绝", "cancel": "取消",
            "accept": "接受", "decline": "谢绝", "skip": "跳过",
            "yes": "是", "no": "否",
        }
        options_display = [LABEL_MAP.get(o.lower(), o) for o in options]

        is_timeout = False
        if created_at:
            is_timeout = check_decision_timeout(created_at, timeout_seconds=3600)

        timeout_notified_key = f"timeout_notified_{decision_id}"
        if is_timeout and not st.session_state.get(timeout_notified_key, False):
            try:
                send_timeout_notification(
                    decision_id=decision_id,
                    task_id=pending.get("task_id", "unknown"),
                    stage_id=pending.get("stage_id", "unknown")
                )
                st.session_state[timeout_notified_key] = True
                add_log(f"🔔 决策 {decision_id} 超时通知已发送", level="warning")
            except Exception as e:
                add_log(f"⚠️ 发送超时通知失败: {e}", level="warning")

        @st.dialog("⚠️ 决策点：任务需要您的确认")
        def show_dialog():
            if is_timeout:
                st.error("⏰ 该决策已等待超过1小时，请立即处理！")
            try:
                db = get_db()
                latest_energy = db.get_latest_energy()
                if latest_energy:
                    energy_level = latest_energy.get("level")
                    if energy_level is not None and energy_level < 30:
                        st.warning(f"🧘 您当前能量较低（{energy_level}%），建议先休息片刻再做决策。")
            except Exception:
                pass

            st.write(f"**问题：** {question}")
            st.write(f"**任务ID：** {pending.get('task_id', 'unknown')}")
            st.write(f"**阶段ID：** {pending.get('stage_id', 'unknown')}")
            user_note = st.text_area("备注（可选）", key="decision_note")
            st.write("**请选择：**")
            cols = st.columns(len(options))
            for i, option in enumerate(options):
                with cols[i]:
                    if st.button(f"{options_display[i]}", key=f"btn_decision_{i}", use_container_width=True):
                        try:
                            decision_manager.resume_decision(
                                decision_id=decision_id,
                                user_choice=option,
                                user_note=user_note
                            )
                            st.success(f"✅ 已选择：{option}")
                            add_log(f"📋 用户决策：{option}（决策ID: {decision_id}）")
                            try:
                                db = get_db()
                                db.log_audit({
                                    "action": "decision_made",
                                    "agent_id": "founder",
                                    "details": json.dumps({
                                        "decision_id": decision_id,
                                        "choice": option,
                                        "note": user_note
                                    })
                                })
                            except Exception:
                                pass
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 恢复决策失败: {e}")
        show_dialog()
    except Exception as e:
        st.error(f"❌ 渲染决策对话框失败: {e}")
        add_log(f"❌ 渲染决策对话框失败: {e}", level="error")

# ================================================================
# V4.0 P1: 驾驶舱动态面板
# ================================================================

def parse_suggested_panels(briefing: dict) -> list:
    """
    解析军师简报中的 `_suggested_panels` 字段，返回面板配置列表。
    
    输入: briefing dict，包含 _suggested_panels 字段
    输出: [{"type": "metric", "title": "...", "value": ..., "delta": ...}, ...]
    """
    panels = []
    suggested = briefing.get("_suggested_panels", [])
    for panel_config in suggested:
        if isinstance(panel_config, dict):
            panels.append(panel_config)
    return panels


def render_dynamic_panels():
    """渲染动态面板（从 st.session_state.dynamic_panels 读取）"""
    dynamic_panels = st.session_state.get("dynamic_panels", [])
    if not dynamic_panels:
        return
    
    st.markdown("### 📊 动态面板")
    cols = st.columns(len(dynamic_panels))
    for i, panel in enumerate(dynamic_panels):
        with cols[i % len(cols)]:
            panel_type = panel.get("type", "metric")
            title = panel.get("title", "未命名")
            value = panel.get("value", 0)
            delta = panel.get("delta")
            
            if panel_type == "metric":
                if delta is not None:
                    st.metric(title, value, delta)
                else:
                    st.metric(title, value)
            elif panel_type == "line_chart":
                import pandas as pd
                import numpy as np
                data = panel.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    st.line_chart(df)
            elif panel_type == "bar_chart":
                import pandas as pd
                data = panel.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    st.bar_chart(df)
            else:
                st.write(f"**{title}**: {value}")
    st.divider()


def clear_dynamic_panels():
    """任务完成后清空临时面板"""
    st.session_state.dynamic_panels = []
    st.session_state.suggested_panels = []


def update_dynamic_panels_from_briefing(briefing: dict):
    """
    从军师简报更新动态面板。
    在军师分析完成后调用。
    """
    suggested = parse_suggested_panels(briefing)
    if suggested:
        st.session_state.suggested_panels = suggested
        st.session_state.dynamic_panels = suggested
        add_log(f"📊 动态面板已更新: {len(suggested)} 个面板", level="info")


# ================================================================
# F11: 指挥官工作台渲染（SaaS 专业风格）
# ================================================================

def get_agent_team():
    """获取模拟 AI 员工团队数据"""
    db_agents = []
    try:
        db = get_db()
        rows = db.execute_sql(
            "SELECT agent_id, agent_type, status FROM agents WHERE status != 'inactive' LIMIT 20"
        )
        db_agents = rows
    except Exception:
        pass

    # 从 session_state 和日志中推断活跃 agent
    running_count = sum(1 for t in st.session_state.tasks.values() if t.get("status") == "running")
    completed_count = sum(1 for t in st.session_state.tasks.values()
                          if t.get("status") == "completed")

    # 构建 agent 列表（从 runtime + db 数据）
    agents = []
    if st.session_state.get("ancestor"):
        ancestor_agent = st.session_state.ancestor
        status = "running" if running_count > 0 else "standby"
        agents.append({
            "name": "祖辈·家族长老",
            "role": "任务拆解 / 合规审计 / 家族健康守护",
            "status": status,
            "model": "Claude 3.5 Sonnet",
            "cost": "~¥0.15/次",
            "depends_on": None,
        })
    if running_count > 0 or completed_count > 0:
        agents.append({
            "name": "父辈·指挥官",
            "role": "SOP 搜索 / 阶段调度 / 资源协调",
            "status": "running" if running_count > 0 else "completed",
            "model": "Claude 3.5 Sonnet",
            "cost": "~¥0.25/次",
            "depends_on": "祖辈·家族长老" if running_count > 0 else None,
        })
        agents.append({
            "name": "孙辈·执行者",
            "role": "代码生成 / 文档撰写 / 测试执行",
            "status": "running" if running_count > 0 else "completed",
            "model": "Claude 3 Haiku",
            "cost": "~¥0.08/次",
            "depends_on": "父辈·指挥官",
        })

    # 基础 agent（始终存在）
    base_agents = [
        {"name": "成本·CFO", "role": "预算追踪 / 成本分析 / 异常预警", "status": "standby",
            "model": "GPT-4o-mini", "cost": "~¥0.02/次", "depends_on": None},
        {"name": "Skill·基因库", "role": "Skill 提取 / 验证激活 / 版本管理", "status": "standby",
            "model": "Claude 3 Haiku", "cost": "~¥0.05/次", "depends_on": None},
        {"name": "宪法·守护者", "role": "合规审计 / 规则执行 / 安全校验", "status": "standby",
            "model": "Claude 3 Haiku", "cost": "~¥0.03/次", "depends_on": None},
        {"name": "错题·复盘师", "role": "失败分析 / 经验提取 / 知识沉淀", "status": "standby",
            "model": "GPT-4o-mini", "cost": "~¥0.02/次", "depends_on": None},
        {"name": "日程·管家", "role": "日程提醒 / 时间规划 / 能量记录", "status": "standby",
            "model": "Local", "cost": "免费", "depends_on": None},
    ]
    agents.extend(base_agents)
    return agents, running_count, completed_count


# ================================================================
# CEO Agent LLM 调用
# ================================================================
def _call_ceo_llm(user_message: str) -> str:
    """
    调用 LLM 为 CEO Agent 生成回复。
    - 测试模式下返回 mock 响应
    - 生产模式下调用 DeepSeek API
    """
    # 测试模式：返回智能 mock 响应
    if os.getenv("FROST_TESTING") == "1":
        msg_lower = user_message.lower()
        if "进度" in msg_lower:
            return (
                "根据当前进度分析：项目正按计划推进中。建议关注以下要点：\n\n"
                "1. 确保每个阶段的产出物已完成验收\n"
                "2. 检查是否有阻塞项需要协调资源\n"
                "3. 建议每周进行一次阶段性回顾\n\n"
                "总体状态：✅ 正常"
            )
        elif "成本" in msg_lower or "预算" in msg_lower:
            return (
                "成本分析报告：\n\n"
                "本月 API 消耗在预算范围内，使用率健康。\n"
                "建议：保持当前优化策略，避免不必要的重复调用。\n\n"
                "状态：✅ 成本正常"
            )
        elif "下一步" in msg_lower or "做什么" in msg_lower:
            return (
                "基于当前项目状态，建议下一步行动：\n\n"
                "1. 优先完成当前阶段的产出验收\n"
                "2. 查看是否有 pending 的决策点需要处理\n"
                "3. 可以考虑启动日终回顾，记录今日进展\n\n"
                "需要我帮你执行其中某项吗？"
            )
        else:
            return (
                f"收到你的指令：「{user_message[:80]}」\n\n"
                "我已分析当前项目状态，建议如下：\n"
                "1. 确认任务优先级和依赖关系\n"
                "2. 分配资源并启动对应的 SOP 流程\n"
                "3. 完成后进行验收和知识沉淀\n\n"
                "需要我帮你具体执行哪一步？"
            )

    # 生产模式：调用真实 LLM
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        try:
            from core.secrets import get_decrypted_key
            api_key = get_decrypted_key("DEEPSEEK_API_KEY", prompt_if_missing=False)
        except Exception:
            pass
    if not api_key:
        return "⚠️ 未配置 API Key。请在设置页面配置 DEEPSEEK_API_KEY。"

    system_prompt = """你是 FROST-SOP 家族的 CEO Agent，负责全局指挥和决策。
你的职责包括：
1. 分析项目进度和状态
2. 给出行动建议和优先级排序
3. 回答关于项目管理的任何问题
4. 协调各个 Agent 的工作

请用简洁、专业的中文回复。回答控制在 200 字以内。"""

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ CEO Agent 暂时无法回复：{str(e)[:100]}\n请稍后重试或检查 API 配置。"


# ================================================================
# 导航子视图：技能库 / 成本 / 输出文档 / 设置
# ================================================================
def _render_skills_view():
    """导航视图：技能基因库"""
    st.markdown("## 🧬 技能基因库")
    st.caption("管理和浏览所有活跃的技能基因模板")

    # 返回仪表盘按钮
    if st.button("← 返回仪表盘", key="btn_skills_back"):
        st.session_state.wb_nav = "dashboard"
        st.rerun()

    st.divider()

    # 技能统计
    try:
        db = get_db()
        skills = db.execute_sql(
            "SELECT name, skill_type, status, trigger_keywords, success_rate "
            "FROM skills ORDER BY status, name"
        )
        if skills:
            active_count = sum(1 for s in skills if s.get("status") == "active")
            draft_count = sum(1 for s in skills if s.get("status") == "draft")
            st.markdown(f"**统计**: {len(skills)} 个技能 | {active_count} 活跃 | {draft_count} 草稿")

            for s in skills:
                status = s.get("status", "unknown")
                badge = "🟢" if status == "active" else ("🟡" if status == "draft" else "⚪")
                with st.expander(f"{badge} {s['name']} ({s.get('skill_type', '通用')})"):
                    st.caption(f"状态: {status}")
                    if s.get("trigger_keywords"):
                        st.caption(f"触发词: {s['trigger_keywords']}")
                    if s.get("success_rate") is not None:
                        st.caption(f"成功率: {s['success_rate']:.0%}")
        else:
            st.info("暂无技能记录。运行 SOP 任务将自动提取技能基因。")
    except Exception as e:
        st.warning(f"技能数据加载失败: {e}")

    # 基因模板展示
    st.divider()
    st.subheader("📋 SOP 教练模板")
    templates_dir = "sops/templates"
    if os.path.exists(templates_dir):
        templates = sorted([f for f in os.listdir(templates_dir) if f.endswith(".yaml")])
        if templates:
            for tpl in templates:
                with st.expander(f"📄 {tpl}"):
                    try:
                        with open(os.path.join(templates_dir, tpl), "r", encoding="utf-8") as f:
                            st.code(f.read(), language="yaml")
                    except Exception as e:
                        st.caption(f"读取失败: {e}")
        else:
            st.caption("模板目录为空")
    else:
        st.caption(f"模板目录 `{templates_dir}` 不存在")


def _render_costs_view():
    """导航视图：成本仪表盘"""
    st.markdown("## 💰 成本仪表盘")
    if st.button("← 返回仪表盘", key="btn_costs_back"):
        st.session_state.wb_nav = "dashboard"
        st.rerun()

    st.divider()

    # 调用现有成本渲染
    from core.cost import get_cost_tracker
    try:
        cost_tracker = get_cost_tracker()
        budget = cost_tracker.check_budget()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("本月消耗", f"¥{budget['total_cost']:.2f}")
        with col2:
            st.metric("月度预算", f"¥{budget['monthly_budget']:.2f}")
        with col3:
            usage_pct = budget.get("usage_ratio", 0) * 100
            st.metric("使用率", f"{usage_pct:.1f}%")
        with col4:
            st.metric("剩余", f"¥{budget['monthly_budget'] - budget['total_cost']:.2f}")

        st.progress(
            min(budget.get("usage_ratio", 0), 1.0),
            text=f"预算使用 {usage_pct:.1f}%"
        )
    except Exception as e:
        st.error(f"成本数据加载失败: {e}")

    # 成本明细表
    st.divider()
    st.subheader("📊 近期成本明细")
    try:
        db = get_db()
        records = db.execute_sql(
            "SELECT timestamp, agent_id, model, tokens, estimated_cost, operation "
            "FROM cost_log ORDER BY timestamp DESC LIMIT 50"
        )
        if records:
            import pandas as pd
            df = pd.DataFrame(records)
            if not df.empty:
                df["estimated_cost"] = df["estimated_cost"].apply(lambda x: f"¥{x:.4f}")
                df["timestamp"] = df["timestamp"].astype(str).str[:19]
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("暂无成本记录")
    except Exception as e:
        st.warning(f"成本明细加载失败: {e}")


def _render_outputs_view():
    """导航视图：输出文档浏览器"""
    st.markdown("## 📂 输出文档")
    if st.button("← 返回仪表盘", key="btn_outputs_back"):
        st.session_state.wb_nav = "dashboard"
        st.rerun()

    st.divider()

    output_dir = "output"
    if not os.path.exists(output_dir):
        st.info(f"`{output_dir}/` 目录尚未创建。运行 SOP 任务后将自动生成产出文件。")
        return

    all_files = []
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            fpath = os.path.join(root, f)
            relpath = os.path.relpath(fpath, output_dir)
            mtime = os.path.getmtime(fpath)
            size = os.path.getsize(fpath)
            all_files.append((relpath, mtime, size, fpath))

    all_files.sort(key=lambda x: x[1], reverse=True)

    st.caption(f"共 {len(all_files)} 个文件")

    # 文件搜索
    search = st.text_input("🔍 搜索文件名", key="output_search")
    filtered = all_files
    if search:
        filtered = [(r, m, s, p) for r, m, s, p in all_files if search.lower() in r.lower()]

    # 分页
    page_size = 30
    page = st.number_input("页码", min_value=1, max_value=max(
        1, (len(filtered) - 1) // page_size + 1), value=1, key="output_page")
    start = (page - 1) * page_size
    page_files = filtered[start:start + page_size]

    for relpath, mtime, size, fpath in page_files:
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        size_str = f"{size:,}B" if size < 1024 else f"{size / 1024:.1f}KB" if size < 1024 * \
            1024 else f"{size / 1024 / 1024:.1f}MB"
        col1, col2, col3 = st.columns([5, 2, 1])
        with col1:
            st.caption(f"📄 {relpath}")
        with col2:
            st.caption(f"{mtime_str}")
        with col3:
            st.caption(size_str)

        # 文件内容预览
        with st.expander(f"预览: {relpath}"):
            try:
                if relpath.endswith(('.py', '.yaml', '.yml', '.json', '.md', '.txt', '.html', '.css', '.js', '.toml', '.cfg', '.ini', '.sh', '.bat')):
                    with open(fpath, "r", encoding="utf-8", errors="replace") as ff:
                        content = ff.read()
                    st.code(content[:5000], language=relpath.split('.')[-1])
                else:
                    st.caption(f"二进制文件 ({size_str})，无法预览")
            except Exception as e:
                st.caption(f"读取失败: {e}")


def _render_settings_view():
    """导航视图：设置页"""
    st.markdown("## ⚙️ 设置")
    if st.button("← 返回仪表盘", key="btn_settings_back"):
        st.session_state.wb_nav = "dashboard"
        st.rerun()

    st.divider()

    # API 配置
    st.subheader("🔑 API 配置")
    col1, col2 = st.columns([3, 1])
    with col1:
        api_key_status = "✅ 已配置" if os.getenv("DEEPSEEK_API_KEY") else "⚠️ 未配置"
        st.caption(f"DEEPSEEK_API_KEY: {api_key_status}")
    with col2:
        if st.button("🔐 加密存储", key="btn_encrypt_setup", use_container_width=True):
            try:
                from core.secrets import setup_wizard
                setup_wizard()
                st.success("加密存储已配置")
            except Exception as e:
                st.error(f"配置失败: {e}")

    # 系统状态
    st.divider()
    st.subheader("📊 系统状态")
    try:
        db = get_db()
        conn = db.get_connection()
        st.caption(f"数据库连接: ✅ 正常")

        # 各表行数
        tables = ["skills", "skill_versions", "cost_log", "decision_points", "audit_log"]
        for table in tables:
            try:
                result = db.execute_sql(f"SELECT COUNT(*) as cnt FROM {table}")
                cnt = result[0]["cnt"] if result else 0
                st.caption(f"  {table}: {cnt} 行")
            except Exception:
                st.caption(f"  {table}: ⚠️ 查询失败")
    except Exception as e:
        st.warning(f"数据库状态检查失败: {e}")

    # 工作台模式
    st.divider()
    st.subheader("🎯 当前工作模式")
    st.caption(f"模式: {st.session_state.wb_mode}")
    st.caption(f"视图: {st.session_state.get('wb_view', 'dashboard')}")
    st.caption(f"初始化: {'✅' if st.session_state.get('initialized') else '❌'}")

    # 清理 & 重置
    st.divider()
    st.subheader("🛠️ 维护操作")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🗑️ 清理 cost_log 未知记录", use_container_width=True, key="btn_cleanup_cost"):
            try:
                db = get_db()
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cost_log WHERE agent_id = 'unknown'")
                conn.commit()
                st.success("未知 agent_id 记录已清理")
            except Exception as e:
                st.error(f"清理失败: {e}")
    with col_b:
        if st.button("🔄 重置导航到仪表盘", use_container_width=True, key="btn_reset_nav"):
            st.session_state.wb_nav = "dashboard"
            st.session_state.wb_view = "dashboard"
            st.rerun()


def render_commander_dashboard():
    """渲染指挥官驾驶舱——专业SaaS后台首屏"""
    agents, running_cnt, completed_cnt = get_agent_team()
    proj = get_project_by_mode(st.session_state.wb_mode)
    task = get_recommended_task(st.session_state.wb_mode)

    # 成本数据
    try:
        cost_tracker = get_cost_tracker()
        budget_info = cost_tracker.check_budget()
        total_cost = budget_info["total_cost"]
        monthly_budget = budget_info["monthly_budget"]
        usage_ratio = budget_info["usage_ratio"]
    except Exception:
        total_cost = st.session_state.total_tokens
        monthly_budget = 100000
        usage_ratio = total_cost / monthly_budget if monthly_budget > 0 else 0

    # 模型成本细分（从 cost_log 聚合）
    model_costs = {}
    for entry in st.session_state.cost_log:
        model = entry.get("agent", "unknown")
        tokens = entry.get("tokens", 0)
        model_costs[model] = model_costs.get(model, 0) + tokens

    # ================================================================
    # 顶部全局导航栏 — 可交互按钮
    # ================================================================
    nav_items = [
        ("dashboard", "仪表盘"),
        ("skills", "技能库"),
        ("costs", "成本"),
        ("outputs", "输出文档"),
        ("settings", "设置"),
    ]
    mode_labels = {"dev": "开发模式", "create": "创作模式", "client": "客户模式"}
    mode = st.session_state.wb_mode
    current_nav = st.session_state.get("wb_nav", "dashboard")

    # 渲染品牌 + 导航栏布局
    nav_brand = f'<span class="brand">FROST-SOP</span><span class="brand-sub">| 家族AI指挥平台</span>'
    nav_right = f'<span style="font-size:12px;color:#94A3B8;">{mode_labels.get(mode, mode)}</span>'
    nav_right += f'<span class="task-badge">{running_cnt} running · {completed_cnt} done</span>'
    nav_right += '<span class="user-avatar">L</span>'

    st.markdown(f'''
    <div class="saas-navbar">
        <div>{nav_brand}</div>
        <div class="nav-right">{nav_right}</div>
    </div>
    ''', unsafe_allow_html=True)

    # 可点击导航按钮行
    nav_cols = st.columns([1, 1, 1, 1, 1, 4])
    for i, (nid, nlabel) in enumerate(nav_items):
        is_active = current_nav == nid
        btn_type = "primary" if is_active else "secondary"
        with nav_cols[i]:
            if st.button(
                nlabel,
                key=f"navbtn_{nid}",
                type=btn_type,
                use_container_width=True,
            ):
                st.session_state.wb_nav = nid
                st.rerun()

    # ================================================================
    # 导航路由 — 非仪表盘视图直接渲染对应内容并返回
    # ================================================================
    if current_nav == "skills":
        _render_skills_view()
        return
    elif current_nav == "costs":
        _render_costs_view()
        return
    elif current_nav == "outputs":
        _render_outputs_view()
        return
    elif current_nav == "settings":
        _render_settings_view()
        return
    # current_nav == "dashboard" → 继续渲染仪表盘

    # ================================================================
    # 主内容区 — 左右分栏
    # ================================================================
    st.markdown('<div class="saas-content">', unsafe_allow_html=True)
    col_main, col_side = st.columns([7, 3])

    with col_main:
        # --- 项目概览卡片 ---
        project_name = proj["name"] if proj else "默认项目"
        project_icon = proj.get("icon", "◈") if proj else "◈"
        st.markdown(f"""
        <div class="saas-project-header">
            <div>
                <span class="project-title">{project_icon} {project_name}</span>
                <span class="saas-badge saas-badge-active" style="margin-left:10px;">进行中</span>
                <span class="saas-badge saas-badge-monitoring" style="margin-left:6px;">CEO Agent · 监控中</span>
            </div>
            <div style="text-align:right;">
                <div style="font-size:14px;font-weight:700;color:#0F172A;">
                    {task['progress']}% 完成
                </div>
                <div style="font-size:11px;color:#64748B;">
                    预计剩余 {task.get('duration', '2h')}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- 进度条 ---
        progress_val = task.get("progress", 0)
        st.markdown(f"""
        <div style="margin-bottom:16px;font-size:12px;color:#64748B;">
            当前任务 · {task['task_name'][:60]}
        </div>
        """, unsafe_allow_html=True)
        st.progress(progress_val / 100, text=f"{progress_val}%")
        # 操作按钮
        col_a, col_b = st.columns([3, 1])
        with col_a:
            if st.button("▶ 开始工作", key="btn_saas_start", type="primary", use_container_width=True):
                st.session_state.wb_view = "project_detail"
                st.session_state.wb_active_project = task.get(
                    "project_id", st.session_state.wb_mode)
                add_log(f"🎯 开始任务: {task['task_name']}")
                st.rerun()
        with col_b:
            alt_idx = st.session_state.get("wb_alt_index", 0)
            alts = task.get("alternatives", [])
            if alts and st.button("↻ 换一个", key="btn_saas_switch", use_container_width=True):
                new_idx = (alt_idx + 1) % len(alts)
                st.session_state.wb_alt_index = new_idx
                st.rerun()

        # --- 动态提示文本 ---
        if progress_val < 30:
            hint = "项目刚起步，建议明确需求文档后进入核心开发阶段。"
        elif progress_val < 70:
            hint = "核心功能开发中，关注测试覆盖率和代码质量。"
        elif progress_val < 100:
            hint = "接近交付，请确认所有验收标准并准备上线。"
        else:
            hint = "项目已完成，可以归档并总结经验。"
        st.caption(f"💡 {hint}")

        st.divider()

        # --- KPI 卡片行 ---
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f"""
            <div class="saas-stat-card">
                <div class="stat-label">任务进度</div>
                <div class="stat-value">{progress_val}%</div>
                <div class="stat-delta">{task['task_name'][:20]}...</div>
            </div>
            """, unsafe_allow_html=True)
        with k2:
            st.markdown(f"""
            <div class="saas-stat-card">
                <div class="stat-label">运行中 Agent</div>
                <div class="stat-value">{running_cnt}</div>
                <div class="stat-delta">共 {len(agents)} 个成员</div>
            </div>
            """, unsafe_allow_html=True)
        with k3:
            st.markdown(f"""
            <div class="saas-stat-card">
                <div class="stat-label">已消耗成本</div>
                <div class="stat-value">¥{total_cost:.2f}</div>
                <div class="stat-delta">预算 ¥{monthly_budget:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
        with k4:
            energy = None
            try:
                db = get_db()
                energy = db.get_latest_energy()
            except Exception:
                pass
            e_level = energy.get("level", 75) if energy else 75
            e_text = "充足" if e_level >= 60 else "适中" if e_level >= 30 else "偏低"
            e_color = "#22C55E" if e_level >= 60 else "#F59E0B" if e_level >= 30 else "#EF4444"
            st.markdown(f"""
            <div class="saas-stat-card">
                <div class="stat-label">创始人能量</div>
                <div class="stat-value" style="color:{e_color};">{e_level}%</div>
                <div class="stat-delta">状态: {e_text}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

        # V4.0 P1: 渲染动态面板
        render_dynamic_panels()

        # --- 预算消耗长条卡片 ---
        pct = usage_ratio * 100
        pfill_class = ""
        if pct > 80:
            pfill_class = "danger"
        elif pct > 60:
            pfill_class = "warning"

        model_detail = ""
        for model_name, tokens in sorted(model_costs.items(), key=lambda x: -x[1])[:4]:
            model_detail += f'<span style="margin-right:16px;font-size:12px;color:#64748B;">{model_name}: {tokens:,} tokens</span>'

        st.markdown(f"""
        <div class="saas-cost-bar">
            <div class="cost-header">
                <div>
                    <span style="font-size:14px;font-weight:700;color:#0F172A;">预算消耗</span>
                    <span style="font-size:12px;color:#64748B;margin-left:8px;">已消耗 ¥{total_cost:.2f} / 预算 ¥{monthly_budget:,.0f}</span>
                </div>
                <div style="font-size:14px;font-weight:700;color:{'#EF4444' if pct > 80 else '#3B82F6'};">
                    {pct:.1f}%
                </div>
            </div>
            <div class="saas-progress">
                <div class="saas-progress-fill {pfill_class}" style="width:{min(pct, 100):.1f}%;"></div>
            </div>
            <div style="margin-top:10px;">{model_detail}</div>
        </div>
        """, unsafe_allow_html=True)

        # --- AI 员工团队 — 可交互卡片 ---
        st.markdown("""
        <div style="font-size:13px;font-weight:700;color:#0F172A;margin-bottom:12px;">
            AI 员工团队
        </div>
        """, unsafe_allow_html=True)

        agent_skill_map = {
            "祖辈·家族长老": ["任务拆解", "合规审计", "家族健康", "长老建议"],
            "父辈·指挥官": ["SOP搜索", "阶段调度", "资源协调", "决策管理"],
            "孙辈·执行者": ["代码生成", "文档撰写", "测试执行", "LLM调用"],
            "成本·CFO": ["预算追踪", "成本分析", "异常预警"],
            "Skill·基因库": ["Skill提取", "验证激活", "版本管理"],
            "宪法·守护者": ["合规审计", "规则执行", "安全校验"],
            "错题·复盘师": ["失败分析", "经验提取", "知识沉淀"],
            "日程·管家": ["日程提醒", "时间规划", "能量记录"],
        }

        for ag in agents[:8]:
            s = ag["status"]
            status_label = {"running": "运行中", "completed": "已完成",
                "waiting": "等待中", "standby": "待命中"}.get(s, s)
            status_icon = {"running": "🟢", "completed": "✅",
                "waiting": "🟡", "standby": "⚪"}.get(s, "⚪")
            skills = agent_skill_map.get(ag["name"], ["通用任务"])

            with st.expander(f"{status_icon} {ag['name']} — {status_label}", expanded=(s == "running")):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.caption(f"**角色**: {ag['role']}")
                    st.caption(f"**模型**: {ag['model']} | **成本**: {ag['cost']}")
                    if ag.get("depends_on"):
                        st.caption(f"**依赖**: {ag['depends_on']}")

                    # 技能列表
                    st.caption("**技能标签**:")
                    skill_cols = st.columns(len(skills))
                    for i, skill_name in enumerate(skills):
                        with skill_cols[i]:
                            st.caption(f"`{skill_name}`")

                with col_b:
                    # 操作按钮
                    if s == "standby":
                        if st.button("▶ 唤醒", key=f"agent_wake_{ag['name']}", use_container_width=True):
                            add_log(f"🔔 唤醒 Agent: {ag['name']}")
                            st.toast(f"{ag['name']} 已收到唤醒指令")
                            st.rerun()
                    elif s == "running":
                        if st.button("⏸ 暂停", key=f"agent_pause_{ag['name']}", use_container_width=True):
                            add_log(f"⏸ 暂停 Agent: {ag['name']}")
                            st.toast(f"{ag['name']} 暂停请求已发送")
                            st.rerun()
                    elif s == "completed":
                        if st.button("🔄 重用", key=f"agent_reuse_{ag['name']}", use_container_width=True):
                            add_log(f"🔄 重用 Agent: {ag['name']}")
                            st.toast(f"{ag['name']} 再次激活")
                            st.rerun()

                # 进度展示（running 状态）
                if s == "running":
                    import random
                    random.seed(hash(ag["name"]) % 10000)
                    fake_progress = random.randint(30, 90)
                    st.progress(fake_progress / 100, text=f"任务进度: {fake_progress}%")

        # --- 实时日志窗口 ---
        st.markdown("""
        <div style="font-size:13px;font-weight:700;color:#0F172A;margin-bottom:8px;">
            实时日志
        </div>
        """, unsafe_allow_html=True)
        log_lines = st.session_state.logs[-12:] if st.session_state.logs else []
        if log_lines:
            log_html = '<div class="saas-log-window">'
            for log in reversed(log_lines):
                lvl = log.get("level", "info")
                lvl_class = f"saas-log-{lvl}" if lvl in ("info",
                                                         "success", "warn", "error") else "saas-log-info"
                log_html += f'<div class="saas-log-line"><span class="saas-log-time">[{log["time"]}]</span> <span class="{lvl_class}">{log["message"][:100]}</span></div>'
            log_html += '</div>'
        else:
            log_html = '<div class="saas-log-window"><span class="saas-log-time">系统就绪，等待任务...</span></div>'
        st.markdown(log_html, unsafe_allow_html=True)

    # ================================================================
    # 右侧面板 — CEO Agent 对话 & 快捷指令
    # ================================================================
    with col_side:
        # 初始化 CEO 对话历史
        if "ceo_conversation" not in st.session_state:
            st.session_state.ceo_conversation = []
        if "ceo_pending_msg" not in st.session_state:
            st.session_state.ceo_pending_msg = None

        # CEO Agent panel
        st.markdown("""
        <div class="saas-panel">
            <div class="saas-panel-title">CEO Agent 对话</div>
        </div>
        """, unsafe_allow_html=True)

        ceo_msg = st.text_area(
            "输入指令",
            placeholder="向 CEO Agent 提问或下达指令...",
            key="ceo_chat_input",
            height=80,
            label_visibility="collapsed"
        )
        if st.button("发送", key="btn_ceo_send", use_container_width=True):
            if ceo_msg.strip():
                st.session_state.ceo_pending_msg = ceo_msg.strip()
                st.rerun()

        # 处理待发送消息（在 rerun 后执行，避免重复发送）
        if st.session_state.ceo_pending_msg:
            msg = st.session_state.ceo_pending_msg
            st.session_state.ceo_pending_msg = None
            add_log(f"💬 CEO对话: {msg[:60]}")

            # 调用 LLM 获取回复
            with st.spinner("CEO Agent 思考中..."):
                response = _call_ceo_llm(msg)
            st.session_state.ceo_conversation.append({"role": "user", "content": msg})
            st.session_state.ceo_conversation.append({"role": "assistant", "content": response})
            add_log(f"✅ CEO回复: {response[:60]}")
            st.rerun()

        # 显示对话历史
        conv = st.session_state.ceo_conversation
        if conv:
            with st.container(height=300):
                for entry in conv[-10:]:  # 最近10条
                    role_label = "🧑 你" if entry["role"] == "user" else "🤖 CEO"
                    st.caption(f"**{role_label}**: {entry['content'][:200]}")
        else:
            st.caption("_向 CEO Agent 提问以开始对话_")

        # 快捷指令
        st.markdown("""
        <div class="saas-panel" style="margin-top:8px;">
            <div class="saas-panel-title">快捷指令</div>
        </div>
        """, unsafe_allow_html=True)

        q1, q2, q3 = st.columns(3)
        with q1:
            if st.button("📊 进度如何", key="quick_progress", use_container_width=True):
                prompt = f"当前项目进度: {progress_val}%，请评估状态并给出建议"
                with st.spinner("CEO 分析中..."):
                    resp = _call_ceo_llm(prompt)
                st.session_state.ceo_conversation.append({"role": "user", "content": "📊 进度如何"})
                st.session_state.ceo_conversation.append({"role": "assistant", "content": resp})
                add_log("📊 CEO进度分析完成")
                st.rerun()
        with q2:
            if st.button("💰 成本正常吗", key="quick_cost", use_container_width=True):
                status = "正常" if pct < 80 else "预警" if pct < 100 else "超标"
                prompt = f"成本使用率 {pct:.1f}%，状态：{status}，月度预算 ¥{monthly_budget}，请分析并给出建议"
                with st.spinner("CEO 分析中..."):
                    resp = _call_ceo_llm(prompt)
                st.session_state.ceo_conversation.append({"role": "user", "content": "💰 成本正常吗"})
                st.session_state.ceo_conversation.append({"role": "assistant", "content": resp})
                add_log("💰 CEO成本分析完成")
                st.rerun()
        with q3:
            if st.button("🎯 下一步做什么", key="quick_next", use_container_width=True):
                prompt = f"当前项目: {project_name}，进度 {progress_val}%，模式 {st.session_state.wb_mode}。请给出下一步行动建议"
                with st.spinner("CEO 分析中..."):
                    resp = _call_ceo_llm(prompt)
                st.session_state.ceo_conversation.append({"role": "user", "content": "🎯 下一步做什么"})
                st.session_state.ceo_conversation.append({"role": "assistant", "content": resp})
                add_log("🎯 CEO建议已生成")
                st.rerun()

        # 模式快速切换
        st.markdown("""
        <div class="saas-panel" style="margin-top:8px;">
            <div class="saas-panel-title">上下文模式</div>
        </div>
        """, unsafe_allow_html=True)
        for mode_key, label in [("dev", "🔧 开发模式"), ("create", "✍️ 创作模式"), ("client", "💼 客户模式")]:
            is_active = st.session_state.wb_mode == mode_key
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"saas_mode_{mode_key}",
                         type=btn_type if is_active else "secondary",
                         use_container_width=True):
                if st.session_state.wb_mode != mode_key:
                    st.session_state.wb_mode = mode_key
                    st.session_state.wb_alt_index = 0
                    st.session_state.wb_view = "dashboard"
                    st.session_state.wb_active_project = None
                    add_log(f"🔄 上下文切换: {label}")
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)  # close saas-content

    # --- 日终回顾检查 ---
    check_daily_review()


def check_daily_review():
    """检查是否需要弹出日终回顾（每天 18:00 之后）—— SaaS 风格"""
    now = datetime.now()
    if now.hour < 18:
        return
    if st.session_state.get("wb_daily_review_dismissed"):
        return

    today_review = get_today_review()
    if today_review and today_review.get("confirmed"):
        return

    with st.container():
        st.markdown('<div class="daily-review-panel">', unsafe_allow_html=True)
        st.markdown("### 🌅 日终回顾")
        st.caption("一天的工作即将结束，来看看今天的成果——")

        narrative = generate_daily_narrative()
        st.markdown(f"""
        <div style="background:#F8FAFC; border-radius:6px; padding:14px; margin:10px 0;
                    font-size:13px; color:#0F172A; line-height:1.7; white-space:pre-line;">
        {narrative}
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("✅ 确认打卡", key="btn_review_confirm", type="primary", use_container_width=True):
                save_daily_review(narrative=narrative, confirmed=True)
                st.session_state.wb_daily_review_dismissed = True
                st.toast("🎉 今日打卡完成！辛苦了，明天见～")
                add_log("🌅 日终回顾已确认")
                st.rerun()
        with col_b:
            if st.button("📝 修改叙事", key="btn_review_edit", use_container_width=True):
                st.session_state.wb_view = "daily_review"
                st.rerun()
        with col_c:
            if st.button("⏭️ 稍后再说", key="btn_review_dismiss", use_container_width=True):
                st.session_state.wb_daily_review_dismissed = True
                add_log("🌅 日终回顾已延后")
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)


# ================================================================
# F11: 项目详情页
# ================================================================
def render_project_detail():
    """渲染项目详情页 — SaaS 风格"""
    pid = st.session_state.get("wb_active_project") or st.session_state.wb_mode
    proj = get_project_by_mode(pid) if pid in ["dev", "create", "client"] else None
    if not proj:
        proj = {"id": pid, "name": "项目详情", "icon": "📂", "sop_template": ""}

    # 返回 + 项目标题
    col_back, col_title = st.columns([1, 11])
    with col_back:
        if st.button("←", key="btn_back_to_dashboard", use_container_width=True):
            st.session_state.wb_view = "dashboard"
            st.session_state.wb_active_project = None
            st.rerun()
    with col_title:
        st.markdown(f"## {proj.get('icon', '📂')} {proj.get('name', '项目详情')}")
    st.caption(proj.get("description", ""))

    # ========== 保留现有3标签页功能 ==========
    tab1, tab2, tab3 = st.tabs(["💬 指挥面板", "💰 成本仪表盘", "🏥 家族健康"])

    with tab1:
        render_command_panel()
    with tab2:
        render_cost_dashboard()
    with tab3:
        render_health_dashboard()

    # ========== 项目专属信息 ==========
    st.divider()
    st.subheader("📋 SOP 进度时间线")
    sop_template = proj.get("sop_template", "")
    if sop_template:
        sop_file = f"sops/templates/{sop_template}.yaml"
        if os.path.exists(sop_file):
            try:
                sop = SOP.load_from_yaml(sop_file)
                stages = getattr(sop, 'stages', [])
                for i, stage in enumerate(stages):
                    phase_id = stage.get('phase_id', stage.get('name', f'Phase {i + 1}'))
                    st.markdown(
                        f"🔄 **Phase {i + 1}/{len(stages)}** — {phase_id} — "
                        f"{stage.get('description', '')[:60]}"
                    )
            except Exception:
                st.caption(f"SOP 模板: {sop_template}")
        else:
            st.caption(f"SOP 模板: {sop_template} (文件未找到)")
    else:
        st.info("该项目尚未关联SOP模板")

    st.divider()
    st.subheader("📂 最近产出")
    output_dir = "output"
    if os.path.exists(output_dir):
        files = sorted(os.listdir(output_dir), key=lambda f: os.path.getmtime(
            os.path.join(output_dir, f)), reverse=True)[:10]
        if files:
            for f in files:
                st.caption(f"📄 {f}")
        else:
            st.caption("暂无产出文件")
    else:
        st.caption("output/ 目录不存在")

    st.divider()
    st.subheader("🧬 关联 Skill")
    try:
        db = get_db()
        skills_raw = db.execute_sql(
            "SELECT name, skill_type, status FROM skills WHERE status='active' LIMIT 10"
        )
        if skills_raw:
            for s in skills_raw:
                st.caption(f"- {s['name']} ({s.get('skill_type', '通用')})")
        else:
            st.caption("暂无活跃 Skill")
    except Exception:
        st.caption("Skill 数据不可用")

    st.divider()
    st.subheader("💰 成本统计")
    try:
        db = get_db()
        cost_result = db.execute_sql("""
            SELECT COALESCE(SUM(estimated_cost), 0) as total
            FROM cost_log
            WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now', 'localtime')
        """)
        monthly = cost_result[0]["total"] if cost_result else 0
        st.metric("本月成本", f"¥{monthly:.2f}")
    except Exception:
        st.caption("成本数据不可用")


# ================================================================
# F11: 日终回顾详情页
# ================================================================
def render_daily_review_detail():
    """渲染日终回顾编辑页"""
    if st.button("← 返回首屏", key="btn_review_back"):
        st.session_state.wb_view = "dashboard"
        st.rerun()

    st.title("🌅 日终回顾")

    narrative = generate_daily_narrative()
    edited = st.text_area("今日叙事总结（可编辑）", value=narrative, height=300, key="review_narrative")

    # 能量曲线
    try:
        db = get_db()
        history = db.get_energy_history(7)
        if history:
            import pandas as pd
            st.subheader("📈 近7天能量曲线")
            df = pd.DataFrame(history)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                st.line_chart(df.set_index("timestamp")["energy_level"], height=200)
    except ImportError:
        st.caption("(需要 pandas 显示曲线)")
    except Exception:
        pass

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✅ 确认打卡", key="btn_review_detail_confirm", type="primary", use_container_width=True):
            save_daily_review(narrative=edited, confirmed=True)
            st.session_state.wb_daily_review_dismissed = True
            st.session_state.wb_view = "dashboard"
            st.toast("🎉 今日打卡完成！辛苦了～")
            add_log("🌅 日终回顾已确认")
            st.rerun()
    with col_b:
        if st.button("💾 保存草稿", key="btn_review_detail_save", use_container_width=True):
            save_daily_review(narrative=edited, confirmed=False)
            st.toast("📝 叙事先保存了，之后可以再改")
            add_log("🌅 日终回顾草稿已保存")


# ================================================================
# 移动端简版
# ================================================================
def render_mobile_view():
    """移动端简化视图 — SaaS 风格"""
    st.markdown("""
    <div style="background:#1E293B;color:#F8FAFC;padding:10px 14px;border-radius:6px;margin-bottom:12px;
                display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:14px;font-weight:700;">FROST-SOP</span>
        <span style="font-size:11px;color:#94A3B8;">移动指挥台</span>
    </div>
    """, unsafe_allow_html=True)

    task = get_recommended_task(st.session_state.wb_mode)

    # 焦点任务
    st.markdown(f"""
    <div style="background:#FFFFFF;border-radius:8px;padding:14px;border:1px solid #E2E8F0;margin-bottom:12px;">
        <div style="font-size:11px;color:#64748B;font-weight:600;text-transform:uppercase;margin-bottom:4px;">
            今日任务
        </div>
        <div style="font-size:15px;font-weight:700;color:#0F172A;">{task['task_name'][:40]}</div>
        <div style="font-size:12px;color:#94A3B8;margin-top:6px;">{task['duration']} · {task['match_text']}</div>
    </div>
    """, unsafe_allow_html=True)

    # 模式切换（紧凑版）
    cols = st.columns(3)
    for i, (mode_key, label) in enumerate([
        ("dev", "🔧 开发"), ("create", "✍️ 创作"), ("client", "💼 客户")
    ]):
        with cols[i]:
            if st.button(label, key=f"mobile_mode_{mode_key}",
                         type="primary" if st.session_state.wb_mode == mode_key else "secondary",
                         use_container_width=True):
                st.session_state.wb_mode = mode_key
                st.rerun()

    # 紧急提醒
    try:
        db = get_db()
        energy = db.get_latest_energy()
        if energy and energy.get("level", 50) < 30:
            st.warning("🧘 能量偏低，建议休息一下")
    except Exception:
        pass


# ================================================================
# 保留的现有功能（F1-F10）
# ================================================================

def render_command_panel():
    """Tab 1: 指挥面板（保留原有功能）"""
    # 快捷命令按钮
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🆕 新功能开发", use_container_width=True, key="btn_new_feature"):
            st.session_state.task_input = "给项目添加用户认证功能"
    with col2:
        if st.button("🐛 Bug修复", use_container_width=True, key="btn_bug_fix"):
            st.session_state.task_input = "修复登录页面的样式错乱问题"
    with col3:
        if st.button("📊 周期回顾", use_container_width=True, key="btn_review"):
            st.session_state.task_input = "回顾本周的开发任务完成情况"

    # 任务输入框
    task_input = st.text_area(
        "输入任务描述",
        placeholder="用自然语言描述你想让AI完成的任务...",
        value=st.session_state.get("task_input", ""),
        key="task_input_widget",
    )

    # F6.5 撒豆成兵
    st.subheader("💾 F6.5 撒豆成兵")
    col_save, col_load = st.columns(2)
    with col_save:
        if st.button("💾 保存当前配置", use_container_width=True, key="btn_save_config"):
            available_skills = []
            try:
                conn = get_db().get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, name, skill_type, task_type, status FROM skills WHERE status = 'active'"
                )
                active_skills = cursor.fetchall()
                available_skills = [
                    {"id": s["id"], "name": s["name"],
                        "task_type": s["task_type"] or s["skill_type"]}
                    for s in active_skills
                ]
            except Exception:
                pass

            config = {
                "timestamp": datetime.now().isoformat(),
                "task_description": st.session_state.get("task_input", ""),
                "parameters": {},
                "project_name": "FROST-SOP 项目工作台",
                "version": "F11",
                "available_skills": available_skills,
            }
            asset_store = AssetStore()
            filename = asset_store.save(config)
            st.session_state.saved_config = config
            st.success(f"✅ 配置已保存为：{filename}，下次一键唤醒")

    with col_load:
        if st.button("🔄 唤醒上次配置", use_container_width=True, key="btn_load_config"):
            asset_store = AssetStore()
            config = asset_store.load_latest()
            if config:
                st.session_state["task_input"] = config.get("task_description", "")
                st.success("✅ 已唤醒上次配置，可以直接执行")
                st.rerun()
            else:
                st.warning("⚠️ 没有找到可唤醒的配置，请先保存一次")

    # 执行按钮
    if st.button("🚀 执行任务", type="primary", use_container_width=True, key="btn_execute"):
        execute_task(task_input or st.session_state.get("task_input", ""))


def execute_task(task_text: str):
    """执行SOP任务（保留原有6步流程）"""
    if not task_text:
        st.warning("请输入任务描述")
        return
    if not st.session_state.initialized:
        st.warning("家族系统尚未初始化，请刷新页面")
        return

    task_id = create_task_internal(task_text)
    task = st.session_state.tasks[task_id]
    task["status"] = "running"

    try:
        db = get_db()
        db.update("tasks", "id", task_id, {"status": "running"})
    except Exception:
        pass

    st.session_state.task_count += 1
    add_log(f"📝 创始人输入: {task_text}")

    with st.status("🚀 执行任务中...", expanded=True) as status_status:
        try:
            # Step 1: 祖辈LLM拆解
            status_status.update(label="Step 1/6: 祖辈正在拆解任务...", state="running")
            add_log("--- Step 1/6: 祖辈开始拆解 ---")
            context = st.session_state.ancestor.run(
                sop_steps=["call_llm"],
                initial_context={
                    "_prompt": f"分析以下任务，拆解为1-3个父辈Agent，返回JSON: {task_text}",
                    "_system_prompt": "你是一个任务拆解助手。请返回有效的JSON。",
                }
            )
            llm_response = context.get("_llm_response", "")
            tokens = context.get("_llm_tokens", {}).get("total", 0)
            st.session_state.total_tokens += tokens
            st.session_state.cost_log.append({
                "timestamp": datetime.now().isoformat(),
                "tokens": tokens,
                "task_id": task_id,
                "agent": "ancestor",
            })
            add_log(f"✅ Step 1完成: 拆解结果({tokens} Token)")

            # Step 2: 创建父辈并搜索SOP
            status_status.update(label="Step 2/6: 父辈正在搜索SOP...", state="running")
            add_log("--- Step 2/6: 父辈搜索SOP ---")
            coordination_store = Store()
            parent = create_parent("parent_commander", coordination_store)
            search_context = parent.run(
                sop_steps=["search_sop"],
                initial_context={
                    "_search_query": "DEV-001",
                    "_asset_store": st.session_state.asset_store,
                    "_search_external": True,
                }
            )
            search_results = search_context.get("_search_results", [])
            add_log(f"✅ Step 2完成: 找到 {len(search_results)} 个SOP模板")

            # Step 3: 合规校验
            status_status.update(label="Step 3/6: 合规校验...", state="running")
            add_log("--- Step 3/6: 合规校验 ---")
            sop = SOP.load_from_yaml("sops/templates/DEV-001.yaml")
            compliance_rules = {
                "required_stages": ["审查交付"],
                "forbidden_skills": ["direct_db_write"],
            }
            if search_results:
                sop_to_use = search_results[0].get("content", {})
            else:
                sop_to_use = {
                    "stages": sop.stages,
                    "required_stages": sop.required_stages,
                    "forbidden_skills": sop.forbidden_skills,
                }

            context = st.session_state.ancestor.run(
                sop_steps=["validate_sop"],
                initial_context={
                    "_sop_to_validate": type('SOP', (), sop_to_use)(),
                    "_compliance_rules": compliance_rules,
                }
            )
            validation = context.get("_validation_result", {})
            if validation.get("valid"):
                add_log("✅ Step 3完成: 合规校验通过")
            else:
                add_log(f"❌ Step 3失败: 合规校验失败 - {validation.get('errors')}")
                status_status.update(label="❌ 合规校验失败", state="error")
                task["status"] = "failed"
                save_tasks_to_store()
                st.error(f"合规校验失败: {validation.get('errors')}")
                return

            # Step 4: 内化SOP
            status_status.update(label="Step 4/6: 父辈内化SOP...", state="running")
            add_log("--- Step 4/6: 内化SOP ---")
            context = parent.run(
                sop_steps=["internalize_sop"],
                initial_context={"_sop_to_internalize": sop_to_use}
            )
            sop_stages_detail = context.get("_sop_stages", [])
            add_log(f"✅ Step 4完成: 内化完成，共{len(sop_stages_detail)}个阶段")

            # Step 5: 执行各阶段
            stage_context = {"_stage_results": [], "_parent_agent": parent}
            progress_bar = st.progress(0)
            for i, stage in enumerate(sop_stages_detail):
                stage_name = stage.get("name", f"阶段{i + 1}")
                status_status.update(
                    label =f"Step 5/6: 孙辈执行「{stage_name}」({i + 1}/{len(sop_stages_detail)})...",
                    state="running"
                )
                add_log(f"--- Step 5.{i + 1}: 孙辈执行「{stage_name}」---")
                stage_context["_current_stage"] = stage
                stage_context = parent.run(
                    sop_steps=["execute_stage"],
                    initial_context=stage_context
                )
                result = stage_context.get("_current_stage_result", {})
                add_log(f"✅ 阶段「{stage_name}」完成")
                task["stages"].append({
                    "name": stage_name,
                    "status": result.get("status", "unknown"),
                    "output": result.get("output", ""),
                })
                progress_bar.progress((i + 1) / len(sop_stages_detail))

            # Step 6: 收割产出
            status_status.update(label="Step 6/6: 收割产出...", state="running")
            add_log("--- Step 6/6: 收割产出 ---")
            all_results = stage_context.get("_stage_results", [])
            st.session_state.asset_store.save("task:latest", {
                "task": task_text,
                "stages_completed": len(all_results),
                "stage_results": all_results,
            })
            task["status"] = "completed"
            task["results"] = all_results
            save_tasks_to_store()
            try:
                db = get_db()
                db.update("tasks", "id", task_id, {"status": "completed"})
            except Exception:
                pass
            add_log(f"🎉 任务全部完成! {len(all_results)}个阶段产出已存入资产Store")
            st.session_state.task_result = all_results
            status_status.update(
                label=f"✅ 任务完成! ({len(all_results)}个阶段)",
                state="complete"
            )

        except Exception as e:
            task["status"] = "failed"
            save_tasks_to_store()
            try:
                db = get_db()
                db.update("tasks", "id", task_id, {"status": "failed"})
            except Exception:
                pass
            add_log(f"❌ 任务执行失败: {type(e).__name__}: {e}", level="error")
            status_status.update(label=f"❌ 执行失败: {e}", state="error")
            st.error(f"任务执行失败: {type(e).__name__}: {e}")


def render_cost_dashboard():
    """Tab 2: 成本仪表盘（保留原有功能）"""
    st.subheader("💰 成本仪表盘")
    try:
        cost_tracker = get_cost_tracker()
        budget_info = cost_tracker.check_budget()
        monthly_budget = budget_info["monthly_budget"]
        total_cost = budget_info["total_cost"]
        usage_ratio = budget_info["usage_ratio"]
        remaining = budget_info["remaining"]
    except Exception:
        monthly_budget = 100000
        total_cost = st.session_state.total_tokens
        usage_ratio = total_cost / monthly_budget if monthly_budget > 0 else 0
        remaining = monthly_budget - total_cost

    alert_text = "🔴 超标" if usage_ratio >= 1.0 else ("🟡 预警" if usage_ratio >= 0.8 else "🟢 正常")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("已用成本", f"¥{total_cost:.2f}", delta=f"预算: ¥{monthly_budget:.2f}")
    with col2:
        st.metric("剩余预算", f"¥{remaining:.2f}", delta=f"{usage_ratio * 100:.1f}% 已用")
    with col3:
        st.metric("使用状态", alert_text)
    with col4:
        st.metric("本月任务", st.session_state.task_count, delta="个任务")

    st.write("**预算使用进度:**")
    st.progress(min(usage_ratio, 1.0))
    st.write(f"{usage_ratio * 100:.1f}% 已用 (¥{total_cost:.2f} / ¥{monthly_budget:.2f})")


# ================================================================
# 保留的辅助函数（F4兵器库、F9能量、F9日程）
# ================================================================

def _count_gene_templates():
    """统计能力基因库中的教练模板数量"""
    if not st.session_state.get("asset_store"):
        return 0
    return sum(1 for key in st.session_state.asset_store.list_keys() if key.startswith("skill_gene:"))


def _show_armory_templates():
    """展示教练模板列表"""
    st.subheader("🏛️ 教练模板库")
    asset_store = st.session_state.get("asset_store")
    if not asset_store:
        st.info("资产Store未初始化")
        return
    templates = []
    for key in asset_store.list_keys():
        if key.startswith("skill_gene:"):
            gene = asset_store.load(key)
            if gene:
                templates.append(gene)
    categories = list(set(t.get("category", "未分类") for t in templates))
    selected_category = st.selectbox("分类筛选", ["全部"] + sorted(categories))
    if selected_category != "全部":
        templates = [t for t in templates if t.get("category") == selected_category]
    st.caption(f"共 {len(templates)} 个模板")
    for t in templates[:50]:
        with st.expander(f"{t.get('name', '未知')} ({t.get('category', '未分类')})"):
            st.write(t.get("description", "无描述")[:200])


def _show_mercenaries():
    """展示预置雇佣兵"""
    st.subheader("⚔️ 预置雇佣兵")
    st.write("**Markdown转HTML** (md2html)")
    st.write("**关键词提取** (extract_keywords)")
    st.write("**日期格式化** (format_date)")


def render_energy_logger():
    """在侧边栏渲染能量状态记录器"""
    st.subheader("⚡ 能量状态")
    if "energy_emotion" not in st.session_state:
        st.session_state.energy_emotion = ""
    energy_level = st.slider("当前能量", 0, 100, 50, key="energy_level")
    if energy_level < 30:
        st.markdown('<span style="color:#FB6B4B">🔴 低能量，建议休息</span>', unsafe_allow_html=True)
    elif energy_level < 60:
        st.markdown('<span style="color:#F97316">🟡 中等能量</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:#2D6A4F">🟢 能量充沛</span>', unsafe_allow_html=True)

    emotions = ["专注", "疲惫", "焦虑", "平静", "兴奋", "低落"]
    for row_idx in range(0, 6, 3):
        cols = st.columns(3)
        for col_idx, emotion in enumerate(emotions[row_idx:row_idx + 3]):
            with cols[col_idx]:
                is_selected = st.session_state.energy_emotion == emotion
                btn_label = f"{'✅ ' if is_selected else ''}{emotion}"
                if st.button(btn_label, key=f"emotion_{emotion}", use_container_width=True):
                    st.session_state.energy_emotion = emotion
                    st.rerun()

    energy_note = st.text_area("备注（可选）", key="energy_note_sidebar", height=60,
                                placeholder="记录此刻的想法...")
    if st.button("📝 记录此刻", key="record_energy", use_container_width=True):
        if st.session_state.energy_emotion:
            try:
                db = get_db()
                db.add_energy_log(level=energy_level,
                                  emotion=st.session_state.energy_emotion, note=energy_note)
                st.toast("✅ 能量状态已记录")
                add_log(f"⚡ 能量记录: {energy_level}% ({st.session_state.energy_emotion})")
                st.session_state.energy_emotion = ""
                st.rerun()
            except Exception as e:
                st.error(f"❌ 记录失败: {e}")
        else:
            st.warning("请先选择情绪标签")

    st.divider()
    st.caption("📈 近30天能量曲线")
    try:
        db = get_db()
        history = db.get_energy_history(30)
        if history:
            import pandas as pd
            df = pd.DataFrame(history)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                st.line_chart(df.set_index("timestamp")["energy_level"], height=150)
    except ImportError:
        st.caption("（需要 pandas 显示曲线图）")
    except Exception:
        pass


def render_schedule_page():
    """渲染私人日程管理页面"""
    st.title("📅 日程管理")
    st.caption("管理你的私人日程，系统会在关键节点提醒你")
    if "editing_schedule_id" not in st.session_state:
        st.session_state.editing_schedule_id = None

    with st.expander("➕ 添加日程", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("标题", key="schedule_title")
            start_dt = st.text_input("开始时间 (YYYY-MM-DD HH:MM)", key="schedule_start")
        with col2:
            repeat_type = st.selectbox("重复", ["none", "daily", "weekly", "monthly"], key="schedule_repeat",
                                       format_func=lambda x: {"none": "不重复", "daily": "每天", "weekly": "每周", "monthly": "每月"}.get(x, x))
            end_dt = st.text_input("结束时间 (YYYY-MM-DD HH:MM)", key="schedule_end")
        description = st.text_area("描述（可选）", key="schedule_desc", height=80)
        if st.button("✅ 添加日程", key="add_schedule_btn", use_container_width=True):
            if title and start_dt and end_dt:
                try:
                    db = get_db()
                    db.add_schedule(title=title, description=description, start_time=start_dt,
                                    end_time=end_dt, repeat_type=repeat_type, repeat_end="")
                    st.toast("✅ 日程已添加")
                    add_log(f"📅 日程添加: {title}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 添加失败: {e}")
            else:
                st.warning("请填写标题和时间")

    st.subheader("📋 日程列表")
    try:
        db = get_db()
        schedules = db.get_schedules()
        if not schedules:
            st.info("暂无日程，请添加第一个日程")
        else:
            from collections import defaultdict
            grouped = defaultdict(list)
            for s in schedules:
                start = s.get("start_time", "")
                date_key = start[:10] if start and len(start) >= 10 else "未知日期"
                grouped[date_key].append(s)
            for date_key in sorted(grouped.keys()):
                st.markdown(f"**{date_key}**")
                for s in grouped[date_key]:
                    with st.container():
                        col_main, col_del = st.columns([6, 1])
                        with col_main:
                            title_text = s.get("title") or s.get("name", "无标题")
                            st.write(f"**{title_text}**")
                            st.caption(f"{s.get('start_time', '?')} → {s.get('end_time', '?')}")
                        with col_del:
                            if st.button("🗑️", key=f"del_sch_{s['id']}"):
                                db.delete_schedule(s["id"])
                                st.toast("✅ 日程已删除")
                                st.rerun()
                        st.divider()
    except Exception as e:
        st.error(f"❌ 加载日程失败: {e}")


def render_health_dashboard():
    """渲染家族健康度仪表"""
    st.subheader("🏥 家族健康度")
    asset_store = st.session_state.get("asset_store")
    if not asset_store:
        st.info("资产Store未初始化")
        return
    with st.spinner("长老正在审计家族健康度..."):
        try:
            elder = create_elder("health_elder", asset_store=asset_store)
            context = {"_asset_store": asset_store,
                "_constitution_store": st.session_state.get("constitution_store")}
            result = elder.run(["audit_family"], context)
            report = result.get("_audit_report", {})
        except Exception as e:
            st.error(f"审计失败: {e}")
            return

    if not report:
        st.warning("审计报告为空")
        return

    stats = report.get("statistics", {})
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总任务数", stats.get("total_tasks", 0))
    with col2:
        st.metric("成功", stats.get("successful_tasks", 0))
    with col3:
        st.metric("失败", stats.get("failed_tasks", 0))
    with col4:
        st.metric("错题本", stats.get("total_lessons", 0))


# ================================================================
# 核心初始化函数
# ================================================================

def init_family():
    """初始化家族系统"""
    if not st.session_state.initialized:
        with st.spinner("正在初始化家族系统..."):
            st.session_state.constitution_store = create_constitution_store()
            add_log("✅ 宪法Store初始化完成")
            st.session_state.asset_store = create_asset_store()
            add_log("✅ 资产Store初始化完成")
            st.session_state.ancestor = create_ancestor(
                st.session_state.constitution_store, st.session_state.asset_store)
            add_log("✅ 祖辈Agent初始化完成")
            st.session_state.initialized = True
            add_log("家族系统初始化完成 - 祖辈Agent已就绪")

            # V2.0: 创建长老并订阅事件总线（fail-safe）
            elder = create_elder("elder_ui", asset_store=st.session_state.asset_store)
            if subscribe_elder_to_events(elder):
                add_log("✅ [V2.0] 长老已订阅 TASK_COMPLETED 事件")
            else:
                add_log("⚠️ [V2.0] 长老事件订阅跳过（EventBus 不可用）")

            load_tasks_from_store()


def load_tasks_from_store():
    """从SQLite恢复历史任务"""
    try:
        db = get_db()
        rows = db.select_all("tasks", where="status IN ('pending', 'running', 'completed')")
        for row in rows:
            task_id = row["id"]
            if task_id not in st.session_state.tasks:
                st.session_state.tasks[task_id] = {
                    "id": row["id"], "title": row["title"],
                    "description": row["description"], "status": row["status"],
                    "created_at": str(row["created_at"]), "stages": [], "results": []
                }
        if rows:
            add_log(f"📂 从 SQLite 恢复了 {len(rows)} 个历史任务")
    except Exception as e:
        add_log(f"⚠️ 从 SQLite 恢复任务失败: {e}", level="warning")


def auto_wake():
    """启动时自动加载最新配置"""
    try:
        asset_store = AssetStore()
        config = asset_store.load_latest()
        if config:
            st.session_state.saved_config = config
            st.session_state.config_loaded = True
            add_log(f"🔄 自动唤醒上次配置：{config.get('sop_name', '未知SOP')}")
            return config
    except Exception:
        pass
    return None


def save_tasks_to_store():
    """保存任务数据到资产Store"""
    if st.session_state.initialized:
        st.session_state.asset_store.save("tasks", st.session_state.tasks)


def create_task_internal(title: str, description: str = ""):
    """创建新任务"""
    task_id = "task_{}".format(st.session_state.task_id_counter)
    st.session_state.task_id_counter += 1
    st.session_state.tasks[task_id] = {
        "id": task_id, "title": title, "description": description,
        "status": "pending", "created_at": datetime.now().isoformat(),
        "stages": [], "results": [],
    }
    try:
        db = get_db()
        db.save_task({"id": task_id, "title": title,
                     "description": description, "status": "pending"})
    except Exception:
        pass
    save_tasks_to_store()
    add_log("任务创建: {} (ID: {})".format(title, task_id))
    return task_id


# ================================================================
# 主入口
# ================================================================

def main():
    """主渲染入口"""
    inject_css()

    # F11 数据库迁移（确保工作台需要的表存在）
    try:
        ensure_workbench_migrations()
    except Exception as e:
        add_log(f"⚠️ 工作台数据库迁移失败: {e}", level="warning")

    # F9 日程提醒检查
    if "reminder_checked" not in st.session_state:
        st.session_state.reminder_checked = False
    if not st.session_state.reminder_checked:
        try:
            from core.notifier import send_windows_notification
            db = get_db()
            upcoming = db.get_upcoming_reminders(15)
            for item in upcoming:
                try:
                    title_text = item.get("title") or item.get("name", "日程提醒")
                    send_windows_notification(
                        "📅 FROST-SOP 日程提醒",
                        f"{title_text} 即将在 {item.get('start_time', '?')} 开始"
                    )
                    db.mark_schedule_notified(item["id"])
                except Exception:
                    pass
            st.session_state.reminder_checked = True
        except Exception:
            pass

    # F8 决策对话框（仅处理本会话内产生的决策点）
    if "wb_session_start" not in st.session_state:
        # 首次启动：清理所有残留 pending 决策，记录启动时间
        st.session_state.wb_session_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            db = get_db()
            cursor = db.get_connection().cursor()
            cursor.execute(
                "UPDATE decision_points SET status='auto_cancelled', "
                "user_note='应用启动清理', responded_at=? WHERE status='pending'",
                (st.session_state.wb_session_start,)
            )
            db.get_connection().commit()
        except Exception:
            pass
    if st.session_state.get("wb_view") == "dashboard":
        # 仅驾驶舱视图检查决策点（避免其他页面也弹窗）
        render_decision_dialog()

    # 移动端适配
    if is_mobile():
        return render_mobile_view()

    # ========== 侧边栏 ==========
    with st.sidebar:
        render_sidebar()

    # ========== 主区域渲染 ==========
    # 隐藏旧标题（已由导航栏替代），保留家族初始化
    init_family()

    # F6.5 自动唤醒
    if not st.session_state.config_loaded:
        auto_wake()

    view = st.session_state.get("wb_view", "dashboard")

    if view == "dashboard":
        render_commander_dashboard()
    elif view == "project_detail":
        render_project_detail()
    elif view == "daily_review":
        render_daily_review_detail()
    elif view == "schedule":
        render_schedule_page()

    # ========== 底部状态栏（仅在非dashboard视图显示） ==========
    if view != "dashboard":
        st.divider()
        st.caption(f"FROST-SOP F11 · 家族AI指挥平台 · {st.session_state.wb_mode} 模式")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("任务数", st.session_state.task_count)
        with col2:
            st.metric("Token消耗", f"{st.session_state.total_tokens:,}")
        with col3:
            running = sum(1 for t in st.session_state.tasks.values()
                          if t.get("status") == "running")
            st.metric("运行中", running)

        # 任务产出
        if st.session_state.get("task_result"):
            with st.expander("📦 最新任务产出"):
                for i, stage_result in enumerate(st.session_state.task_result):
                    st.write(f"阶段{i + 1}: {stage_result.get('stage', '未知')}")


def render_sidebar():
    """渲染侧边栏（SaaS 专业风格）"""
    # ========== 项目列表 ==========
    st.subheader("📂 项目切换")
    for proj in get_project_defaults():
        is_current = proj["mode"] == st.session_state.wb_mode
        prefix = "●" if is_current else "○"
        if st.button(f"{prefix} {proj['icon']} {proj['name']}", key=f"sidebar_proj_{proj['id']}",
                     use_container_width=True):
            st.session_state.wb_mode = proj["mode"]
            st.session_state.wb_view = "dashboard"
            st.session_state.wb_active_project = None
            st.rerun()

    # ========== 兵器库 ==========
    st.divider()
    st.subheader("🏛️ 兵器库")
    gene_count = _count_gene_templates()
    st.caption(f"教练模板: {gene_count} 个")
    st.caption("雇佣兵: 3 个预置")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔍 浏览模板", use_container_width=True, key="sidebar_browse_templates"):
            st.session_state.show_armory = "templates"
    with col_b:
        if st.button("⚔️ 查看雇佣兵", use_container_width=True, key="sidebar_view_mercenaries"):
            st.session_state.show_armory = "mercenaries"
    if st.session_state.get("show_armory") == "templates":
        _show_armory_templates()
    elif st.session_state.get("show_armory") == "mercenaries":
        _show_mercenaries()

    # ========== 能量状态 ==========
    st.divider()
    render_energy_logger()

    # ========== 导航 ==========
    st.divider()
    nav = st.radio("🧭 导航", ["🎯 指挥官首屏", "📅 日程管理"], key="sidebar_nav")
    if nav == "📅 日程管理":
        st.session_state.wb_view = "schedule"
        st.rerun()
    elif nav == "🎯 指挥官首屏" and st.session_state.wb_view == "schedule":
        st.session_state.wb_view = "dashboard"
        st.rerun()

    # ========== F10 活跃 Skill ==========
    if st.session_state.get("initialized"):
        try:
            db = get_db()
            live_skills = db.execute_sql(
                "SELECT name, skill_type, status FROM skills WHERE status = 'active' LIMIT 10"
            )
            if live_skills:
                st.divider()
                st.subheader("🧠 活跃 Skill")
                for skill in live_skills:
                    st.caption(f"- {skill['name']} ({skill.get('skill_type', '通用')})")
        except Exception:
            pass


# ================================================================
# 启动
# ================================================================
if __name__ == "__main__":
    main()
