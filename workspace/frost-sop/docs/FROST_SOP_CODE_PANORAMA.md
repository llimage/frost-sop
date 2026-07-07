# FROST-SOP 代码全景检查报告

> 检查日期：2026-06-17
> 检查范围：核心模块 80%（~8,000/10,000 行）、Agent 层 100%、Skills 层 50%、API 层 100%、配置 100%
> 方法：静态代码分析，不依赖运行时

---

## 一、代码量统计与模块分布

| 模块 | 文件数 | 估计行数 | 占比 | 质量评估 |
|------|--------|---------|------|---------|
| **core/**（核心） | 20+ | ~4,800 | 48% | 分化严重 |
| **skills/**（技能） | 25+ | ~3,000 | 30% | 参差不齐 |
| **agents/**（代理） | 3 | ~1,300 | 13% | 设计良好 |
| **api/**（接口） | 2 | ~1,000 | 10% | 功能完整 |
| **stores/**（存储） | 2 | ~200 | 2% | 简单有效 |
| **tests/**（测试） | 107 | ~29,500 | — | 模拟模式为主 |
| **SOP 模板** | 12 | ~800 | — | 半成 |

**总代码量（不含测试）**：~10,300 行 Python
**测试代码量**：~29,500 行（2.8 倍于生产代码）

---

## 二、模块依赖图

```
                    ┌─────────────┐
                    │  frontend   │  ← Next.js (未读细节)
                    └──────┬──────┘
                           │ REST API
                    ┌──────▼──────┐
                    │  api/main   │  ← FastAPI, 15端点, 842行
                    │  (models)   │  ← Pydantic模型
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐     ┌─────▼─────┐    ┌─────▼─────┐
    │ ancestor│     │  parent   │    │   elder   │  ← agents/ (分形治理)
    │(gen=0)  │     │(gen=1..N)│    │ (audit)  │
    └────┬────┘     └─────┬─────┘    └─────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
                   ┌──────▼──────┐
                   │ core/agent  │  ← Agent基类, 577行, 重试+生命周期
                   └──────┬──────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    ┌────▼────┐    ┌─────▼─────┐   ┌────▼────┐
    │core/skill│    │ core/store│   │core/sop │  ← 基础组件
    │ (35行)  │    │ (342行)  │   │ (111行)│
    └────┬────┘    └─────┬─────┘   └────┬────┘
         │               │             │
         │    ┌──────────┼──────────┐ │
         │    │          │          │ │
    ┌────▼────▼────┐ ┌───▼────┐ ┌───▼────┐ ┌────▼────┐
    │ core/db      │ │cost.py│ │event_bus│ │monitor │
    │ (1200行)     │ │(224行)│ │(699行) │ │(103行)│
    │ 数据库        │ │预算   │ │事件   │ │性能   │
    └──────────────┘ └───────┘ └───────┘ └───────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
         ┌────▼────┐ ┌───▼────┐ ┌────▼────┐
         │workbench│ │decision│ │dead_mans│
         │(498行)  │ │manager │ │switch   │
         │工作台    │ │(291行) │ │(229行)  │
         └─────────┘ └────────┘ └─────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
         ┌────▼────┐ ┌───▼────┐ ┌────▼────┐
         │llm.py   │ │web_fetch│ │orchestr │  ← skills/
         │(591行)  │ │(181行) │ │(1332行)│
         │LLM调用   │ │网页抓取 │ │编排     │
         └─────────┘ └────────┘ └─────────┘
```

---

## 三、关键发现（按严重程度）

### 🔴 P0 — 架构级问题

#### P0-1: `core/skill.py` 是整个系统最脆弱的环节（35行，无防护）

```python
# 当前代码（skill.py:25-35）
def execute(self, context: dict) -> dict:
    """
    Execute the skill function.
    """
    return self._func(context)  # ← 没有任何try/catch
```

**与依赖它的模块对比**（讽刺）：
| 依赖者 | 防护级别 | 行数 |
|--------|---------|------|
| `core/agent.py` | 重试3次 + 备用Skill + 错误上报 | 577 |
| `core/db.py` | SQL注入3层防护 + 写锁 + WAL | 1200 |
| `core/skill.py` | **裸函数调用** | **35** |

**影响**：Agent 的 `_execute_step_with_retry` 在 skill 层抛异常时才能捕获。但如果 Skill 内部死循环、内存泄漏、或返回非 dict 类型，**Agent 层的重试完全无效**。

#### P0-2: `api/main.py` 硬编码 `temperature=0.7`（已修复，但模式存在）

已修复，但检查发现**还有多处硬编码**：
- `conftest.py:11`：`FROST_TESTING` 强制 `"1"`
- `api/main.py:480`（原）：`"_temperature": 0.7`
- `core/workbench.py:21-58`：DEFAULT_PROJECTS 硬编码 revenue_monthly
- `skills/llm.py:283`：默认 `temperature=0.7`（虽然下面有 profile 覆盖，但默认值仍高）

#### P0-3: `conftest.py` 是"单点失效"设计

```python
# conftest.py:11
os.environ.setdefault("FROST_TESTING", "1")
```

这行代码意味着：**所有测试默认不调用真实 LLM**。导致：
- `llm.py` 的 `call_llm` 函数有两条路径（online/offline），测试永远只走 offline
- 温度映射、缓存、成本追踪、错误处理等**全部未在测试中验证**
- 107 个测试文件 × 数千次调用 = 零次真实 API 测试

**这不是测试策略，是自我欺骗。**

---

### 🟠 P1 — 设计级问题

#### P1-1: `core/sop.py` 验证器是"空壳"

```python
# sop.py:70-110
class SOPValidator:
    def validate(self, sop: SOP, rules: dict) -> dict:
        errors = []
        # 检查 required stages
        for stage_name in required:
            if not any(s.get("name") == stage_name for s in sop.stages):
                errors.append(...)
        # 检查 forbidden skills
        for skill_name in forbidden:
            ...
        # 检查 budget limit
        if max_budget is not None and hasattr(sop, "budget"):
            ...
        return {"valid": len(errors) == 0, "errors": errors}
```

**实际检查能力**：
- ✅ 是否包含 required stages（名字匹配）
- ✅ 是否使用了 forbidden skills（名字匹配）
- ✅ 预算是否超限（如果 sop 有 budget 属性）
- ❌ **不检查 YAML 格式合法性**（load_from_yaml 用裸 open + yaml.safe_load）
- ❌ **不检查 stage 结构完整性**（stage 是否有 name/skill/requirement？）
- ❌ **不检查技能是否存在**（skill 名字在不在 skills 目录？）
- ❌ **不检查循环依赖**（SOP A 引用 SOP B，B 引用 A）

**SOP 是"宪法"，但宪法的解释器只检查封面有没有写名字。**

#### P1-2: `core/event_bus.py` 和 `core/agent.py` 有**两个事件总线**

```python
# event_bus.py:128-153
class EventBus:          # 同步总线（threading.Lock）
    _instance = None

# event_bus.py:437-474
class AsyncEventBus:     # 异步总线（asyncio.Lock）
    _instance = None
```

**问题**：
- 两个单例，互不干扰，但代码逻辑几乎完全相同（复制粘贴）
- 同步 Agent 用 EventBus，异步 Agent 用 AsyncEventBus
- 如果同步代码订阅了 EventBus，异步代码发布到 AsyncEventBus，**事件丢失**
- 没有文档说明什么时候用哪个

#### P1-3: `core/memory.py` 的降级模式是"假向量数据库"

```python
# memory.py:128-148
if self.fallback_mode:
    # 降级模式：简单的关键词匹配
    query_words = set(query.lower().split())
    for mem in self._memory_keywords:
        text_words = set(mem["text"].lower().split())
        overlap = len(query_words & text_words)
        if overlap > 0:
            results.append({..."score": overlap / len(query_words)})
```

当 ChromaDB 不可用时，返回的是**关键词匹配结果**，不是向量相似度。对于"如何优化 LLM"查询，可能匹配到"优化数据库"的记忆（都有"优化"），**语义完全不相关**。

---

### 🟡 P2 — 代码级问题

#### P2-1: `core/db.py` 的 `_migrate_table` 有安全检查误报

```python
# db.py:487-494
if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col_name):
    continue  # 跳过非法列名
if not re.match(r"^[A-Z]+\s*(DEFAULT\s+[^;\-]*|)$", col_def, re.IGNORECASE):
    continue  # 跳过非法列定义
```

**误报场景**：
- `updated_at` → `updated` 匹配 `UPDATE` 关键词 → 误报
- `timestamp` → 列定义包含 `DEFAULT CURRENT_TIMESTAMP` → 通过
- `TEXT DEFAULT ''` → 包含单引号，但正则 `[^;\-]*` 允许 → 通过

#### P2-2: `core/llm.py` 缓存机制可能返回过时响应

```python
# llm.py:55-77
_LLM_CACHE: dict[str, dict] = {}
_LLM_CACHE_MAX_SIZE = 500

def _cache_key(context: dict) -> str | None:
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

**缓存 key 不包含**：
- 当前日期（时间敏感信息如"今天"会返回昨天的缓存）
- Agent ID（不同 Agent 的相同 prompt 会共享缓存，导致信息泄露）
- 任务 ID（不同任务的相同 prompt 会共享缓存）

#### P2-3: `api/models.py` 的 `TaskCreateRequest` 默认 `use_real_llm=False`

```python
# api/models.py:23
class TaskCreateRequest(BaseModel):
    description: str = Field(..., min_length=1)
    sop_id: str = Field(default="DEV-001")
    project_id: str = Field(default="default")
    use_real_llm: bool = Field(default=False)  # ← 默认不走真实LLM
```

API 入口默认使用模拟模式，即使系统配置为真实模式。**前端用户不主动勾选，就永远得不到真实LLM输出。**

---

## 四、代码质量矩阵

| 模块 | 行数 | 错误处理 | 测试覆盖 | 文档 | 复杂度 | 评分 |
|------|------|---------|---------|------|--------|------|
| `core/db.py` | 1200 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 中等 | **A-** |
| `core/agent.py` | 577 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 中等 | **B+** |
| `core/event_bus.py` | 699 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 高 | **B** |
| `core/llm.py` | 591 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 中等 | **B-** |
| `core/skill.py` | 35 | ⭐ | ⭐⭐⭐ | ⭐⭐ | 低 | **D+** |
| `core/sop.py` | 111 | ⭐⭐ | ⭐⭐ | ⭐⭐ | 低 | **C** |
| `core/workbench.py` | 498 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 中等 | **C** |
| `core/decision_manager` | 291 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 中等 | **B-** |
| `api/main.py` | 842 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 中等 | **B-** |
| `agents/ancestor.py` | 110 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 低 | **B+** |
| `agents/parent.py` | 179 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 低 | **B+** |
| `agents/elder.py` | 1002 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 高 | **B** |

---

## 五、架构一致性检查

### FROST 哲学遵守情况

| 原则 | 设计意图 | 实际代码 | 偏差 |
|------|---------|---------|------|
| **SOP 驱动** | 所有行为由外部 SOP 定义 | `SOPValidator` 为空壳，`load_from_yaml` 无验证 | ⚠️ 中等偏差 |
| **分形治理** | Ancestor→Parent→Child | `create_ancestor`, `create_parent`, `spawn` 清晰分层 | ✅ 遵守 |
| **AI 是杠杆** | LLM 只处理必要环节 | `llm.py` 缓存+成本追踪，但 API 默认模拟 | ⚠️ 轻度偏差 |
| **数据主权** | 本地优先，SQLite | 所有数据本地 SQLite，无云服务依赖 | ✅ 遵守 |
| **可观测性** | 成本/事件/审计全链路 | `cost_log`, `event_log`, `audit_log` 都有 | ✅ 遵守 |
| **Skill 是蛋白** | 无状态能力单元 | `skill.py` 35行，确实无状态，但无防护 | ⚠️ 过度简化 |

---

## 六、测试体系真相

| 指标 | 数值 | 问题 |
|------|------|------|
| 测试文件 | 107 | 数量充足 |
| 测试行数 | ~29,500 | 2.8倍于生产代码 |
| 覆盖率 | 80.18% | 高但 misleading |
| 真实LLM测试 | 0 | **致命** |
| 集成测试 | 有（mock） | 不验证端到端 |
| 属性测试（hypothesis） | 有 | 只测边界条件，不测业务逻辑 |
| 混沌测试 | 有 | 只测异常注入，不测恢复能力 |
| 负载测试（locust） | 有 | 未验证 |

**测试覆盖的盲区**：
1. `llm.py` 的 `call_llm` 函数（online 路径）→ 0 覆盖
2. `api/main.py` 的 FastAPI 端点 → 覆盖但 mock
3. `core/db.py` 的并发场景（WAL + 写锁）→ 未测
4. `core/event_bus.py` 的多线程事件竞争 → 未测
5. `agents/` 的事件驱动模式 → 未测

---

## 七、与之前审计的交叉验证

| 之前审计发现 | 代码验证结果 | 状态 |
|------------|------------|------|
| `skill.py` 无错误处理 | ✅ 确认：35行，裸 `return self._func(context)` | 未修复 |
| `api/main.py` temperature 硬编码 | ✅ 已修复（`_llm_profile` 替代） | 已修复 |
| `workbench.py` 假数据 | ✅ 确认：DEFAULT_PROJECTS 硬编码 revenue | 未修复 |
| 测试全部 mock | ✅ 确认：`conftest.py:11` 强制 FROST_TESTING=1 | 未修复 |
| SQL 安全检查误报 | ✅ 确认：`_migrate_table` 的 `updated_at` 误报 | 已 workaround |
| 覆盖率 80% 是幻觉 | ✅ 确认：高覆盖率但关键路径未测 | 未修复 |

---

## 八、代码中的"好设计"（值得保留）

| 设计 | 位置 | 说明 |
|------|------|------|
| **DBManager 单例 + WAL** | `db.py:95-106` | SQLite WAL 模式 + busy_timeout + 写锁，解决并发 |
| **SQL 注入三层防护** | `db.py:18-43, 626-632` | 表名白名单 + 列名正则 + WHERE 关键词过滤 |
| **Agent 重试机制** | `agent.py:317-423` | 3 次重试 + 指数退避 + 备用 Skill 切换 |
| **生命周期追踪** | `agent.py:181-213` | created → running → destroyed，写入数据库 |
| **事件总线敏感数据过滤** | `event_bus.py:342-367` | API key/token 等自动替换为 `***REDACTED***` |
| **成本熔断** | `cost.py:30-142` | 月度预算 ¥300，80% 预警，100% 熔断 |
| **路径遍历防护** | `path_safety.py` | OWASP ASVS 4.0 L1 合规，相对路径检查 |
| **JSON 安全解析** | `json_safety.py` | 深度限制、长度限制、数值溢出防护 |
| **API Key 加密** | `secrets.py` | AES-256-GCM + PBKDF2HMAC，机器绑定 |
| **死人开关** | `dead_mans_switch.py` | 30 分钟无事件触发告警，防止静默失败 |

---

## 九、全景检查结论

### 总体评估：B-（可用但有明显裂缝）

**代码层面的真实状态**：
- ✅ **架构骨架完整**：分形治理、SOP 驱动、事件总线、成本追踪——概念都实现了
- ✅ **基础设施成熟**：数据库、API、加密、安全、监控——有企业级意识
- ⚠️ **执行层脆弱**：Skill 基类 35 行无防护、SOP 验证器空壳、测试自欺欺人
- ⚠️ **重复代码**：EventBus/AsyncEventBus、多处硬编码、workaround 而非修复根因
- ❌ **业务数据虚假**：workbench.py 的 revenue 是硬编码的，不是真实业务数据

### 核心判断

> **FROST-SOP 是一个"骨架比肌肉强壮"的系统。DB 层、Agent 层、API 层的设计是好的，但 Skill 层（实际执行单元）和 SOP 层（业务规则）太薄弱，导致上层的好设计无法真正保护业务执行。**

### 与之前评估的一致性

| 维度 | 之前评估 | 代码验证后 |
|------|---------|-----------|
| 总体评分 | B- | **B-**（一致） |
| 最脆弱模块 | skill.py | **skill.py**（一致） |
| 最大风险 | 测试自欺欺人 | **测试自欺欺人**（一致） |
| 最成熟模块 | db.py | **db.py**（一致） |
| 假数据问题 | workbench.py | **workbench.py**（一致） |
| 新发现 | — | **EventBus 双轨制、缓存 key 缺陷、API 默认模拟** |

---

> **最终诚实结论**：代码全景检查确认了之前的所有判断，没有推翻之前的结论，但发现了 3 个新的代码级问题（EventBus 双轨制、缓存 key 缺陷、API 默认模拟）。系统整体架构设计是正确的，但执行层和测试层需要加固。这不是"重写"的问题，而是"补漏洞"的问题——预计 4-6 小时可以修复所有 P0/P1 问题。
