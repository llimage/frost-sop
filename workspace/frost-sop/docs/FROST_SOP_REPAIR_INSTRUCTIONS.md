# FROST-SOP 全量修复指令（按优先级执行）

> 执行者：WorkBuddy / Partner Agent
> 预计耗时：4-6 小时
> 验收标准：每步修复后运行对应测试，全绿才能下一步

---

## 执行顺序（不可跳过）

```
Step 1: skill.py 加错误处理（地基，必须先做）
Step 2: conftest.py 拆分 + 冒烟测试（测试说真话）
Step 3: db.py SQL 安全检查误报根治（根因修复）
Step 4: sop.py 验证器增强（宪法解释器）
Step 5: api/main.py 硬编码扫描（全局清理）
Step 6: workbench.py 假数据标注（诚实标记）
Step 7: llm.py 缓存 key 修复（时间敏感）
Step 8: event_bus.py 双轨制文档（架构债务）
```

---

## Step 1: skill.py 加错误处理（30分钟）

### 目标
让 Skill 执行层从"裸函数"变成"可容错、可观测"的生产级组件。

### 修改文件
`workspace/frost-sop/core/skill.py`

### 当前代码（第1-35行）
```python
class Skill:
    def __init__(self, name: str, func):
        self.name = name
        self._func = func

    def execute(self, context: dict) -> dict:
        return self._func(context)
```

### 修改后代码
```python
"""
PHILOSOPHY:
Skill is a stateless capability unit (like a protein).
Receives context dict, returns updated context dict.

V2.0: 增加错误处理、输入验证、输出验证、超时控制
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Skill:
    """
    PHILOSOPHY: A protein. Stateless capability unit.
    Receives context dict, returns updated context dict.

    V2.0: 增加容错机制，确保 Skill 错误不中断任务链
    """

    def __init__(
        self,
        name: str,
        func,
        required_keys: list[str] | None = None,
        output_schema: dict[str, type] | None = None,
        timeout_seconds: int = 60,
    ):
        """
        Initialize a Skill.

        Args:
            name: The name of the skill
            func: A pure function with signature func(context: dict) -> dict
            required_keys: 必需的输入 context 键列表
            output_schema: 期望的输出类型检查 {key: type}
            timeout_seconds: 执行超时（秒）
        """
        self.name = name
        self._func = func
        self._required_keys = required_keys or []
        self._output_schema = output_schema or {}
        self._timeout_seconds = timeout_seconds

    def execute(self, context: dict) -> dict:
        """
        Execute the skill function with full error handling.

        Args:
            context: The input context dictionary

        Returns:
            Updated context dictionary. On error, returns context with _skill_error keys.
        """
        # 1. 输入验证
        for key in self._required_keys:
            if key not in context:
                logger.error("[%s] 缺少必需输入: %s", self.name, key)
                context["_skill_error"] = f"缺少必需输入: {key}"
                context["_skill_error_name"] = self.name
                context["_skill_failed"] = True
                return context

        # 2. 执行（带超时保护）
        try:
            import signal

            def _timeout_handler(signum, frame):
                raise TimeoutError(f"Skill {self.name} 执行超过 {self._timeout_seconds} 秒")

            # 设置超时（Unix 系统）
            old_handler = None
            try:
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(self._timeout_seconds)
            except (AttributeError, ValueError):
                pass  # Windows 不支持 signal.SIGALRM

            try:
                result = self._func(context)
            finally:
                try:
                    signal.alarm(0)
                    if old_handler is not None:
                        signal.signal(signal.SIGALRM, old_handler)
                except (AttributeError, ValueError):
                    pass

        except TimeoutError as e:
            logger.error("[%s] 执行超时: %s", self.name, e)
            context["_skill_error"] = f"执行超时: {e}"
            context["_skill_error_name"] = self.name
            context["_skill_failed"] = True
            return context
        except Exception as e:
            logger.error("[%s] 执行异常: %s", self.name, e, exc_info=True)
            context["_skill_error"] = f"执行异常: {type(e).__name__}: {e}"
            context["_skill_error_name"] = self.name
            context["_skill_failed"] = True
            return context

        # 3. 输出验证
        if not isinstance(result, dict):
            logger.error("[%s] 返回值类型错误: 期望 dict, 实际 %s", self.name, type(result).__name__)
            context["_skill_error"] = f"返回值类型错误: 期望 dict, 实际 {type(result).__name__}"
            context["_skill_error_name"] = self.name
            context["_skill_failed"] = True
            return context

        # 4. 输出 schema 检查
        for key, expected_type in self._output_schema.items():
            if key in result and not isinstance(result[key], expected_type):
                logger.error(
                    "[%s] 输出类型不匹配: %s 期望 %s, 实际 %s",
                    self.name, key, expected_type.__name__, type(result[key]).__name__
                )
                context["_skill_error"] = f"输出类型不匹配: {key}"
                context["_skill_error_name"] = self.name
                context["_skill_failed"] = True
                return context

        # 5. 成功：合并结果
        if "_skill_failed" in context:
            del context["_skill_failed"]
        context.update(result)
        context["_reason"] = result.get("_reason", f"Skill {self.name} 执行成功")
        return context
```

### 向后兼容说明
- 现有 Skill 实例无需修改：`required_keys`、`output_schema`、`timeout_seconds` 都有默认值
- Agent 的 `_execute_step_with_retry` 不需要改（它已经在捕获异常）
- 但 Agent 现在可以检查 `context.get("_skill_failed")` 来判断是否需要重试

### 验证方式
```bash
# 1. 语法检查
python -m py_compile workspace/frost-sop/core/skill.py

# 2. 运行 skill 相关测试
cd workspace/frost-sop && python -m pytest tests/test_agent.py -v -k skill

# 3. 手动验证：创建一个会抛异常的 Skill，确认不崩溃
```

---

## Step 2: conftest.py 拆分 + 冒烟测试（1小时）

### 目标
让测试从"全部模拟"变成"单元测试模拟 + 冒烟测试真实"。

### 修改 1：创建新的 conftest.py（替换根目录的）

**文件**：`workspace/frost-sop/conftest.py`（根目录，不是 tests/ 下的）

**当前内容（第1-11行）**：
```python
import os
os.environ.setdefault("FROST_TESTING", "1")
```

**替换为**：
```python
"""
FROST-SOP 全局 pytest 配置（根目录）

测试分级：
- unit: 单元测试（mock 模式，快速）
- smoke: 冒烟测试（真实 LLM，3 分钟）
- integration: 集成测试（真实 LLM，手动触发）
"""

import os
import pytest


# 只在运行单元测试时设置 FROST_TESTING=1
def pytest_configure(config):
    """根据测试标记自动设置测试模式"""
    markers = [m.name for m in config.getoption("-m", default=[])]

    # 如果没有指定标记，或指定了 unit 标记，使用 mock 模式
    if not markers or "unit" in markers:
        os.environ["FROST_TESTING"] = "1"
    elif "smoke" in markers or "integration" in markers:
        # 冒烟/集成测试使用真实 LLM
        os.environ.pop("FROST_TESTING", None)


def pytest_collection_modifyitems(config, items):
    """自动给没有标记的测试添加 unit 标记"""
    for item in items:
        if not any(marker.name in ["unit", "smoke", "integration"] for marker in item.markers):
            item.add_marker(pytest.mark.unit)
```

### 修改 2：创建冒烟测试

**新文件**：`workspace/frost-sop/tests/smoke/test_system_alive.py`

```python
"""
冒烟测试：3 分钟验证系统核心链路可用。
使用真实 LLM，消耗约 50-100 tokens。

运行方式：
    pytest tests/smoke/ -m smoke -v
"""

import os
import pytest

# 确保真实模式
os.environ.pop("FROST_TESTING", None)


@pytest.mark.smoke
class TestSystemAlive:
    """3 分钟冒烟测试"""

    def test_llm_online_call(self):
        """真实 LLM 调用能工作"""
        from skills.llm import call_llm

        result = call_llm({
            "_prompt": "Say 'pong' only",
            "_llm_profile": "execute",
            "_max_tokens": 10,
        })

        assert result.get("_llm_backend") == "online", "LLM 未走 online 路径"
        assert result.get("_llm_response", "").strip() != "", "LLM 响应为空"
        print(f"LLM 响应: {result.get('_llm_response', '')}")

    def test_temperature_profile_effective(self):
        """temperature profile 映射生效"""
        from skills.llm import call_llm

        # execute profile 应该使用 0.1
        result = call_llm({
            "_prompt": "Generate a random number between 1-100",
            "_llm_profile": "execute",
            "_max_tokens": 20,
        })

        assert result.get("_llm_backend") == "online"
        # 如果 temperature 生效，两次相同 prompt 应该返回相似结果
        result2 = call_llm({
            "_prompt": "Generate a random number between 1-100",
            "_llm_profile": "execute",
            "_max_tokens": 20,
        })
        # 不要求完全相同，但应该相似（不是随机发散）
        assert result.get("_llm_response") == result2.get("_llm_response"), \
            "execute profile temperature 未生效（两次结果不同）"

    def test_database_read_write(self):
        """数据库能读写"""
        from core.db import DBManager

        db = DBManager(db_path=":memory:")  # 内存数据库，不污染生产数据
        db.insert("projects", {
            "id": "smoke_test",
            "name": "冒烟测试",
            "status": "active",
        })
        row = db.select_one("projects", "id", "smoke_test")
        assert row["name"] == "冒烟测试"

    def test_sop_load_and_validate(self):
        """SOP 能加载并通过基础验证"""
        from core.sop import SOP, SOPValidator

        sop = SOP.load_from_yaml("sops/templates/OPS-007.yaml")
        assert sop.sop_id == "OPS-007"
        assert len(sop.stages) > 0

        # 验证器检查
        validator = SOPValidator()
        result = validator.validate(sop, {
            "required_stages": ["信息收集"],
            "forbidden_skills": [],
        })
        assert result["valid"] is True

    def test_api_health_endpoint(self):
        """API 健康检查返回 200"""
        import requests

        try:
            resp = requests.get("http://localhost:8000/api/health", timeout=5)
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
        except requests.ConnectionError:
            pytest.skip("API 服务未启动，跳过此测试")
```

### 修改 3：修改 CI 配置

**文件**：`.github/workflows/test.yml`

**在现有 jobs 后添加**：
```yaml
  # ──────────────────────────────────────────────────────────
  # Job 3: 冒烟测试（真实 LLM）
  # ──────────────────────────────────────────────────────────
  smoke-test:
    name: Smoke Test (Real LLM)
    runs-on: ubuntu-latest
    timeout-minutes: 5
    needs: unit-tests
    if: github.event_name == 'workflow_dispatch' || contains(github.event.head_commit.message, '[smoke]')

    env:
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
      - run: pip install -r requirements.txt
      - run: |
          pytest tests/smoke/ -m smoke -v --timeout 180
```

### 验证方式
```bash
# 1. 单元测试（mock 模式）
cd workspace/frost-sop && pytest tests/ -m unit -x -q

# 2. 冒烟测试（真实 LLM，需要 DEEPSEEK_API_KEY）
pytest tests/smoke/ -m smoke -v

# 3. 确认冒烟测试走了真实 LLM（检查输出中有 "_llm_backend": "online"）
```

---

## Step 3: db.py SQL 安全检查误报根治（30分钟）

### 目标
修复 `_WHERE_DANGEROUS_KEYWORDS` 对列名的误报。

### 修改文件
`workspace/frost-sop/core/db.py`

### 当前问题代码（第46-61行）
```python
_WHERE_DANGEROUS_KEYWORDS = [
    ";", "--", "/*", "*/",
    "UNION", "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "EXEC", "EXECUTE", "TRUNCATE",
]
```

### 问题
- `updated_at` 列名中的 `UPDATE` 被误报为危险关键词
- `created_at` 中的 `CREATE` 可能被误报
- 但 `select_all("tasks", "updated_at = ?", ["2026-01-01"])` 是合法的

### 修改后代码
```python
# S-001 修复：WHERE 子句危险关键字（用于非参数化部分的检测）
# 注意：这些关键词只应在操作符位置出现，不应在列名中出现
# 但为了安全，我们检查整个 WHERE 字符串，同时允许合法的列名包含这些子串
_WHERE_DANGEROUS_KEYWORDS = [
    ";",      # 语句分隔
    "--",     # 注释
    "/*", "*/",  # 块注释
    "UNION",  # UNION 注入
    "DROP",   # 删除表
    "DELETE", # 删除数据
    "INSERT", # 插入数据
    "ALTER",  # 修改表结构
    "EXEC", "EXECUTE", "TRUNCATE",  # 执行/截断
]

# 列名中常见的安全关键词子串（允许出现在列名中）
_ALLOWED_IN_COLUMN_NAMES = {
    "CREATE": ["created_at", "created_by", "creation_date"],
    "UPDATE": ["updated_at", "updated_by", "update_time"],
}
```

### 修改 `select_all` 方法（第741-778行）

在现有的安全检查后添加**白名单豁免**：

```python
def select_all(self, table: str, where: str | None = None, params: list[Any] | None = None):
    # ... 现有代码 ...

    # S-001 修复：WHERE 子句安全验证
    if where:
        where_upper = where.upper()
        for keyword in _WHERE_DANGEROUS_KEYWORDS:
            if keyword in where_upper:
                # 白名单豁免：检查是否是列名的一部分
                exempt = False
                for allowed_keyword, allowed_columns in _ALLOWED_IN_COLUMN_NAMES.items():
                    if keyword == allowed_keyword:
                        # 检查 where 中是否包含允许的列名
                        for col in allowed_columns:
                            if col.upper() in where_upper:
                                exempt = True
                                break
                    if exempt:
                        break

                if not exempt:
                    raise ValueError(f"Security: Dangerous keyword '{keyword}' in WHERE clause")

    # ... 现有代码 ...
```

### 验证方式
```bash
# 1. 运行之前失败的测试
cd workspace/frost-sop && pytest tests/test_workbench_coverage.py -v

# 2. 确认 updated_at 不再误报
python -c "
from core.db import DBManager
db = DBManager(':memory:')
db.select_all('projects', 'updated_at = ?', ['2026-01-01'])
print('✅ updated_at 列名不再误报')
"

# 3. 确认真正的危险关键词仍然被拦截
python -c "
from core.db import DBManager
db = DBManager(':memory:')
try:
    db.select_all('projects', 'id = 1; DROP TABLE projects; --', [])
    print('❌ 危险关键词未被拦截')
except ValueError as e:
    print('✅ 危险关键词正确拦截:', e)
"
```

---

## Step 4: sop.py 验证器增强（45分钟）

### 目标
让 SOP 验证器不只是"检查封面"，而是"检查宪法内容"。

### 修改文件
`workspace/frost-sop/core/sop.py`

### 当前代码（第65-110行）
```python
class SOPValidator:
    def validate(self, sop: SOP, rules: dict) -> dict:
        errors = []
        # ... 只有 required_stages 和 forbidden_skills 检查 ...
        return {"valid": len(errors) == 0, "errors": errors}
```

### 修改后代码
```python
class SOPValidator:
    """
    PHILOSOPHY: Governance check. Validates SOP against compliance rules.

    V2.0: 增加结构完整性检查、字段必填检查、技能存在性检查
    """

    # 每个 stage 必须有的字段
    REQUIRED_STAGE_FIELDS = ["name", "skill", "requirement"]
    # 可选但推荐的字段
    RECOMMENDED_STAGE_FIELDS = ["output_type", "output_format", "constraint"]

    def validate(self, sop: SOP, rules: dict) -> dict:
        """
        全面验证 SOP。

        检查项：
        1. 基础字段完整性（sop_id, name, version, stages）
        2. 每个 stage 的结构完整性（必填字段）
        3. 阶段名称唯一性
        4. required_stages 合规性
        5. forbidden_skills 合规性
        6. 预算限制
        """
        errors = []
        warnings = []

        # 1. 基础字段检查
        if not sop.sop_id:
            errors.append({"rule": "sop_id", "message": "SOP ID 不能为空"})
        if not sop.name:
            errors.append({"rule": "name", "message": "SOP 名称不能为空"})
        if not sop.stages:
            errors.append({"rule": "stages", "message": "SOP 至少需要一个阶段"})

        # 2. 每个 stage 的结构检查
        stage_names = set()
        for i, stage in enumerate(sop.stages):
            stage_name = stage.get("name", f"阶段{i+1}")

            # 检查必填字段
            for field in self.REQUIRED_STAGE_FIELDS:
                if field not in stage or not stage[field]:
                    errors.append({
                        "rule": "stage_field_required",
                        "message": f"Stage '{stage_name}' 缺少必需字段: {field}",
                        "stage": stage_name,
                        "field": field,
                    })

            # 检查阶段名唯一性
            if stage_name in stage_names:
                errors.append({
                    "rule": "duplicate_stage_name",
                    "message": f"Stage 名称重复: '{stage_name}'",
                    "stage": stage_name,
                })
            stage_names.add(stage_name)

            # 检查推荐字段（warning 级别）
            for field in self.RECOMMENDED_STAGE_FIELDS:
                if field not in stage:
                    warnings.append({
                        "rule": "stage_field_recommended",
                        "message": f"Stage '{stage_name}' 缺少推荐字段: {field}",
                        "stage": stage_name,
                        "field": field,
                    })

        # 3. required_stages 检查
        required = rules.get("required_stages", [])
        for stage_name in required:
            if not any(s.get("name") == stage_name for s in sop.stages):
                errors.append({
                    "rule": "required_stages",
                    "message": f"Missing required stage: {stage_name}",
                })

        # 4. forbidden_skills 检查
        forbidden = rules.get("forbidden_skills", [])
        for skill_name in forbidden:
            for stage in sop.stages:
                stage_skills = stage.get("skills", [])
                if skill_name in stage_skills:
                    errors.append({
                        "rule": "forbidden_skills",
                        "message": f"Stage '{stage.get('name')}' contains forbidden skill: {skill_name}",
                    })

        # 5. 预算检查
        max_budget = rules.get("max_budget")
        if max_budget is not None and hasattr(sop, "budget") and sop.budget > max_budget:
            errors.append({
                "rule": "max_budget",
                "message": f"Budget exceeded: {sop.budget} > {max_budget}",
            })

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stage_count": len(sop.stages),
            "checked_at": __import__("datetime").datetime.now().isoformat(),
        }

    def validate_yaml(self, yaml_path: str) -> dict:
        """
        直接从 YAML 文件验证 SOP。

        Args:
            yaml_path: YAML 文件路径

        Returns:
            验证结果字典
        """
        try:
            sop = SOP.load_from_yaml(yaml_path)
            return self.validate(sop, {})
        except Exception as e:
            return {
                "valid": False,
                "errors": [{"rule": "yaml_load", "message": str(e)}],
                "warnings": [],
            }
```

### 验证方式
```bash
# 1. 验证现有 SOP 模板
python -c "
from core.sop import SOPValidator
v = SOPValidator()
result = v.validate_yaml('sops/templates/OPS-007.yaml')
print('Valid:', result['valid'])
print('Errors:', result['errors'])
print('Warnings:', result['warnings'])
"

# 2. 验证一个故意损坏的 SOP
# 创建一个缺少 name 的 stage，确认验证器能发现
```

---

## Step 5: api/main.py 硬编码扫描（30分钟）

### 目标
扫描并清理 API 层所有硬编码配置值。

### 检查清单

| 位置 | 当前值 | 修复方式 |
|------|--------|---------|
| `api/main.py:480` | `_temperature: 0.7` | ✅ 已修复（`_llm_profile: execute`） |
| `api/main.py:22-23` | CORS origins 默认值 | 从环境变量读取（已有） |
| `api/models.py:23` | `use_real_llm: False` | 改为 `True`（真实模式默认） |

### 修改文件
`workspace/frost-sop/api/models.py`

**当前（第19-24行）**：
```python
class TaskCreateRequest(BaseModel):
    description: str = Field(..., min_length=1, description="任务描述")
    sop_id: str = Field(default="DEV-001", description="SOP模板ID")
    project_id: str = Field(default="default", description="项目ID")
    use_real_llm: bool = Field(default=False, description="是否使用真实LLM")
```

**修改后**：
```python
class TaskCreateRequest(BaseModel):
    description: str = Field(..., min_length=1, description="任务描述")
    sop_id: str = Field(default="DEV-001", description="SOP模板ID")
    project_id: str = Field(default="default", description="项目ID")
    use_real_llm: bool = Field(
        default=True,  # ← 默认使用真实 LLM
        description="是否使用真实LLM（默认True，测试时可设为False）"
    )
```

### 附加：扫描其他硬编码
```bash
# 运行以下命令，检查是否有其他硬编码配置
cd workspace/frost-sop && grep -rn "temperature.*=.*0\." --include="*.py" api/ core/ skills/
cd workspace/frost-sop && grep -rn "FROST_TESTING.*=.*1" --include="*.py" api/ core/ skills/
```

### 验证方式
```bash
# 1. 检查修改后的默认值
python -c "
from api.models import TaskCreateRequest
req = TaskCreateRequest(description='test')
print('use_real_llm default:', req.use_real_llm)
assert req.use_real_llm == True, '默认应该是 True'
"

# 2. 运行 API 测试
pytest tests/test_api_endpoints.py -v -x
```

---

## Step 6: workbench.py 假数据标注（15分钟）

### 目标
对硬编码数据添加 TODO 注释，标记为"需替换为真实数据源"。

### 修改文件
`workspace/frost-sop/core/workbench.py`

### 修改 1：DEFAULT_PROJECTS 添加注释（第21-58行）

在每个项目的 `revenue_monthly` 前添加 TODO：

```python
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
        # TODO: revenue_monthly 当前为硬编码演示值，需从数据库或财务系统读取真实数据
        # Issue: https://github.com/user/project/issues/123
        "revenue_monthly": 34200,
    },
    # ... 其他项目同理 ...
]
```

### 修改 2：`_build_task_recommendation` 添加注释（第205-228行）

在 `task_scenarios` 前添加：

```python
def _build_task_recommendation(...) -> dict:
    """构建任务推荐"""
    # TODO: task_scenarios 为硬编码模拟数据，后续应从任务数据库动态读取
    # 当前实现仅用于演示和测试
    task_scenarios = {
        "dev": {
            "task_name": "实现用户权限管理的 RBAC 模块",
            "progress": 65,
            "duration": "2.5h",
            "phase": "Phase 3/5 · 代码实现",
        },
        # ...
    }
```

### 验证方式
```bash
# 确认 TODO 注释已添加
grep -n "TODO" workspace/frost-sop/core/workbench.py
```

---

## Step 7: llm.py 缓存 key 修复（20分钟）

### 目标
让缓存 key 包含时间戳，避免返回过时响应。

### 修改文件
`workspace/frost-sop/skills/llm.py`

### 当前代码（第62-76行）
```python
def _cache_key(context: dict) -> str | None:
    if context.get("_llm_cache_bypass", False):
        return None
    if os.getenv("FROST_TESTING") == "1":
        return None
    key_parts = [
        context.get("_prompt", ""),
        context.get("_system_prompt", ""),
        str(context.get("_temperature", "")),
        context.get("_model", "deepseek-chat"),
        str(context.get("_max_tokens", "")),
        context.get("_llm_profile", ""),
    ]
    return hashlib.sha256("|".join(key_parts).encode("utf-8")).hexdigest()
```

### 修改后代码
```python
def _cache_key(context: dict) -> str | None:
    """生成缓存 key。包含日期、Agent ID、任务 ID，避免过时响应和信息泄露。"""
    if context.get("_llm_cache_bypass", False):
        return None
    if os.getenv("FROST_TESTING") == "1":
        return None

    # 获取当前日期（用于时间敏感查询如"今天"、"本周"）
    from datetime import date
    today = date.today().isoformat()

    key_parts = [
        # 用户输入（核心）
        context.get("_prompt", ""),
        context.get("_system_prompt", ""),
        # LLM 配置
        str(context.get("_temperature", "")),
        context.get("_model", "deepseek-chat"),
        str(context.get("_max_tokens", "")),
        context.get("_llm_profile", ""),
        # 上下文隔离（防止不同 Agent/任务共享缓存）
        context.get("_agent_id", "default"),
        context.get("_task_id", "default"),
        # 时间戳（日期级别，避免"今天"查询返回昨天结果）
        today,
    ]
    return hashlib.sha256("|".join(key_parts).encode("utf-8").hexdigest()
```

### 验证方式
```bash
# 1. 同一天相同 prompt 的缓存 key 应该相同
python -c "
from skills.llm import _cache_key
k1 = _cache_key({'_prompt': 'test', '_agent_id': 'a1', '_task_id': 't1'})
k2 = _cache_key({'_prompt': 'test', '_agent_id': 'a1', '_task_id': 't1'})
print('Same key:', k1 == k2)
assert k1 == k2, '同一天相同输入应该相同'
"

# 2. 不同 Agent 的缓存 key 应该不同
python -c "
from skills.llm import _cache_key
k1 = _cache_key({'_prompt': 'test', '_agent_id': 'a1'})
k2 = _cache_key({'_prompt': 'test', '_agent_id': 'a2'})
print('Different key:', k1 != k2)
assert k1 != k2, '不同 Agent 应该不同'
"
```

---

## Step 8: event_bus.py 双轨制文档（15分钟）

### 目标
为 EventBus/AsyncEventBus 双轨制添加架构说明，避免误用。

### 修改文件
`workspace/frost-sop/core/event_bus.py`

### 在文件顶部注释后添加（第20-21行之间）

```python
"""
架构说明：双轨制事件总线
─────────────────────────
EventBus（同步）和 AsyncEventBus（异步）是两个独立的单例。

使用场景：
- 同步代码（main.py、Streamlit UI、Agent.run）→ 使用 EventBus
- 异步代码（main_async.py、FastAPI 异步端点）→ 使用 AsyncEventBus

注意事项：
1. 两个总线互不干扰，事件不会自动跨总线传播
2. 如果同步代码订阅了 EventBus，异步代码发布到 AsyncEventBus，
   同步订阅者不会收到事件
3. 生产环境建议统一使用一种模式（推荐：同步 EventBus）

未来规划：V4.0 可能合并为一个统一总线（自动检测同步/异步上下文）
"""
```

### 验证方式
```bash
# 确认文档已添加
head -40 workspace/frost-sop/core/event_bus.py | grep -A5 "架构说明"
```

---

## 验收总清单

| Step | 验收方式 | 通过标准 |
|------|---------|---------|
| 1 | `pytest tests/test_agent.py -v` | 全绿 |
| 2 | `pytest tests/smoke/ -m smoke -v` | 全绿，确认 `_llm_backend: online` |
| 3 | `pytest tests/test_workbench_coverage.py` | 全绿（不再触发误报） |
| 4 | `python -c "from core.sop import SOPValidator; v=SOPValidator(); print(v.validate_yaml('sops/templates/OPS-007.yaml'))"` | 无 errors |
| 5 | `python -c "from api.models import TaskCreateRequest; print(TaskCreateRequest(description='t').use_real_llm)"` | 输出 `True` |
| 6 | `grep "TODO" workspace/frost-sop/core/workbench.py` | 有 2+ 处 TODO |
| 7 | `python -c "from skills.llm import _cache_key; print(_cache_key({'_prompt': 'test', '_agent_id': 'a'}))"` | 有输出 |
| 8 | `grep "架构说明" workspace/frost-sop/core/event_bus.py` | 匹配成功 |

---

> **执行原则**：
> 1. 每步修复后立即验证，不通过不进入下一步
> 2. 修改前用 `git diff` 确认变更范围
> 3. 所有修改保持向后兼容（现有代码不破坏）
> 4. 如有疑问，停止并报告，不猜测
