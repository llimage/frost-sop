"""
FROST-SOP 测试数据工厂 (Data Factories)

使用 Faker + Factory Boy 自动生成测试数据，
覆盖边界值、特殊字符、超长字段等手工测试难以穷举的场景。

用法:
    from tests.factories import TaskConfigFactory, SOPTemplateFactory

    config = TaskConfigFactory()           # 随机数据
    config = TaskConfigFactory(task_input="Fix bug")  # 指定字段
    configs = TaskConfigFactory.create_batch(10)      # 批量生成
"""

import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any

import factory
from faker import Faker

faker = Faker(["zh_CN", "en_US"])


# ──────────────────────────────────────────────────────────────
# 基础值生成器
# ──────────────────────────────────────────────────────────────

def random_task_id() -> str:
    """生成随机任务 ID (task: 前缀 + UUID)。"""
    return f"task:{uuid.uuid4().hex[:12]}"


def random_agent_id() -> str:
    """生成随机 Agent ID。"""
    return f"agent_{uuid.uuid4().hex[:8]}"


def random_sop_id() -> str:
    """生成随机 SOP 模板 ID。"""
    prefixes = ["DEV", "OPS", "STR", "MT"]
    return f"{random.choice(prefixes)}-{faker.random_int(1, 999):03d}"


def random_skill_id() -> str:
    """生成随机 Skill ID。"""
    return f"skill_{faker.word()}_{int(datetime.now().timestamp() * 1000)}"


def boundary_string(length: int = 255) -> str:
    """生成边界长度字符串（含中文、特殊字符）。"""
    base = faker.text(max_nb_chars=length)
    # 确保包含中文和特殊字符
    if len(base) < length:
        base += "测试🧪边界!"
    return base[:length]


def unicode_text() -> str:
    """生成含 emoji、特殊 Unicode 的文本。"""
    return f"{faker.sentence()} 🚀 {faker.word()} \u2665 \u2603"


def empty_or_whitespace() -> str:
    """生成空字符串或纯空白字符串。"""
    return random.choice(["", "   ", "\t", "\n"])


# ──────────────────────────────────────────────────────────────
# Task 任务工厂
# ──────────────────────────────────────────────────────────────

class TaskConfigFactory(factory.Factory):
    """任务配置工厂 — 覆盖正常、边界、异常值。"""

    class Meta:
        model = dict

    task_id = factory.LazyFunction(random_task_id)
    task_input = factory.LazyFunction(lambda: faker.sentence(nb_words=8))
    sop_id = factory.LazyFunction(random_sop_id)
    created_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    status = "pending"

    class Params:
        # 边界值变体
        as_minimal = factory.Trait(
            task_input="x",
            sop_id="DEV-001",
        )
        as_verbose = factory.Trait(
            task_input=factory.LazyFunction(
                lambda: faker.text(max_nb_chars=2000)
            ),
            sop_id=factory.LazyFunction(random_sop_id),
        )
        as_unicode = factory.Trait(
            task_input=factory.LazyFunction(unicode_text),
        )
        as_empty = factory.Trait(
            task_input=factory.LazyFunction(empty_or_whitespace),
        )
        as_completed = factory.Trait(
            status="completed",
        )
        as_failed = factory.Trait(
            status="failed",
        )


# ──────────────────────────────────────────────────────────────
# Agent 装配配置工厂
# ──────────────────────────────────────────────────────────────

class AgentConfigFactory(factory.Factory):
    """孙辈 Agent 装配配置工厂。"""

    class Meta:
        model = dict

    agent_id = factory.LazyFunction(random_agent_id)
    name = factory.LazyFunction(lambda: f"孙辈Agent-{faker.word().title()}")
    role = factory.LazyFunction(
        lambda: random.choice(["分析员", "工程师", "测试员", "审查员", "设计员"])
    )
    assigned_skills = factory.LazyFunction(
        lambda: [random_skill_id() for _ in range(faker.random_int(1, 5))]
    )
    parent_id = "parent_agent"
    model = "gpt-4"
    temperature = factory.LazyFunction(lambda: round(random.uniform(0.0, 1.0), 2))

    class Params:
        as_minimal = factory.Trait(
            assigned_skills=["skill_gene:basic"],
            temperature=0.0,
        )
        as_maximal = factory.Trait(
            assigned_skills=factory.LazyFunction(
                lambda: [random_skill_id() for _ in range(20)]
            ),
            temperature=1.0,
        )


# ──────────────────────────────────────────────────────────────
# SOP 模板工厂
# ──────────────────────────────────────────────────────────────

class SOPPhaseFactory(factory.Factory):
    """SOP 阶段工厂。"""

    class Meta:
        model = dict

    phase_id = factory.LazyFunction(
        lambda: f"phase_{faker.random_int(1, 20):02d}"
    )
    name = factory.LazyFunction(lambda: faker.catch_phrase())
    description = factory.LazyFunction(lambda: faker.text(max_nb_chars=200))
    inputs = factory.LazyFunction(lambda: [faker.word() for _ in range(3)])
    outputs = factory.LazyFunction(lambda: [faker.word() for _ in range(2)])
    skill = factory.LazyFunction(random_skill_id)


class SOPTemplateFactory(factory.Factory):
    """SOP 模板工厂。"""

    class Meta:
        model = dict

    sop_id = factory.LazyFunction(random_sop_id)
    name = factory.LazyFunction(lambda: faker.catch_phrase())
    version = "1.0.0"
    description = factory.LazyFunction(lambda: faker.paragraph(nb_sentences=3))
    phases = factory.LazyFunction(
        lambda: [SOPPhaseFactory() for _ in range(faker.random_int(3, 7))]
    )

    class Params:
        as_5_phase = factory.Trait(
            phases=factory.LazyFunction(lambda: [SOPPhaseFactory() for _ in range(5)]),
        )
        as_single_phase = factory.Trait(
            phases=factory.LazyFunction(lambda: [SOPPhaseFactory()]),
        )


# ──────────────────────────────────────────────────────────────
# Skill 技能工厂
# ──────────────────────────────────────────────────────────────

class SkillConfigFactory(factory.Factory):
    """Skill 技能配置工厂。"""

    class Meta:
        model = dict

    id = factory.LazyFunction(random_skill_id)
    name = factory.LazyFunction(lambda: f"skill_gene:{faker.word()}")
    status = factory.LazyFunction(
        lambda: random.choice(["draft", "active", "rejected"])
    )
    success_rate = factory.LazyFunction(lambda: round(random.uniform(0.0, 1.0), 2))
    trigger_keywords = factory.LazyFunction(
        lambda: faker.words(nb=faker.random_int(3, 8))
    )
    task_type = factory.LazyFunction(
        lambda: random.choice(
            ["code_review", "data_analysis", "text_generation", "testing", "design"]
        )
    )
    description = factory.LazyFunction(lambda: faker.text(max_nb_chars=300))

    class Params:
        as_active_high_quality = factory.Trait(
            status="active",
            success_rate=0.95,
        )
        as_draft = factory.Trait(
            status="draft",
            success_rate=0.0,
        )
        as_rejected = factory.Trait(
            status="rejected",
            success_rate=0.0,
        )
        as_low_quality = factory.Trait(
            status="active",
            success_rate=0.1,
        )


# ──────────────────────────────────────────────────────────────
# Event 事件工厂
# ──────────────────────────────────────────────────────────────

class EventFactory(factory.Factory):
    """EventBus 事件工厂。"""

    class Meta:
        model = dict

    event_id = factory.LazyFunction(lambda: f"evt_{uuid.uuid4().hex[:8]}")
    event_type = factory.LazyFunction(
        lambda: random.choice(
            [
                "task.created",
                "task.completed",
                "task.failed",
                "phase.started",
                "phase.completed",
                "agent.assembled",
                "skill.activated",
            ]
        )
    )
    source = factory.LazyFunction(random_agent_id)
    timestamp = factory.LazyFunction(lambda: datetime.now().isoformat())
    payload = factory.LazyFunction(
        lambda: {"data": faker.text(max_nb_chars=100), "meta": {"version": "1.0"}}
    )

    class Params:
        as_error_event = factory.Trait(
            event_type="task.failed",
            payload=factory.LazyFunction(
                lambda: {
                    "error": faker.text(max_nb_chars=200),
                    "code": faker.random_int(400, 599),
                }
            ),
        )
        as_complex_payload = factory.Trait(
            payload=factory.LazyFunction(
                lambda: {
                    "nested": {
                        "data": [faker.word() for _ in range(10)],
                        "deep": {"very": {"deep": faker.sentence()}},
                    }
                }
            ),
        )


# ──────────────────────────────────────────────────────────────
# Store 键值对工厂
# ──────────────────────────────────────────────────────────────

class StoreEntryFactory(factory.Factory):
    """Store 键值对工厂 — 覆盖正常值和边界异常值。"""

    class Meta:
        model = dict

    key = factory.LazyFunction(
        lambda: f"{random.choice(['task', 'lesson', 'config'])}:{uuid.uuid4().hex[:8]}"
    )
    value = factory.LazyFunction(
        lambda: faker.pydict(nb_elements=faker.random_int(1, 5), value_types=[str, int, float, bool])
    )
    namespace = "default"
    readonly = False

    class Params:
        as_readonly = factory.Trait(
            key="constitution:immutable_rule",
            readonly=True,
        )
        as_large_value = factory.Trait(
            value=factory.LazyFunction(
                lambda: {"text": faker.text(max_nb_chars=10000)}
            ),
        )
        as_special_chars_key = factory.Trait(
            key="task:test-😀-unicode-key",
        )
        as_empty_value = factory.Trait(
            value={},
        )


# ──────────────────────────────────────────────────────────────
# 便利函数
# ──────────────────────────────────────────────────────────────

def create_batch(factory_class: type[factory.Factory], size: int = 10, **kwargs) -> list[dict[str, Any]]:
    """创建一批随机测试数据。

    Args:
        factory_class: 工厂类
        size: 批量大小
        **kwargs: 覆盖字段

    Returns:
        测试数据字典列表
    """
    return factory_class.create_batch(size, **kwargs)


def create_edge_case_task_configs() -> list[dict[str, Any]]:
    """创建覆盖所有边界场景的任务配置列表。"""
    return [
        TaskConfigFactory(),
        TaskConfigFactory(as_minimal=True),
        TaskConfigFactory(as_verbose=True),
        TaskConfigFactory(as_unicode=True),
        TaskConfigFactory(as_empty=True),
        TaskConfigFactory(as_completed=True),
        TaskConfigFactory(as_failed=True),
    ]


def create_edge_case_skill_configs() -> list[dict[str, Any]]:
    """创建覆盖所有边界场景的 Skill 配置列表。"""
    return [
        SkillConfigFactory(),
        SkillConfigFactory(as_active_high_quality=True),
        SkillConfigFactory(as_draft=True),
        SkillConfigFactory(as_rejected=True),
        SkillConfigFactory(as_low_quality=True),
    ]


def create_edge_case_store_entries() -> list[dict[str, Any]]:
    """创建覆盖所有边界场景的 Store 条目列表。"""
    return [
        StoreEntryFactory(),
        StoreEntryFactory(as_readonly=True),
        StoreEntryFactory(as_large_value=True),
        StoreEntryFactory(as_special_chars_key=True),
        StoreEntryFactory(as_empty_value=True),
    ]
