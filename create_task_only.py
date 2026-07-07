"""
FROST-SOP 任务创建工具
绕过API层，直接创建任务记录（不立即执行）
"""

import sys
from datetime import datetime
from pathlib import Path

# 确保frost-sop根目录在Python路径中
frost_sop_path = Path(__file__).parent / "workspace" / "frost-sop"
sys.path.insert(0, str(frost_sop_path))

from core.db import get_db  # noqa: E402


def create_task_only(
    description: str, sop_id: str = "DEV-001", project_id: str = "default"
):
    """
    只创建任务记录，不执行SOP

    参数:
        description: 任务描述
        sop_id: SOP模板ID
        project_id: 项目ID

    返回:
        任务ID
    """
    import uuid

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    db = get_db()

    # 确保项目存在
    existing = db.select_one("projects", "id", project_id)
    if not existing:
        db.insert(
            "projects",
            {
                "id": project_id,
                "name": "默认项目",
                "description": "FROST-SOP默认项目",
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
        )

    # 创建任务记录（状态为pending，不执行）
    db.insert(
        "tasks",
        {
            "id": task_id,
            "title": description[:60],
            "description": description,
            "project_id": project_id,
            "status": "pending",  # 关键：设置为pending，不立即执行
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
    )

    print(f"✅ 任务已创建：{task_id}")
    print(f"   描述：{description}")
    print(f"   SOP：{sop_id}")
    print("   状态：pending（待执行）")
    print("\n可以通过API或界面手动触发执行。")

    return task_id


if __name__ == "__main__":
    # 演示：创建一个"狩猎任务"
    task_id = create_task_only(
        description="狩猎任务：关于长上下文记忆管理、有效精简历史消息、减少token消耗方面的优秀的实践和skill",
        sop_id="STR-001",
        project_id="default",
    )
    print(f"\n任务ID: {task_id}")
