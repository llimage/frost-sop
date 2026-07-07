# FROST-SOP V7 全量诚实审计报告

> 审计日期：2026-06-17
> 审计范围：核心模块（db/agent/sop/llm/skill/workbench/web_fetcher）+ 测试体系 + 架构一致性
> 审计标准：不是"有多少测试"，而是"测试有没有测到真正会坏的地方"

---

## 一、总体判断（先给结论）

**当前状态：B-（可用但有明显裂缝）**

| 维度 | 评分 | 说明 |
|------|------|------|
| **代码质量** | B+ | db.py/agent.py优秀，skill.py/workbench.py有明显问题 |
| **测试质量** | B- | 覆盖率高但关键路径未测，全部模拟模式 |
| **架构一致性** | B | FROST哲学有体现，但部分模块偏离 |
| **生产就绪度** | C+ | 能跑，但遇到边界情况会崩 |

**核心发现：80%的覆盖率是一个"舒适的幻觉"——它覆盖了行数，但没有覆盖"真实世界会坏的方式"。**

---

## 二、逐模块审计

### 2.1 core/db.py — 评分：A-（项目最佳模块）

**优点（真正优秀）**：
- ✅ SQL注入三层防护：表名白名单+列名正则验证+WHERE子句关键词过滤
- ✅ WAL模式+ busy_timeout=5000，解决SQLite并发写锁定
- ✅ 19张表的标准化迁移机制（`_migrate_table`通用函数）
- ✅ 性能索引全覆盖（22个索引，覆盖所有高频查询列）
- ✅ 连接池管理（单例模式+自动重连）

**问题（减分项）**：
- ⚠️ `ALLOWED_TABLES`是硬编码集合，新增表需要手动维护（已发现workbench的3张表漏加）
- ⚠️ `execute_sql`方法的SQL注入警告注释是"免责声明"而非"真正的安全"——它接受任意SQL
- ⚠️ `_WHERE_DANGEROUS_KEYWORDS`检查过于粗暴：`updated_at`列名触发`UPDATE`误报（已发现）

**诚实结论**：这是整个项目最成熟、最接近生产级的模块。把它交给一个DBA审查，反馈会是"基本可用，细节待打磨"。

---

### 2.2 core/agent.py — 评分：B+（设计良好，有隐患）

**优点**：
- ✅ 重试机制：max_retries + retry_delay + 备用Skill切换（`_find_alternate_skill`）
- ✅ 生命周期追踪：created → running → destroyed，写入agent_status表
- ✅ 事件驱动：event_driven模式，步骤完成后发布STEP_COMPLETED事件
- ✅ 错误上报：max retries时回调`on_max_retries`给祖辈Agent
- ✅ 内存管理：`_cleanup()`释放循环引用

**问题**：
- ⚠️ **最严重的隐患**：`run()`方法在`finally`中调用`destroy()`，但`destroy()`会写数据库。如果数据库写入失败（磁盘满、权限问题），异常被静默捕获（`logger.warning`），但Agent状态已被设为"destroyed"——**这意味着一个"已销毁"的Agent可能还在被使用**。
- ⚠️ `_execute_step_with_retry`中`time.sleep(self._retry_delay_seconds)`是同步阻塞——如果Agent在处理Web请求，会卡住整个线程。
- ⚠️ `_find_alternate_skill`的备用逻辑过于简单：只是加`_backup`后缀或前缀匹配，实际生产中很少有用。
- ⚠️ `run()`在失败时`raise execution_error`，但`destroy()`已经在`finally`中执行了——如果销毁时也失败，原始错误被覆盖。

**关键代码隐患（第167-173行）**：
```python
finally:
    self.destroy()  # ← 如果这里抛异常，execution_error可能丢失

if execution_error:
    raise execution_error  # ← 但destroy()的异常已被吞掉
```

**诚实结论**：设计思路正确，但"错误处理中的错误处理"有漏洞。高并发场景下会出问题。

---

### 2.3 skills/llm.py — 评分：B（功能完整，有硬编码残留）

**优点**：
- ✅ 三重模型支持：在线/离线/测试模式
- ✅ 温度profile映射已加（execute/create/review）
- ✅ Token消耗追踪（成本日志）
- ✅ 失败日志记录（`_write_failure_log`）
- ✅ API密钥缺失时优雅降级

**问题**：
- ⚠️ **第283行**：`temperature = context.get("_temperature", 0.7)`——默认值0.7仍然偏高，虽然下面有profile覆盖，但如果用户既没传`_temperature`也没传`_llm_profile`，就fallback到0.7
- ⚠️ `api/main.py`第480行仍然硬编码`temperature=0.7`——**LLM温度修复没有在API层生效**
- ⚠️ 没有超时控制：如果DeepSeek API挂起，`client.chat.completions.create()`会无限等待
- ⚠️ 没有token预算检查：调用前不检查本月是否已超预算
- ⚠️ `call_llm`返回的是修改后的`context` dict，不是新对象——调用方可能意外修改LLM的响应

**诚实结论**：功能完整，但"默认值陷阱"和"API层不同步"是生产事故的温床。

---

### 2.4 core/sop.py — 评分：C（过于简单，缺验证）

**现状**：111行，只有基本的YAML加载和简单的validate框架。

**问题**：
- ❌ **没有阶段结构验证**：加载YAML后，不检查每个stage是否有`name`、`skill`、`prompt`等必需字段
- ❌ **没有循环依赖检测**：SOP A引用SOP B，SOP B引用SOP A——会导致无限递归
- ❌ **没有版本兼容性检查**：V1.0的SOP在V2.0的引擎上执行，可能字段不匹配
- ❌ `validate()`方法只有框架，没有具体规则实现
- ❌ `load_from_yaml()`使用裸`open()`，没有路径安全检查（虽然`core/path_safety.py`存在，但sop.py没用它）

**诚实结论**：这是"骨架有了，血肉没有"。SOP是整个系统的"宪法"，但宪法的解释器几乎为空。

---

### 2.5 core/skill.py — 评分：D+（整个系统最脆弱的环节）

**现状**：35行，裸函数包装器。

**问题**：
- ❌ **无错误处理**：`execute()`直接`return self._func(context)`，任何异常直接上抛
- ❌ **无输入验证**：不检查context是否有必需字段
- ❌ **无输出验证**：不检查返回值是否为dict
- ❌ **无超时**：Skill函数可能无限运行
- ❌ **无重试**：依赖外层Agent的重试，但Skill本身无重试策略
- ❌ **无降级**：失败时没有其他选择

**与其他模块的对比（讽刺）**：
| 模块 | 行数 | 错误处理 |
|------|------|---------|
| db.py | 1000+ | 三层SQL注入防护 |
| agent.py | 577 | 重试+上报+备用Skill |
| skill.py | 35 | **无任何错误处理** |

**诚实结论**：这是整个系统的"阿喀琉斯之踵"。db.py和agent.py做了那么多防护，但Skill作为执行单元没有任何自我保护——就像一个身穿重甲的骑士，手里拿的却是一把木剑。

---

### 2.6 core/workbench.py — 评分：C（功能可用，数据造假）

**问题**：
- ❌ **硬编码虚假数据**：`revenue_monthly: 34200`、`revenue_monthly: 6000`、`revenue_monthly: 15000`——这些是写死的数字，不是从数据库读取的
- ❌ `get_recommended_task()`中的`task_scenarios`是硬编码的模拟数据——每次调用返回相同的"实现用户权限管理的RBAC模块"
- ❌ `generate_daily_narrative()`使用`execute_sql`绕过安全检查——这是**用 workaround 掩盖 root cause**，而不是修复安全检查的误报逻辑
- ⚠️ `_build_task_recommendation`的"能量匹配"逻辑极其简单：>=60=match, >=30=partial, <30=mismatch——没有实际的任务-能量关联分析

**关键代码（第33-57行）**：
```python
DEFAULT_PROJECTS = [
    {
        "id": "saas",
        "name": "轻云SaaS",
        ...
        "revenue_monthly": 34200,  # ← 硬编码，不是真实数据
    },
    ...
]
```

**诚实结论**：这是一个"演示级"模块——功能有，但数据是假的。如果廖亮真的靠这个做决策，会被误导。

---

### 2.7 skills/web_fetcher.py — 评分：B（功能可用，测试好）

**优点**：
- ✅ HTML解析有安全过滤（跳过script/style/nav/footer/header）
- ✅ 字符数限制（防止内存爆炸）
- ✅ 搜索失败优雅降级（返回空列表）
- ✅ 测试覆盖好（mock网络请求，测试解析逻辑）

**问题**：
- ⚠️ `_duckduckgo_search`依赖HTML解析class名——如果DuckDuckGo改版，会静默失败
- ⚠️ 没有User-Agent设置，可能被目标网站拦截
- ⚠️ 没有robots.txt检查

---

## 三、测试体系审计（重点）

### 3.1 覆盖率数字的真相

| 指标 | 数值 | 可信度 |
|------|------|--------|
| 行覆盖率 | 80.18% | ⚠️ 高但 misleading |
| 测试文件数 | ~1488 | ✅ 数量充足 |
| 真实LLM测试 | 0 | ❌ **致命缺陷** |
| 集成测试 | 有但模拟 | ⚠️ 未验证端到端 |

### 3.2 测试质量的深层问题

**问题1：所有测试在`FROST_TESTING=1`模式下运行**

这意味着：
- LLM调用返回的是模拟响应（"模拟的LLM响应"）
- Token消耗是0
- 成本追踪是假数据
- 温度参数是否生效？**未验证**
- 重试逻辑在真实API超时场景下是否工作？**未验证**

**问题2：新增测试测了"会工作的路径"，没测"会坏的路径"**

以`test_workbench_coverage.py`为例：
- ✅ 测了`ensure_default_projects`能创建项目
- ❌ **没测**：如果数据库被锁，`ensure_default_projects`会怎么做？
- ❌ **没测**：如果`DEFAULT_PROJECTS`被修改（如少了一个字段），插入会失败吗？
- ❌ **没测**：`get_recommended_task`在energy_log为空时的行为

**问题3：测试发现了bug，但修复是workaround而非root cause**

- 发现：`_migrate_table`的列名检查`^[A-Z]+`太严格，`updated_at`的`updated`触发`UPDATE`关键词
- 修复：workbench.py改用`execute_sql`绕过检查
- **正确修复**：应该修改`_WHERE_DANGEROUS_KEYWORDS`或列名检查逻辑

### 3.3 测试的真正价值

**这次覆盖率提升的真正价值不是"80%"这个数字，而是**：
1. 发现了`ALLOWED_TABLES`漏了3张表
2. 发现了SQL安全检查的误报问题
3. 验证了workbench的迁移逻辑确实能创建表

**但这些价值来自"写测试的过程"，而非"覆盖率数字本身"。**

---

## 四、架构一致性审计

### 4.1 FROST哲学遵守情况

| 原则 | 状态 | 证据 |
|------|------|------|
| **SOP驱动** | ⚠️ 部分遵守 | SOP模板存在，但sop.py验证器几乎为空 |
| **分形治理** | ✅ 遵守 | Ancestor→Parent→5孙辈架构清晰 |
| **AI是杠杆** | ⚠️ 有偏离 | workbench.py的硬编码数据让AI变成了"假数据展示器" |
| **数据主权** | ✅ 遵守 | SQLite本地存储，无云依赖 |
| **可观测性** | ⚠️ 半成 | 有成本追踪、有审计日志，但无统一仪表盘 |

### 4.2 模块间耦合度

```
db.py ←── 被所有模块依赖（合理，是基础设施）
  ↑
agent.py ←── 依赖 db.py, store.py, skill.py
  ↑
skill.py ←── 依赖 无（最底层，但被Agent调用）
  ↑
llm.py ←── 依赖 db.py（成本追踪）
  ↑
workbench.py ←── 依赖 db.py
  ↑
api/main.py ←── 依赖 几乎所有模块（合理的聚合层）
```

**耦合评估**：整体合理，但`api/main.py`第305-339行的错误处理是裸`except Exception`——如果任何底层模块抛异常，API返回500，但前端无法区分是"LLM挂了"还是"数据库挂了"。

---

## 五、诚实的问题清单（按优先级排序）

### P0 — 立即修复（今天）

| # | 问题 | 位置 | 影响 | 修复成本 |
|---|------|------|------|---------|
| 1 | **api/main.py仍用temperature=0.7** | api/main.py:480 | LLM温度修复在API层未生效 | 1行代码 |
| 2 | **skill.py无任何错误处理** | core/skill.py:25-35 | 一个Skill挂=整个任务链断 | 半天重写 |
| 3 | **workbench.py数据造假** | core/workbench.py:33-57 | 用户决策基于假数据 | 半天重构 |

### P1 — 本周修复

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 4 | **sop.py验证器为空** | core/sop.py:65-80 | 加载损坏的SOP模板会静默失败 |
| 5 | **llm.py无超时控制** | skills/llm.py:309 | API挂起=请求无限等待 |
| 6 | **agent.pydestroy()异常丢失** | core/agent.py:167-173 | 错误信息可能被覆盖 |
| 7 | **SQL安全检查误报未根治** | core/db.py:46-61 | 合法列名被误拦截 |

### P2 — 本月修复

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 8 | **测试全部模拟模式** | conftest.py, CI | 覆盖率数字不代表真实可靠性 |
| 9 | **workbench.py用execute_sql绕过检查** | core/workbench.py:317 | 技术债务，应修root cause |
| 10 | **无token预算预检查** | skills/llm.py | 可能超预算运行 |

---

## 六、对"80%覆盖率"的最终判断

### 这个数字意味着什么

- ✅ 大部分代码路径被走过至少一次
- ✅ 明显的语法错误、导入错误会被发现
- ✅ 模块间的接口契约有基本验证

### 这个数字不意味着什么

- ❌ **不代表LLM调用可靠**（全部mock）
- ❌ **不代表错误处理正确**（测试只测happy path）
- ❌ **不代表生产可用**（没有负载测试、没有故障注入）
- ❌ **不代表数据正确**（workbench的假数据通过了测试）

### 一个类比

> 你有一辆车，80%的零件都检查了——但检查方式是"在停车状态下按按钮看灯亮不亮"。你从来没有真正发动过引擎，也没有开过上路。然后你说"这辆车80%检查通过，可以开去西藏"。

**80%覆盖率在FROST-SOP的真实含义："静态检查通过，动态行为未验证"。**

---

## 七、建议的下一步（不是V2.0大改造，是止血）

基于这次审计，我**不推荐**立即执行之前制定的8周V2.0大改造计划。更紧急的是先修P0和P1的问题。

### 本周止血清单（3天）

**Day 1（今天）**：
1. 修复`api/main.py`第480行：`temperature=0.7` → 读取profile配置
2. 重写`core/skill.py`：加错误处理、输入验证、输出验证

**Day 2**：
3. 修复`core/db.py`的SQL安全检查误报：`_WHERE_DANGEROUS_KEYWORDS`不应匹配列名，只匹配SQL操作符位置
4. 修复`core/agent.py`的异常丢失问题：用`contextlib.suppress`或嵌套try/except保护destroy()

**Day 3**：
5. 给`workbench.py`的硬编码数据加注释："TODO: 从数据库读取真实数据"
6. 给`skills/llm.py`加超时控制：`client.chat.completions.create(timeout=30)`

### 验证方式

不要看覆盖率数字。验证方式是：
- [ ] 用API调一次chat，确认temperature=0.1生效（检查响应的确定性）
- [ ] 写一个故意抛异常的Skill，确认任务链不中断
- [ ] 用`updated_at`列名做一次select_all，确认不触发安全误报

---

> **最终诚实结论**：FROST-SOP不是"工程化不足"，而是"两极分化严重"——有的模块（db.py）是企业级的，有的模块（skill.py）是草稿级的。80%覆盖率掩盖了这种分化：它让差的模块看起来也没那么差。真正的风险不在"没覆盖的20%"，而在"已覆盖但测试方式错误的80%"。
