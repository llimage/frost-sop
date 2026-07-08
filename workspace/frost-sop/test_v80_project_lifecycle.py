"""
FROST-SOP V8.0 — 项目生命周期测试

测试范围：
1. Project 实体创建和状态流转
2. ProjectStore 存储和检索
3. ProjectManager 路由逻辑（新任务 vs 已有项目对话）
4. TaskParentAgent 基础行为（不测试 LLM 调用）
"""

import os
os.environ["FROST_TESTING"] = "1"

import sys
sys.path.insert(0, r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop')
sys.path.insert(0, r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop')

import uuid
from datetime import datetime

from core.project import Project, ProjectStore
from skills.strategy.project_manager import ProjectManager
from agents.task_parent import TaskParentAgent
sys.path.insert(0, r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop')

import uuid
from datetime import datetime


def test_project_entity():
    """测试 Project 实体的创建和状态流转。"""
    print("\n【测试1】Project 实体")

    project = Project(
        id="proj_test_001",
        name="心理健康服务",
        raw_input="我要做心理健康服务",
        status="created",
    )

    assert project.id == "proj_test_001"
    assert project.status == "created"
    assert project.vision is None

    # 状态流转
    project.update_status("vision_aligned")
    assert project.status == "vision_aligned"
    assert project.vision is None  # 状态变了，但愿景还没设置

    project.vision = "为25-35岁职场女性提供轻量级在线心理支持"
    project.update_status("executing")
    assert project.status == "executing"

    project.update_status("completed")
    assert project.status == "completed"
    assert project.completed_at is not None

    print("  ✅ Project 实体创建和状态流转正常")
    return True


def test_project_store():
    """测试 ProjectStore 存储和检索。"""
    print("\n【测试2】ProjectStore")

    # 使用临时存储
    store = ProjectStore()

    # 创建项目
    project = Project(
        id="proj_test_002",
        name="视频剪辑工具",
        raw_input="我要做自动化视频剪辑",
        status="created",
    )

    # 保存
    store.save(project)

    # 加载
    loaded = store.load("proj_test_002")
    assert loaded is not None
    assert loaded.name == "视频剪辑工具"
    assert loaded.status == "created"

    # 列出活跃项目
    active = store.list_active()
    assert len(active) == 1
    assert active[0].id == "proj_test_002"

    # 完成项目后不应在活跃列表中
    project.update_status("completed")
    store.save(project)
    active = store.list_active()
    assert len(active) == 0  # completed 不是活跃状态

    print("  ✅ ProjectStore 存储和检索正常")
    return True


def test_project_manager_new_task():
    """测试 ProjectManager 创建新项目。"""
    print("\n【测试3】ProjectManager - 新任务")

    # 使用全新的 Store（无活跃项目）
    store = ProjectStore()
    pm = ProjectManager(project_store=store)

    # 模拟使用者输入
    result = pm.handle_input("我要做心理健康服务")

    assert result["action"] == "created"
    assert "project_id" in result
    project_id = result["project_id"]

    # 验证项目已创建
    project = store.load(project_id)
    assert project is not None
    assert project.name == "我要做心理健康服务"[:30]
    assert project.status == "vision_aligned"  # handle_new_task 已调用 _align_vision

    # 验证项目负责人已任命
    assert project.parent_agent_id == f"parent_{project_id}"

    print(f"  ✅ 新项目创建: {project_id}, 状态: {project.status}")
    return True
    project = store.load(project_id)
    assert project is not None
    assert project.name == "我要做心理健康服务"[:30]
    assert project.status == "vision_aligned"  # handle_new_task 已调用 _align_vision
    project = store.load(project_id)
    assert project is not None
    assert project.name == "我要做心理健康服务"[:30]
    assert project.status == "vision_aligning"  # 创建后自动进入愿景对齐

    # 验证项目负责人已任命
    assert project.parent_agent_id == f"parent_{project_id}"

    print(f"  ✅ 新项目创建: {project_id}, 状态: {project.status}")
    return True


def test_project_manager_routing():
    """测试 ProjectManager 路由到已有项目。"""
    print("\n【测试4】ProjectManager - 路由到已有项目")

    store = ProjectStore()
    pm = ProjectManager(project_store=store)

    # 先创建一个项目
    result1 = pm.handle_input("我要做心理健康服务")
    project_id = result1["project_id"]

    # 模拟项目内对话（无新任务关键词）
    result2 = pm.handle_input("进度怎么样？")

    assert result2["action"] == "routed"
    assert result2["project_id"] == project_id

    print(f"  ✅ 消息路由到项目: {project_id}")
    return True


def test_project_manager_multiple_projects():
    """测试多个活跃项目时的匹配逻辑。"""
    print("\n【测试5】ProjectManager - 多项目匹配")

    store = ProjectStore()
    pm = ProjectManager(project_store=store)

    # 创建两个项目
    result1 = pm.handle_input("我要做心理健康服务")
    proj1_id = result1["project_id"]

    # 修改第一个项目的状态为 completed，这样它不会被视为活跃
    proj1 = store.load(proj1_id)
    proj1.update_status("completed")
    store.save(proj1)

    result2 = pm.handle_input("我要做视频剪辑工具")
    proj2_id = result2["project_id"]

    # 现在只有一个活跃项目（视频剪辑）
    result3 = pm.handle_input("进度怎么样？")
    assert result3["action"] == "routed"
    assert result3["project_id"] == proj2_id

    print(f"  ✅ 多项目匹配正确，路由到: {proj2_id}")
    return True


def test_task_parent_agent_basic():
    """测试 TaskParentAgent 基础行为（mock LLM）。"""
    print("\n【测试6】TaskParentAgent - 基础行为")

    project = Project(
        id="proj_test_003",
        name="测试项目",
        raw_input="测试",
        status="created",
    )

    store = ProjectStore()
    parent = TaskParentAgent(project=project, project_store=store)

    assert parent.agent_id == "parent_proj_test_003"

    # 处理新任务
    parent.handle_new_task("我要做测试任务")
    assert project.status == "vision_aligned"  # _align_vision 已执行完成
    assert project.raw_input == "我要做测试任务"

    # 模拟愿景对齐完成（手动设置，跳过 LLM）
    project.vision = "为测试用户提供测试服务"
    project.update_status("vision_aligned")
    store.save(project)

    assert project.status == "vision_aligned"
    assert project.vision is not None

    # 处理项目内消息 - 状态查询
    parent.handle_user_message("进度怎么样？")
    # 状态查询会记录到 chat_history
    assert "chat_history" in project.context

    # 处理愿景更新
    parent.handle_user_message("改成大学生用户")
    assert "大学生" in project.vision

    print(f"  ✅ TaskParentAgent 基础行为正常")
    return True
    parent.handle_new_task("我要做测试任务")
    assert project.status == "vision_aligned"  # _align_vision 已执行完成
    assert project.raw_input == "我要做测试任务"
    parent.handle_new_task("我要做测试任务")
    assert project.status == "vision_aligning"
    assert project.raw_input == "我要做测试任务"

    # 模拟愿景对齐完成（手动设置，跳过 LLM）
    project.vision = "为测试用户提供测试服务"
    project.update_status("vision_aligned")
    store.save(project)

    assert project.status == "vision_aligned"
    assert project.vision is not None

    # 处理项目内消息 - 状态查询
    parent.handle_user_message("进度怎么样？")
    # 状态查询会记录到 chat_history
    assert "chat_history" in project.context

    # 处理愿景更新
    parent.handle_user_message("改成大学生用户")
    assert "大学生" in project.vision

    print(f"  ✅ TaskParentAgent 基础行为正常")
    return True


def test_project_to_dict():
    """测试 Project 序列化和反序列化。"""
    print("\n【测试7】Project 序列化")

    project = Project(
        id="proj_test_004",
        name="序列化测试",
        raw_input="测试",
        vision="测试愿景",
        status="executing",
        context={"key": "value"},
    )

    # 序列化
    d = project.to_dict()
    assert d["id"] == "proj_test_004"
    assert d["status"] == "executing"
    assert d["context"]["key"] == "value"

    # 反序列化
    restored = Project.from_dict(d)
    assert restored.id == "proj_test_004"
    assert restored.vision == "测试愿景"

    print("  ✅ Project 序列化/反序列化正常")
    return True


# ── 主函数 ──

def main():
    print("=" * 60)
    print("【V8.0 项目生命周期测试】")
    print("=" * 60)

    results = []

    try:
        results.append(("Project实体", test_project_entity()))
    except Exception as e:
        print(f"  ❌ Project实体测试失败: {e}")
        results.append(("Project实体", False))

    try:
        results.append(("ProjectStore", test_project_store()))
    except Exception as e:
        print(f"  ❌ ProjectStore测试失败: {e}")
        results.append(("ProjectStore", False))

    try:
        results.append(("ProjectManager-新任务", test_project_manager_new_task()))
    except Exception as e:
        print(f"  ❌ ProjectManager新任务测试失败: {e}")
        results.append(("ProjectManager-新任务", False))

    try:
        results.append(("ProjectManager-路由", test_project_manager_routing()))
    except Exception as e:
        print(f"  ❌ ProjectManager路由测试失败: {e}")
        results.append(("ProjectManager-路由", False))

    try:
        results.append(("ProjectManager-多项目", test_project_manager_multiple_projects()))
    except Exception as e:
        print(f"  ❌ ProjectManager多项目测试失败: {e}")
        results.append(("ProjectManager-多项目", False))

    try:
        results.append(("TaskParentAgent", test_task_parent_agent_basic()))
    except Exception as e:
        print(f"  ❌ TaskParentAgent测试失败: {e}")
        results.append(("TaskParentAgent", False))

    try:
        results.append(("Project序列化", test_project_to_dict()))
    except Exception as e:
        print(f"  ❌ Project序列化测试失败: {e}")
        results.append(("Project序列化", False))

    # 汇总
    print("\n" + "=" * 60)
    print("【最终结论】")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")

    print(f"\n总计: {total} 项 | 通过: {passed} | 失败: {total - passed}")

    if passed == total:
        print("\n🎉 V8.0 项目生命周期架构验证通过！")
    else:
        print(f"\n⚠️ {total - passed} 项测试失败，需要修复。")


if __name__ == "__main__":
    main()
