"""
F11 项目工作台核心模块
PHILOSOPHY: 工作台是新界面+旧数据，不新建表，复用现有 F6-F10 数据层。

职责：
1. 项目上下文管理（三线切换：SaaS/专栏/咨询）
2. 能量感知任务推荐
3. 日终回顾叙事生成
4. 项目级配置快照
"""

import json
import os
from datetime import datetime, date
from typing import Dict, Any, Optional, List

from core.db import get_db


# ================================================================
# 项目配置常量（李明远的三个项目）
# ================================================================
DEFAULT_PROJECTS = [
    {
        "id": "saas",
        "name": "轻云SaaS",
        "icon": "🔧",
        "mode": "dev",
        "mode_label": "开发模式",
        "mode_icon": "🔧",
        "sop_template": "DEV-001",
        "description": "效率工具 SaaS 产品迭代与维护",
        "color": "#FB6B4B",  # 珊瑚橙
        "revenue_monthly": 34200,
    },
    {
        "id": "column",
        "name": "技术专栏",
        "icon": "✍️",
        "mode": "create",
        "mode_label": "创作模式",
        "mode_icon": "✍️",
        "sop_template": "MT-001",
        "description": "技术付费专栏内容创作与发布",
        "color": "#2D6A4F",  # 墨绿
        "revenue_monthly": 6000,
    },
    {
        "id": "consult",
        "name": "企业咨询",
        "icon": "💼",
        "mode": "client",
        "mode_label": "客户模式",
        "mode_icon": "💼",
        "sop_template": "OPS-001",
        "description": "企业咨询服务交付与客户管理",
        "color": "#2563EB",  # 蓝
        "revenue_monthly": 15000,
    },
]

PROJECT_BY_MODE = {p["mode"]: p for p in DEFAULT_PROJECTS}
PROJECT_BY_ID = {p["id"]: p for p in DEFAULT_PROJECTS}


def get_project_defaults() -> List[Dict]:
    """获取默认项目列表"""
    return DEFAULT_PROJECTS


def get_project_by_mode(mode: str) -> Optional[Dict]:
    """按模式获取项目"""
    return PROJECT_BY_MODE.get(mode)


def get_project_by_id(pid: str) -> Optional[Dict]:
    """按ID获取项目"""
    return PROJECT_BY_ID.get(pid)


def ensure_default_projects():
    """确保默认项目存在于数据库"""
    db = get_db()
    for proj in DEFAULT_PROJECTS:
        existing = db.select_one("projects", "id", proj["id"])
        if not existing:
            db.insert("projects", {
                "id": proj["id"],
                "name": proj["name"],
                "description": proj.get("description", ""),
                "status": "active",
                "sop_template": proj.get("sop_template", ""),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "last_active_at": datetime.now().isoformat(),
                "energy_level": 100.0,
                "config_ref": "",
                "metadata": json.dumps(proj, ensure_ascii=False),
            })


def ensure_workbench_migrations():
    """确保工作台需要的数据库迁移（扩展 projects 表）"""
    db = get_db()
    conn = db.get_connection()
    cursor = conn.cursor()

    # 获取 projects 表现有列
    existing_cols = {col["name"] for col in cursor.execute("PRAGMA table_info(projects)").fetchall()}

    needed_cols = {
        "sop_template": "TEXT DEFAULT ''",
        "energy_level": "REAL DEFAULT 100.0",
        "config_ref": "TEXT DEFAULT ''",
        "metadata": "TEXT DEFAULT '{}'",
        "last_active_at": "TIMESTAMP",
    }
    for col_name, col_def in needed_cols.items():
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    # 创建 project_skills 关联表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_skills (
        project_id TEXT NOT NULL,
        skill_id TEXT NOT NULL,
        activated_at TEXT NOT NULL,
        usage_count INTEGER DEFAULT 0,
        PRIMARY KEY (project_id, skill_id)
    )
    """)

    # 创建 config_snapshots 表（F6.5 项目级快照）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        snapshot_name TEXT NOT NULL,
        task_description TEXT DEFAULT '',
        sop_state TEXT DEFAULT '{}',
        available_skills TEXT DEFAULT '[]',
        created_at TEXT NOT NULL
    )
    """)

    # 创建 daily_reviews 表（日终回顾）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_date TEXT NOT NULL UNIQUE,
        narrative TEXT DEFAULT '',
        energy_high REAL,
        energy_low REAL,
        energy_avg REAL,
        achievements TEXT DEFAULT '[]',
        confirmed BOOLEAN DEFAULT 0,
        created_at TEXT NOT NULL,
        confirmed_at TEXT
    )
    """)

    conn.commit()
    # 初始化默认项目
    ensure_default_projects()


# ================================================================
# 能量感知任务推荐
# ================================================================
def get_recommended_task(mode: str = "dev") -> Dict[str, Any]:
    """
    根据当前模式和能量状态，推荐最佳任务。

    Args:
        mode: 当前模式 (dev/create/client)

    Returns:
        推荐任务字典，包含 task_name, progress, duration, energy_match, alternatives
    """
    db = get_db()
    proj = get_project_by_mode(mode)
    if not proj:
        return _fallback_task(mode)

    # 获取最新能量
    energy = db.get_latest_energy()
    energy_level = energy.get("level", 50) if energy else 50

    # 获取该项目的任务列表
    tasks = db.select_all("tasks", where="project_id = ? AND status != 'completed'",
                          params=[proj["id"]])
    
    # 简化的推荐逻辑：按紧急度和能量匹配排序
    recommended = _build_task_recommendation(proj, tasks, energy_level, mode)
    return recommended


def _build_task_recommendation(proj: Dict, tasks: List[Dict], energy_level: int, mode: str) -> Dict:
    """构建任务推荐"""
    # 模拟任务数据
    task_scenarios = {
        "dev": {
            "task_name": "实现用户权限管理的 RBAC 模块",
            "progress": 65,
            "duration": "2.5h",
            "phase": "Phase 3/5 · 代码实现",
        },
        "create": {
            "task_name": "撰写本周专栏文章：《AI Agent 架构实践》",
            "progress": 30,
            "duration": "1.5h",
            "phase": "Phase 2/4 · 内容创作",
        },
        "client": {
            "task_name": "回复客户张总的技术方案咨询",
            "progress": 0,
            "duration": "1h",
            "phase": "Phase 1/3 · 需求沟通",
        },
    }

    scenario = task_scenarios.get(mode, task_scenarios["dev"])

    # 能量匹配
    if energy_level >= 60:
        energy_match = "match"
        match_text = "匹配当前能量 🟢"
    elif energy_level >= 30:
        energy_match = "partial"
        match_text = "能量略低，建议简化 🟡"
    else:
        energy_match = "mismatch"
        match_text = "建议先休息再开始 🔴"

    alternatives = {
        "dev": [
            {"name": "修复 SaaS 登录页样式 bug", "duration": "1h"},
            {"name": "更新 API 文档", "duration": "0.5h"},
            {"name": "Review 上周代码 PR", "duration": "1.5h"},
        ],
        "create": [
            {"name": "整理专栏读者反馈", "duration": "0.5h"},
            {"name": "策划下月选题方向", "duration": "1h"},
            {"name": "更新往期文章索引", "duration": "0.5h"},
        ],
        "client": [
            {"name": "准备周五咨询演示 PPT", "duration": "2h"},
            {"name": "更新客户 CRM 记录", "duration": "0.5h"},
            {"name": "整理上月咨询案例", "duration": "1h"},
        ],
    }

    return {
        "project_id": proj["id"],
        "project_name": proj["name"],
        "project_icon": proj["icon"],
        "mode": mode,
        "task_name": scenario["task_name"],
        "progress": scenario["progress"],
        "duration": scenario["duration"],
        "phase": scenario["phase"],
        "energy_match": energy_match,
        "match_text": match_text,
        "energy_level": energy_level,
        "alternatives": alternatives.get(mode, []),
        "sop_template": proj.get("sop_template", ""),
    }


def _fallback_task(mode: str) -> Dict:
    """当没有数据时的回退任务"""
    return {
        "project_id": mode,
        "project_name": "未命名项目",
        "project_icon": "📋",
        "mode": mode,
        "task_name": "开始一个新任务",
        "progress": 0,
        "duration": "—",
        "phase": "待启动",
        "energy_match": "match",
        "match_text": "新任务随时可以开始",
        "energy_level": 50,
        "alternatives": [],
        "sop_template": "",
    }


# ================================================================
# 日终回顾
# ================================================================
def get_today_review() -> Optional[Dict]:
    """获取今日的日终回顾记录"""
    db = get_db()
    today_str = date.today().isoformat()
    return db.select_one("daily_reviews", "review_date", today_str)


def generate_daily_narrative() -> str:
    """
    生成今日叙事总结（模拟 LLM 生成）。

    Returns:
        叙事文本
    """
    db = get_db()
    today_str = date.today().isoformat()

    # 获取今日任务完成情况
    tasks_today = len(db.select_all("tasks",
        where="date(updated_at) = date('now', 'localtime') AND status = 'completed'"))

    # 获取今日能量数据
    energy_data = db.execute_sql("""
        SELECT AVG(level) as avg_energy, MIN(level) as min_energy, MAX(level) as max_energy
        FROM energy_log
        WHERE date(timestamp) = date('now', 'localtime')
    """)
    
    avg_e = energy_data[0]["avg_energy"] if energy_data and energy_data[0]["avg_energy"] else 0
    max_e = energy_data[0]["max_energy"] if energy_data and energy_data[0]["max_energy"] else 0
    min_e = energy_data[0]["min_energy"] if energy_data and energy_data[0]["min_energy"] else 0

    # 获取今日成本
    cost_data = db.execute_sql("""
        SELECT COALESCE(SUM(estimated_cost), 0) as total
        FROM cost_log
        WHERE date(timestamp) = date('now', 'localtime')
    """)
    today_cost = cost_data[0]["total"] if cost_data else 0

    # 生成叙事
    narratives = []
    narratives.append(f"📅 {today_str} 工作回顾")
    narratives.append("")

    if tasks_today > 0:
        narratives.append(f"今天你完成了 {tasks_today} 个任务，持续推进着项目的前进。")
    else:
        narratives.append("今天虽然没有标记完成的任务，但思考和规划本身也是重要的工作。")

    if avg_e > 0:
        narratives.append(f"今日能量均值 {avg_e:.0f}%，峰值达到 {max_e:.0f}%。")
        if avg_e > 70:
            narratives.append("今天的状态非常不错，保持了高效产出。")
        elif avg_e > 40:
            narratives.append("能量状态平稳，节奏控制得当。")
        else:
            narratives.append("能量偏低的一天，休息也是一种生产力。")

    if today_cost > 0:
        narratives.append(f"今日 AI 成本约 ¥{today_cost:.2f}，投入产出比良好。")

    narratives.append("")
    narratives.append("💡 给明天的小建议：")
    if avg_e > 70:
        narratives.append("明天可以挑战更难的任务，趁状态好的时候攻坚。")
    else:
        narratives.append("明天先从一个小任务开始热身，再进入核心工作。")

    return "\n".join(narratives)


def save_daily_review(narrative: str = None, confirmed: bool = False) -> int:
    """
    保存日终回顾

    Args:
        narrative: 叙事总结（None 则自动生成）
        confirmed: 是否确认打卡

    Returns:
        记录 ID
    """
    db = get_db()
    today_str = date.today().isoformat()

    # 获取今日能量数据
    energy_data = db.execute_sql("""
        SELECT AVG(level) as avg_energy, MIN(level) as min_energy, MAX(level) as max_energy
        FROM energy_log
        WHERE date(timestamp) = date('now', 'localtime')
    """)

    avg_e = energy_data[0]["avg_energy"] if energy_data and energy_data[0]["avg_energy"] else 0
    max_e = energy_data[0]["max_energy"] if energy_data and energy_data[0]["max_energy"] else 0
    min_e = energy_data[0]["min_energy"] if energy_data and energy_data[0]["min_energy"] else 0

    if narrative is None:
        narrative = generate_daily_narrative()

    existing = db.select_one("daily_reviews", "review_date", today_str)
    if existing:
        db.update("daily_reviews", "review_date", today_str, {
            "narrative": narrative,
            "energy_high": max_e,
            "energy_low": min_e,
            "energy_avg": avg_e,
            "confirmed": 1 if confirmed else existing.get("confirmed", 0),
            "confirmed_at": datetime.now().isoformat() if confirmed else existing.get("confirmed_at"),
        })
        return existing["id"]

    return db.insert("daily_reviews", {
        "review_date": today_str,
        "narrative": narrative,
        "energy_high": max_e,
        "energy_low": min_e,
        "energy_avg": avg_e,
        "achievements": "[]",
        "confirmed": 1 if confirmed else 0,
        "created_at": datetime.now().isoformat(),
        "confirmed_at": datetime.now().isoformat() if confirmed else None,
    })


# ================================================================
# 项目级配置快照（F6.5 升级）
# ================================================================
def save_project_snapshot(project_id: str, task_desc: str, sop_state: Dict,
                          skills: List[str], snapshot_name: str = None) -> int:
    """保存项目级配置快照"""
    db = get_db()
    if snapshot_name is None:
        snapshot_name = f"自动快照 {datetime.now().strftime('%m/%d %H:%M')}"

    return db.insert("config_snapshots", {
        "project_id": project_id,
        "snapshot_name": snapshot_name,
        "task_description": task_desc,
        "sop_state": json.dumps(sop_state, ensure_ascii=False),
        "available_skills": json.dumps(skills, ensure_ascii=False),
        "created_at": datetime.now().isoformat(),
    })


def load_project_snapshots(project_id: str) -> List[Dict]:
    """加载项目所有配置快照"""
    db = get_db()
    return db.select_all("config_snapshots",
                         where="project_id = ?",
                         params=[project_id])


# ================================================================
# 业务雷达数据
# ================================================================
def get_business_radar_data() -> List[Dict]:
    """获取三条业务线的雷达数据"""
    db = get_db()
    radar = []

    for proj in DEFAULT_PROJECTS:
        # 活跃任务数
        active_tasks = len(db.select_all("tasks",
            where="project_id = ? AND status != 'completed'",
            params=[proj["id"]]))

        # 本月收入（模拟数据）
        revenue = proj.get("revenue_monthly", 0)

        radar.append({
            "id": proj["id"],
            "name": proj["name"],
            "icon": proj["icon"],
            "color": proj["color"],
            "active_tasks": active_tasks,
            "revenue_monthly": revenue,
            "status": "active" if active_tasks > 0 else "idle",
            "mode": proj["mode"],
        })

    return radar
