# FROST-SOP V2.0 全量改造方案

> 版本：2026-06-17
> 目标：健壮、高可用、多沟通方式、坚守FROST哲学
> 约束：一人公司、IT小白、月预算¥300、瀑布式偏好

---

## 一、现状全景诊断

### 1.1 资产清单（已有且可用）

| 维度 | 状态 | 说明 |
|------|------|------|
| **数据库** | ✅ 成熟 | db.py 1000+行，19张表，WAL模式，迁移机制，SQL注入防护 |
| **API层** | ✅ 可用 | FastAPI 842行，15个端点，SSE流式，CORS配置 |
| **Web前端** | ✅ 可用 | Next.js，成本面板、任务管理、决策面板 |
| **测试框架** | ✅ 豪华 | 107个测试文件，pytest+cov+benchmark+hypothesis+locust |
| **CI/CD** | ✅ 有 | GitHub Actions 7个job，Makefile，pre-commit |
| **成本追踪** | ✅ 可用 | cost_log表，月度统计，预算告警 |
| **事件总线** | ✅ 有 | event_log表，EventBus模式 |
| **审计日志** | ✅ 有 | audit_log表，全量记录 |
| **Agent体系** | ✅ 有 | Ancestor→Parent→5孙辈的分形架构 |
| **桌面通知** | ✅ 可用 | Windows toast/plyer降级 |
| **SOP模板** | ⚠️ 半成 | 12个模板，4个已改进，8个待改 |
| **LLM调用** | ⚠️ 已改 | temperature映射已加，但API层未同步 |
| **Skill基类** | ❌ 脆弱 | 35行，无错误处理、无重试、无降级 |
| **配置管理** | ❌ 分散 | 硬编码在多个文件，无统一中心 |
| **测试真实性** | ❌ 自欺 | 全部FROST_TESTING=1，CI全绿≠真实可用 |
| **审计闭环** | ❌ 断裂 | 20+审计报告，无修复→验证追踪 |

### 1.2 核心矛盾

```
数据库层 ──→ 工程化成熟（1000行，企业级）
    ↑
API层   ──→ 功能完整（842行，15端点）
    ↑
Skill层 ──→ 脆弱不堪（35行，无容错） ←── 最致命短板
    ↑
测试层  ──→ 自欺欺人（107文件，全模拟）
```

**关键发现**：系统呈"倒金字塔"——越底层越成熟，越接近用户交互越脆弱。Skill是Agent执行的核心环节，却没有任何错误防护。

### 1.3 多沟通方式现状

| 方式 | 状态 | 覆盖场景 |
|------|------|---------|
| Web前端（Next.js） | ✅ 可用 | 日常任务管理、成本查看、决策提交 |
| REST API | ✅ 可用 | 第三方集成、移动端、自动化脚本 |
| SSE流式日志 | ✅ 可用 | 实时监控、审计追踪 |
| 桌面通知 | ✅ 可用 | 决策超时提醒 |
| CLI命令行 | ⚠️ 有Makefile | 仅限测试/开发，非交互式 |
| IM/邮件/短信 | ❌ 缺失 | 无 |

---

## 二、改造目标与原则

### 2.1 目标定义

| 目标 | 量化标准 | 验收方式 |
|------|---------|---------|
| **健壮** | Skill执行失败率<5%，自动恢复率>90% | 运行100次任务，手动统计失败与恢复 |
| **高可用** | 核心功能7×24可访问，非核心功能降级可用 | 连续7天监控API health端点 |
| **多沟通方式** | 5种方式可用（Web/API/CLI/IM/邮件） | 每种方式成功完成一次端到端任务 |
| **FROST哲学** | SOP驱动、分形治理、AI是杠杆 | 所有功能通过SOP模板配置，非硬编码 |

### 2.2 改造原则（不可妥协）

1. **不倒置金字塔**：先加固Skill层，再扩展功能。地基不稳不盖楼。
2. **测试说真话**：CI必须跑真实LLM调用，模拟测试降为辅助。
3. **配置驱动**：所有可变参数进配置文件，禁止硬编码。
4. ** backwards compatible**：已有功能不破坏，新功能增量添加。
5. **2周一个MVP**：每阶段必须有可验收的交付物，禁止无限期开发。

---

## 三、四阶段改造计划（8周）

```
Week  1-2  │ Phase 1: 地基加固（Skill+Config+Error Handler）
Week  3-4  │ Phase 2: 测试革命（真实CI+冒烟测试+覆盖率提升）
Week  5-6  │ Phase 3: 体验升级（SOP全量+多沟通方式+可观测性）
Week  7-8  │ Phase 4: 债务清偿（审计闭环+文档+交接）
```

---

## Phase 1: 地基加固（Week 1-2）

### 目标
让Skill执行层从"35行草稿"变成"可容错、可重试、可降级"的生产级组件。

### 任务清单

#### P1-1: 重写Skill基类（4小时）

**现状**：35行，无错误处理
**目标**：200行，含重试、降级、验证、日志

```python
# core/skill_v2.py（新文件，不破坏旧的skill.py）
class SkillV2:
    """
    FROST哲学: Skill是状态less的能力单元(protein)。
    V2强化: 容错、可观测、可配置。
    """
    def __init__(
        self,
        name: str,
        func: Callable,
        max_retries: int = 2,
        timeout_seconds: int = 60,
        fallback_skill: Optional['SkillV2'] = None,
        required_keys: Optional[list[str]] = None,
        output_schema: Optional[dict] = None,
    ):
        ...

    def execute(self, context: dict) -> dict:
        """
        执行流程:
        1. 输入验证（required_keys检查）
        2. 超时执行（信号量控制）
        3. 输出验证（output_schema检查）
        4. 失败重试（指数退避）
        5. 降级执行（fallback_skill）
        6. 错误记录（不抛异常，写入context）
        """
        ...
```

**交付物**：`core/skill_v2.py` + 单元测试
**验收**：运行`test_skill_v2.py`，所有场景通过（正常/超时/重试/降级/验证失败）

#### P1-2: 统一配置中心（4小时）

**现状**：配置分散在db.py、llm.py、api/main.py、环境变量
**目标**：一个YAML文件管所有，Pydantic验证，热加载

```yaml
# config/frost.yaml（新增）
llm:
  model: deepseek-chat
  profile_defaults:
    execute: {temperature: 0.1, top_p: 0.8, max_tokens: 2048}
    create:  {temperature: 0.5, top_p: 0.9, max_tokens: 4096}
    review:  {temperature: 0.2, top_p: 0.8, max_tokens: 2048}
  timeout_seconds: 60
  max_retries: 2

database:
  path: data/frost_sop.db
  wal_mode: true
  busy_timeout: 5000

system:
  log_level: INFO
  budget_limit_monthly: 300.0
  notification_channels: [desktop, api]

skill:
  default_timeout: 60
  default_max_retries: 2
  enable_validation: true
```

**交付物**：`core/config.py`（Pydantic模型）+ `config/frost.yaml` + 向后兼容层
**验收**：所有现有代码通过配置中心读取参数，无硬编码

#### P1-3: 全局错误处理器（3小时）

**现状**：每个try/except各自为政，错误格式不统一
**目标**：统一错误码、统一日志、统一降级

```python
# core/error_handler.py
class FROSTError(Exception):
    """所有FROST错误的基类"""
    code: str           # 错误码，如 SKILL_TIMEOUT
    level: str          # error/warning/info
    recoverable: bool   # 是否可自动恢复
    suggested_action: str  # 建议的恢复动作
```

**交付物**：`core/error_handler.py` + 错误码文档
**验收**：所有现有异常被捕获并转换为FROSTError，日志统一

#### P1-4: API层同步修复（2小时）

**现状**：api/main.py第480行`temperature=0.7`硬编码
**目标**：API层读取统一配置，支持profile参数

```python
# api/main.py 修改
@app.post("/api/chat")
def chat(req: ChatRequest):
    config = FROSTConfig.load()
    profile = req.profile or "execute"
    llm_config = config.llm.profile_defaults[profile]

    context = {
        "_prompt": req.message,
        "_llm_profile": profile,  # ← 自动映射temperature
        "_temperature": req.temperature,  # ← 用户可覆盖
        ...
    }
```

**交付物**：修改后的`api/main.py`
**验收**：API调用时temperature按profile自动映射，用户可覆盖

### Phase 1 验收标准

- [ ] `test_skill_v2.py` 全部通过（真实LLM模式，非模拟）
- [ ] `config/frost.yaml` 存在且可被所有模块读取
- [ ] API `/api/chat` 支持profile参数（execute/create/review）
- [ ] 任意Skill抛异常时，任务链不中断，错误被记录到context
- [ ] 代码审查：无新增硬编码配置

---

## Phase 2: 测试革命（Week 3-4）

### 目标
让测试从"自欺欺人的绿色"变成"真实可用的信心"。

### 任务清单

#### P2-1: 拆分测试流水线（3小时）

**现状**：所有测试强制`FROST_TESTING=1`
**目标**：三类测试明确分离

```yaml
# .github/workflows/test.yml 重构
jobs:
  # 1. 单元测试（模拟模式，快，每次push跑）
  unit-tests:
    env:
      FROST_TESTING: "1"
    steps:
      - pytest tests/unit/ -m "unit" --timeout 30

  # 2. 冒烟测试（真实LLM，每次push跑，3分钟）
  smoke-test:
    env:
      FROST_TESTING: "0"
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
    timeout-minutes: 5
    steps:
      - pytest tests/smoke/ -m "smoke" --timeout 180

  # 3. 集成测试（真实LLM，手动触发或含[real-test]的commit）
  integration-tests:
    env:
      FROST_TESTING: "0"
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
    if: contains(github.event.head_commit.message, '[real-test]')
    steps:
      - pytest tests/integration/ -m "integration" --timeout 300
```

**交付物**：重构后的`.github/workflows/test.yml`
**验收**：push一次代码，单元测试和冒烟测试都跑，冒烟测试3分钟内完成

#### P2-2: 编写冒烟测试（3小时）

**目标**：3分钟验证"系统基本可用"

```python
# tests/smoke/test_system_alive.py
import pytest

@pytest.mark.smoke
class TestSystemAlive:
    """3分钟冒烟测试：验证系统核心链路可用"""

    def test_llm_online_call(self):
        """真实LLM调用能工作"""
        result = call_llm({
            "_prompt": "Say 'pong' only",
            "_llm_profile": "execute",
            "_max_tokens": 10,
            "_llm_mode": "online",
        })
        assert result["_llm_backend"] == "online"
        assert result["_llm_response"] != ""

    def test_database_read_write(self):
        """数据库能读写"""
        db = get_db()
        test_id = f"smoke_{uuid4().hex[:8]}"
        db.insert("tasks", {"id": test_id, "title": "smoke", "status": "test"})
        row = db.select_one("tasks", "id", test_id)
        assert row["title"] == "smoke"

    def test_sop_execution(self):
        """OPS-007能完整执行4个阶段"""
        result = run_sop("OPS-007", task="smoke test")
        assert result["status"] == "completed"
        assert len(result["phases"]) == 4

    def test_api_health(self):
        """API健康检查返回200"""
        import requests
        resp = requests.get("http://localhost:8000/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
```

**交付物**：`tests/smoke/`目录，4个测试文件
**验收**：`make smoke`命令3分钟内完成，全部通过

#### P2-3: 提升覆盖率到70%（4小时）

**现状**：`--cov-fail-under=55`
**目标**：`--cov-fail-under=70`

**策略**：不追求100%，专注覆盖"关键路径"
- `core/skill_v2.py` → 90%
- `core/db.py` → 80%（已有基础，补齐边缘case）
- `skills/llm.py` → 80%
- `api/main.py` → 60%（API测试成本高，重点覆盖异常路径）

**交付物**：新增测试文件 + CI阈值修改
**验收**：CI中`--cov-fail-under=70`通过

#### P2-4: 建立测试基线文档（2小时）

```markdown
# docs/TEST_BASELINE.md

## 测试分级

| 级别 | 触发条件 | 耗时 | 真实LLM | 目的 |
|------|---------|------|---------|------|
| 单元 | 每次push | <30s | ❌ | 验证逻辑正确 |
| 冒烟 | 每次push | <3min | ✅ | 验证系统可用 |
| 集成 | [real-test] | <10min | ✅ | 验证端到端 |
| 全量 | 每周/发布前 | <30min | ✅ | 验证全部场景 |

## 已知限制
- 冒烟测试消耗~50 tokens/次，可忽略
- 集成测试消耗~500 tokens/次，需控制频率
- 月度预算¥300 ≈ 可跑~600次集成测试
```

### Phase 2 验收标准

- [ ] push代码时，单元测试+冒烟测试自动跑，全绿
- [ ] 冒烟测试3分钟内完成，消耗<100 tokens
- [ ] 覆盖率阈值改为70%，CI通过
- [ ] 任意开发者（包括未来的你）看`docs/TEST_BASELINE.md`就知道怎么跑测试

---

## Phase 3: 体验升级（Week 5-6）

### 目标
补齐多沟通方式，完成SOP模板全量改进，建立可观测性。

### 任务清单

#### P3-1: 改进剩余8个SOP模板（6小时）

**已改**：OPS-007、DEV-001、STR-001、OPS-006
**待改**：OPS-001、OPS-002、INIT-001、EMAIL-001、JUEJIN-001、REDBOOK-001、MT-001、STR-002

**每个模板添加**：
- `llm_config`（profile映射）
- `output_template`（阶段输出格式）
- `constraint`（禁止项）
- `timeout_seconds`（阶段超时）

**交付物**：8个改进后的YAML
**验收**：每个模板跑一次冒烟测试，输出符合格式约束

#### P3-2: CLI交互模式（4小时）

**现状**：Makefile只有测试命令
**目标**：`frost`命令行工具，支持交互式任务执行

```bash
# 安装后可用
$ frost task create --sop OPS-007 --description "调研长护险政策"
$ frost task list --status running
$ frost agent status
$ frost cost summary --month 2026-06
$ frost config show
```

```python
# frost_cli.py（新增）
import click

@click.group()
def cli():
    """FROST-SOP 命令行工具"""
    pass

@cli.command()
@click.option("--sop", required=True, help="SOP模板ID")
@click.option("--description", required=True, help="任务描述")
def task_create(sop, description):
    """创建并执行任务"""
    result = run_sop(sop, task=description)
    click.echo(f"任务状态: {result['status']}")
    click.echo(f"阶段数: {len(result['phases'])}")
```

**交付物**：`frost_cli.py` + `setup.py`入口
**验收**：`frost task create --sop OPS-007 --description "test"`成功执行

#### P3-3: 邮件通知通道（3小时）

**目标**：任务完成/失败时发送邮件通知

```python
# channels/email_notifier.py（新增）
class EmailNotifier:
    def __init__(self, smtp_config: dict):
        ...

    def send_task_complete(self, task_id: str, summary: str):
        ...

    def send_task_failed(self, task_id: str, error: str):
        ...
```

**配置**：
```yaml
# config/frost.yaml 新增
notification:
  channels: [desktop, email]
  email:
    smtp_host: smtp.gmail.com
    smtp_port: 587
    username: ${EMAIL_USER}
    password: ${EMAIL_PASS}
    to: founder@example.com
```

**交付物**：`channels/email_notifier.py`
**验收**：任务失败时收到邮件通知

#### P3-4: 可观测性面板（4小时）

**目标**：一个页面/接口看全系统健康

```python
# api/main.py 新增端点
@app.get("/api/observability", tags=["系统"])
def observability():
    """系统可观测性仪表盘"""
    db = get_db()
    return {
        "health": {
            "api": "ok",
            "database": check_db(),
            "llm": check_llm(),
        },
        "tasks": {
            "running": count_tasks("running"),
            "completed_today": count_tasks("completed", today=True),
            "failed_today": count_tasks("failed", today=True),
        },
        "cost": {
            "monthly_used": db.get_monthly_cost(year, month),
            "budget_limit": config.budget_limit_monthly,
            "remaining": config.budget_limit_monthly - db.get_monthly_cost(year, month),
        },
        "agents": {
            "total": count_agents(),
            "active": count_agents("active"),
        },
        "system": {
            "version": "2.0.0",
            "uptime_seconds": get_uptime(),
        }
    }
```

**交付物**：新增API端点 + Web前端仪表盘页面
**验收**：打开页面可看到系统健康、任务状态、成本消耗

### Phase 3 验收标准

- [ ] 12个SOP模板全部改进，冒烟测试通过
- [ ] `frost` CLI可交互式执行任务
- [ ] 邮件通知配置可用
- [ ] 可观测性面板显示系统健康、任务、成本、Agent状态

---

## Phase 4: 债务清偿（Week 7-8）

### 目标
清理20+审计报告的遗留债务，建立修复闭环。

### 任务清单

#### P4-1: 审计发现转Issue（4小时）

**现状**：`audit_materials/`和`audit_results/`堆积20+文件
**目标**：每个P0/P1发现转成GitHub Issue或本地追踪

```markdown
# docs/audit_tracker.md（已存在，更新）
| 发现ID | 位置 | 严重 | 状态 | 修复PR | 验证方式 | 到期 |
|--------|------|------|------|--------|---------|------|
| AUD-001 | core/db.py L45 | P0 | ✅ | #123 | test_db_connection.py | 2026-06-20 |
| AUD-002 | skills/llm.py L283 | P1 | ⏳ | - | 手动验证temperature | 2026-06-30 |
```

**交付物**：更新后的`docs/audit_tracker.md`
**验收**：所有P0发现标记为"已修复"或"有明确修复计划"

#### P4-2: 文档重写（6小时）

**目标**：一份文档让"未来的你"能接手

| 文档 | 内容 | 读者 |
|------|------|------|
| `README.md` | 项目简介、5分钟启动、架构图 | 新用户 |
| `docs/ARCHITECTURE.md` | 模块关系、数据流、决策记录 | 开发者 |
| `docs/OPERATIONS.md` | 日常运维、故障排查、回滚 | 运维者 |
| `docs/DEPLOYMENT.md` | 部署步骤、环境变量、依赖 | 部署者 |

**交付物**：4份文档
**验收**：找一个人（或你自己一周后）按文档能独立启动项目

#### P4-3: 版本发布（2小时）

```bash
# 打tag，写release note
git tag -a v2.0.0 -m "FROST-SOP V2.0: 健壮性升级"
```

**Release Note模板**：
```markdown
## FROST-SOP V2.0.0

### 新增
- Skill V2：重试、降级、超时、验证
- 统一配置中心：config/frost.yaml
- CLI工具：frost命令行
- 邮件通知通道
- 可观测性仪表盘
- 真实模式冒烟测试

### 改进
- 12个SOP模板全部标准化
- LLM temperature按任务类型自动映射
- API支持profile参数
- 错误处理统一化

### 修复
- 所有P0审计发现（见audit_tracker.md）
- API层temperature硬编码
- Skill层无错误处理

### 已知问题
- 覆盖率70%，目标80%（V2.1）
- IM通知未实现（V2.1）
```

### Phase 4 验收标准

- [ ] 所有P0审计发现已修复或已有计划
- [ ] 4份核心文档完整
- [ ] v2.0.0 tag已打
- [ ] Release Note已写

---

## 四、资源预算

| 资源 | 需求 | 说明 |
|------|------|------|
| **时间** | 8周，每周~10小时 | 共80小时，符合瀑布式节奏 |
| **Token预算** | +¥50/月 | 冒烟测试+集成测试消耗，可控 |
| **外部依赖** | 0 | 不引入新框架，用现有工具 |
| **学习成本** | 低 | 每个任务都有具体代码示例 |

---

## 五、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Skill V2改造破坏现有功能 | 中 | 高 | 保留skill.py，skill_v2.py增量使用，逐步迁移 |
| 真实LLM测试消耗超预期 | 低 | 中 | 冒烟测试限制3分钟/次，集成测试手动触发 |
| 8个SOP模板改进返工 | 中 | 中 | 先改2个→验证→批量改剩余6个 |
| 文档写完没人看 | 高 | 低 | 用"未来的你能否看懂"作为验收标准 |

---

## 六、FROST哲学坚守检查清单

| 原则 | 检查项 | 本方案如何遵守 |
|------|--------|---------------|
| **SOP驱动** | 所有功能是否通过SOP模板配置？ | Phase 3全量改进12个模板，新增功能（CLI/邮件）也有SOP定义 |
| **分形治理** | 是否保持Ancestor→Parent→5孙辈架构？ | 不改动Agent体系，只加固Skill执行层 |
| **AI是杠杆** | 是否减少而非增加人工工作？ | CLI自动化、邮件通知、自动重试都减少人工盯盘 |
| **数据主权** | 是否本地优先？ | SQLite+本地配置+本地日志，不引入云依赖 |
| **可观测性** | 是否能看见系统状态？ | Phase 3可观测性面板，成本/任务/Agent一目了然 |

---

> **最终判断**：这不是"重构"，而是"加固"。FROST-SOP的骨架（Agent体系、数据库、API）已经成型，需要做的是让血肉（Skill执行、测试真实性、配置管理）配得上骨架的强度。8周后，你将拥有一个能放心托付任务的系统——而不是一个需要你一直盯着修修补补的玩具。
