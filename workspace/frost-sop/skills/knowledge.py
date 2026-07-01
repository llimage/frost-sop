"""
FROST-SOP 知识归档 Skill
PHILOSOPHY: 家族在执行中积累知识。SOP归档和错题本归档是两个独立的Skill。
归档操作写入资产Store，不修改core/目录。
"""

from core.skill import Skill


def archive_sop(context: dict) -> dict:
    """
    将外部搜索到的有效SOP模板归档到家族资产Store。

    输入 context 键：
        _sop_to_archive: dict —— 待归档的SOP模板
        _sop_source: str —— SOP来源（"web"、"llm_synthesis"、"manual"）
        _asset_store: Store —— 资产Store引用
        _task_id: str（可选）—— 关联的任务ID

    输出 context 键：
        _archive_result: dict —— 归档结果
    """

    sop_data = context.get("_sop_to_archive", {})
    source = context.get("_sop_source", "unknown")
    asset_store = context.get("_asset_store")
    task_id = context.get("_task_id", "unknown")

    if not sop_data or not asset_store:
        context["_archive_result"] = {"success": False, "reason": "缺少SOP数据或资产Store"}
        return context

    sop_id = sop_data.get("sop_id", f"sop_{task_id}")
    sop_name = sop_data.get("name", "未命名SOP")

    import datetime

    archive_record = {
        "sop_id": sop_id,
        "name": sop_name,
        "source": source,
        "content": sop_data,
        "archived_at": str(datetime.datetime.now()),
        "task_id": task_id,
        "usage_count": 0,
        "status": "active",
    }

    asset_store.save(f"sop_template:{sop_id}", archive_record)

    context["_archive_result"] = {
        "success": True,
        "sop_id": sop_id,
        "sop_name": sop_name,
        "message": f"SOP '{sop_name}' 已归档到家族资产Store",
    }
    context["_reason"] = f"SOP归档成功: {sop_name} (来源: {source})"
    return context


def archive_lesson(context: dict) -> dict:
    """
    将父辈执行失败的经验教训归档到错题本。

    输入 context 键：
        _lesson: dict —— 教训记录
            {"task_id": str, "error_type": str, "description": str, "solution": str}
        _asset_store: Store —— 资产Store引用

    输出 context 键：
        _archive_result: dict
    """

    lesson = context.get("_lesson", {})
    asset_store = context.get("_asset_store")

    if not lesson or not asset_store:
        context["_archive_result"] = {"success": False, "reason": "缺少教训数据或资产Store"}
        return context

    task_id = lesson.get("task_id", "unknown")
    error_type = lesson.get("error_type", "unknown")

    import datetime

    lesson_record = {
        "task_id": task_id,
        "error_type": error_type,
        "description": lesson.get("description", ""),
        "solution": lesson.get("solution", ""),
        "recorded_at": str(datetime.datetime.now()),
        "times_encountered": 1,
    }

    existing_key = f"lesson:{task_id}:{error_type}"
    existing = asset_store.load(existing_key)
    if existing:
        existing["times_encountered"] = existing.get("times_encountered", 1) + 1
        existing["solution"] = lesson.get("solution", existing.get("solution", ""))
        asset_store.save(existing_key, existing)
    else:
        asset_store.save(existing_key, lesson_record)

    context["_archive_result"] = {
        "success": True,
        "lesson_key": existing_key,
        "message": "教训已归档到错题本",
    }
    context["_reason"] = f"错题本归档: {error_type} (任务: {task_id})"
    return context


def query_lessons(context: dict) -> dict:
    """
    查询错题本中与当前任务相关的教训。

    输入 context 键：
        _error_type: str（可选）—— 按错误类型过滤
        _asset_store: Store

    输出 context 键：
        _lessons: list —— 匹配的教训列表
    """

    error_type = context.get("_error_type", "")
    asset_store = context.get("_asset_store")

    if not asset_store:
        context["_lessons"] = []
        return context

    all_keys = asset_store.list_keys()
    lessons = []
    for key in all_keys:
        if key.startswith("lesson:"):
            lesson_data = asset_store.load(key)
            if lesson_data:
                if (
                    not error_type
                    or error_type.lower() in lesson_data.get("error_type", "").lower()
                ):
                    lessons.append(lesson_data)

    lessons.sort(key=lambda x: x.get("times_encountered", 0), reverse=True)
    context["_lessons"] = lessons[:10]
    context["_reason"] = f"查询错题本: 找到{len(context['_lessons'])}条相关教训"
    return context


archive_sop_skill = Skill("archive_sop", archive_sop)
archive_lesson_skill = Skill("archive_lesson", archive_lesson)
query_lessons_skill = Skill("query_lessons", query_lessons)
