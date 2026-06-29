# FROST白皮书（最终版）vs 代码实现：差距映射与V4.0路线图

**映射日期**: 2026-06-28
**代码版本**: V3.2b（`8634afb`）
**映射原则**: 诚实、逐项、不夸大、不缩小

---

## 一、总体实现度评估

| 白皮书层级 | 代码对应 | 实现度 | 说明 |
|-----------|---------|--------|------|
| 四个原子（Store/Skill/Agent/SOP） | `core/store.py`, `core/skill.py`, `core/agent.py`, `core/sop.py` | **95%** | 核心模型完整，向后兼容事件驱动扩展 |
| 协议① 记忆层级继承 | `core/store.py` HierarchicalStore | **100%** | 单向读取链 + 祖先只读约束已验证 |
| 协议② SOP宪法校验 | `skills/orchestration.py` validate_sop | **100%** | 祖辈调用 → 父辈加载前校验 |
| 协议③ 代际限制 | `core/agent.py` spawn() + max_spawn_generation | **100%** | 超限抛出 PermissionError |
| 协议④ 选择性持久化 | `skills/orchestration.py` merge_from | **80%** | 收割逻辑存在，但**质量评分闸门（三方加权）缺失** |
| 协议⑤ 盈利能力管理 | `core/cost.py` + `core/workbench.py` | **60%** | 成本追踪 ✅，收入追踪静态（写死），**三级亏损预警（黄/红/灭门）缺失** |
| 协议⑥ 狩猎 | `skills/search.py` + `skills/search_gitee.py` | **40%** | 单次搜索 ✅，**持续运行、多斥候并行、自动比对/校验/试炼 缺失** |
| 免疫系统 — 心跳P0 | `skills/watchdog.py` + `core/dead_mans_switch.py` | **85%** | 心跳发送/监控 ✅，死人开关 ✅，Dead Man's Watch ✅。但**孙辈300秒超时监控未实现** |
| 免疫系统 — 呼吸P1 | `skills/orchestration.py` execute_stage | **40%** | 单阶段失败检测存在，但**"连续两阶段失败自动熔断"未显式实现** |
| 免疫系统 — 体检P2 | `agents/elder.py` audit_family | **70%** | 长老审计 ✅，但**父辈连续失败趋势、孙辈超时频率、军师建议否决趋势 等专项监控缺失** |
| 府兵系统 | `agents/ancestor.py`, `agents/parent.py`, `skills/assemble.py` | **90%** | 拆解+组装+执行+收割完整 |
| 交棒系统 | `skills/succession.py` | **70%** | 提案+执行存在，但**数据驱动（KPI未达标触发）未实现** |
| 传承系统 | `core/skill_graph.py` + `sops/skill_cards/` | **50%** | 数据结构定义 ✅，YAML技能卡 ✅，但**无加载器、无运行时集成** |
| 驾驶舱系统 | `core/workbench.py` | **40%** | 项目工作台+日终回顾+能量感知存在，但**无动态决策面板、无Human Agent交互界面** |
| 军师Agent | ❌ **无此文件** | **0%** | 白皮书核心角色，完全缺失 |
| 数据采集终端 | ❌ **无此文件** | **0%** | 情报系统感知层，完全缺失 |
| 斥候多实例并行 | ❌ **无此文件** | **0%** | 白皮书定义的"一群斥候"并行搜索，完全缺失 |
| 图谱执行引擎 | ❌ **无此文件** | **0%** | 从图谱检索 → 拓扑排序 → 平台路由，完全缺失 |
| Human Agent接口 | ❌ **无此文件** | **0%** | 决策点暂停 + 君主交互，完全缺失 |
| 外联系统 | ❌ **无此文件** | **0%** | 跨家族协作+联邦协议，完全缺失 |

**总体实现度: ~55%**（核心原子+基础治理已验证，高级能力（军师、情报、图谱执行、Human Agent）全部缺失）

---

## 二、逐项差距详解

### 🔴 完全缺失（0%）—— V4.0 优先

#### 1. 军师Agent（Strategist）
**白皮书定位**: 战略资源型府兵。定期审视家族健康，向君主呈报战略建议。军师不是特权Agent，和府兵是同一类实例。

**缺失分析**:
- 无 `agents/strategist.py` 或等效文件
- `evolution.py` 的自进化报告是替代物，但**不是战略审视**
- 军师应有：财务分析Skill、运营分析Skill、治理分析Skill、客户分析Skill、狩猎效果分析Skill、预测分析Skill
- 军师应定期执行 STR-002（战略审视SOP），产出创始人简报

**V4.0 建议**: 创建 `agents/strategist.py`，配置战略审视SOP，从 workbench 读取数据，产出多维度简报。

#### 2. 数据采集终端（情报系统感知层）
**白皮书定位**: 自动运行的数据管道。从任务记录、成本日志、Skill使用频率、合规校验记录、心跳事件中采集原始数据，清洗、标准化、存入Store。**不是独立Agent，是纯函数管道。**

**缺失分析**: 当前各模块自己写数据（cost.py写cost_log，orchestration.py写task_stages），但无统一的采集/清洗/标准化管道。

**V4.0 建议**: 创建 `skills/data_pipeline.py`，定义纯函数：采集原始事件 → 清洗 → 标准化 → 写入 `intelligence_store`。

#### 3. 斥候多实例并行（情报系统输入层）
**白皮书定位**: 祖辈按需创建**一群斥候**，并行搜索不同目标。搜索完成后**并行吸收**。三种模式：持续优化搜索、预测性搜索、机会性搜索。

**缺失分析**:
- `skills/search.py` 只有**单次搜索**
- 无定时触发（cron/schedule）
- 无多实例并行创建
- 无自动比对/校验/试炼闭环
- 无"吸收"机制（搜索到的Skill如何进入基因库？）

**V4.0 建议**: 创建 `skills/scout.py`，实现：
1. 根据军师分析结果生成斥候配置清单
2. 并行创建多个斥候Agent（`spawn`）
3. 每个斥候独立搜索，结果汇总
4. 自动比对 → 自动校验 → 自动试炼 → 择优归档到基因库

#### 4. 图谱执行引擎（GraphExecutor + RoutePlatformSkill）
**白皮书定位**: 图谱**不仅是存储结构，还是执行蓝图**。检索结果不是静态模板列表，而是可被父辈直接加载为执行计划的图谱子图。每个Skill节点携带平台无关的技能卡，每条边定义了Skill之间的时序、并行、条件关系。GraphExecutor读取子图，按拓扑排序调度节点，通过RoutePlatformSkill将技能卡解析为当前平台的工具调用。

**缺失分析**:
- `core/skill_graph.py` 只有数据结构定义（7个dataclass）
- 无 GraphExecutor（读取子图 → 拓扑排序 → 调度）
- 无 RoutePlatformSkill（技能卡 → 平台工具调用）
- 无 YAML → SkillCard 加载器

**V4.0 建议**: 创建 `core/graph_executor.py`，实现：
1. 从图谱检索匹配的子图（按需求语义匹配）
2. 拓扑排序（处理 SEQUENCE/PARALLEL/CONDITIONAL 边）
3. 调度节点执行
4. 平台路由：SkillCard.bindings → 实际工具调用

#### 5. Human Agent接口（君主交互层）
**白皮书定位**: Human Agent是FROST宇宙中与软件Agent完全同构的智能体。当SOP遇到决策点时，Human Agent作为流程中的一个节点被唤醒，通过驾驶舱做出确认/驳回/修改的决策。

**缺失分析**:
- `core/decision_manager.py` 有决策点暂停机制，但**无Human Agent唤醒接口**
- 无 CLI/Streamlit 的"君主决策面板"
- Human Agent的决策不被记录为系统输出的正式组成部分

**V4.0 建议**: 创建 `agents/human_agent.py`，实现：
1. 当SOP遇到决策点时暂停
2. 通知君主（CLI/Streamlit/通知）
3. 接收君主决策（确认/驳回/修改）
4. 将决策记录到族谱（审计可追溯）
5. 继续执行

#### 6. 外联系统
**白皮书定位**: 跨家族协作 + 联邦协议。协作协议管理Skill + 信任评分Skill。

**V5.0+ 建议**: 远期能力，当前不优先。

---

### 🟡 部分实现（40-80%）—— V4.0 补完

#### 7. 质量评分闸门（协议④）
**白皮书规格**: 产出需通过质量评分过滤——客户反馈40%、父辈审核35%、孙辈自评25%。三方评分标准差超过30分时触发长老仲裁。默认不保留。

**当前代码**:
- `merge_from` 存在，但**无质量评分逻辑**
- `evolution.py` 有趋势分析，但**无评分闸门**
- 客户反馈、父辈审核、孙辈自评的评分机制**完全缺失**

**V4.0 建议**: 在 `merge_from` 或 `execute_stage` 后增加 `_quality_gate` 步骤：
1. 收集三方评分（模拟/实际客户反馈接口）
2. 计算加权平均分
3. 标准差>30 → 触发长老仲裁
4. 平均分<阈值 → 丢弃产出，不保留

#### 8. 呼吸监控（免疫系统P1）
**白皮书规格**: 连续两个阶段失败自动熔断，暂停执行并上报祖辈。孙辈每次执行后上报Skill调用次数、LLM调用次数、总耗时、产出文件数量。

**当前代码**:
- `execute_stage` 有单阶段失败检测（`status = "failed"`）
- 但**无"连续两阶段失败熔断"的计数器/状态机**
- 孙辈执行后**无上报机制**

**V4.0 建议**: 在 `orchestration.py` 的 `execute_stage` 中增加 `_stage_failure_count` 跟踪，连续失败>=2时触发熔断事件。

#### 9. 盈利能力完整闭环（协议⑤）
**白皮书规格**: 收入追踪、成本归因、盈利能力评估、三级亏损预警（黄/红/灭门）。军师在战略审视时首先看国库。

**当前代码**:
- `cost.py` 有成本追踪 ✅
- `workbench.py` 有静态 `revenue_monthly`（写死的默认值）
- **无动态收入录入**
- **无成本归因**（哪个项目/哪个Agent消耗了多少成本）
- **无三级亏损预警**（黄灯：月度亏损超预算10%；红灯：连续两月超20%；灭门：连续三月超50%）

**V4.0 建议**: 扩展 `core/cost.py`：
1. 增加收入录入接口（`track_revenue`）
2. 成本归因（按项目/Agent/SOP维度）
3. 三级亏损预警逻辑
4. 盈利能力评估（ROI = 收入 - 成本 / 成本）

#### 10. 交棒系统数据驱动
**白皮书规格**: 军师采纳率连续5次低于30%时触发交棒。祖辈治理KPI未达标时，长老可发起交棒建议。君主批准后执行。

**当前代码**:
- `succession.py` 有提案和执行逻辑，但**基于合规失败率**
- **无军师采纳率追踪**
- **无祖辈治理KPI追踪**
- 交棒触发条件与白皮书不符

**V4.0 建议**: 在 `strategist` 和 `elder` 中增加 KPI 追踪，当触发条件满足时调用 `propose_succession`。

---

### 🟢 已实现或接近完整（80-100%）

#### 11. 四个原子 ✅
- Store: `core/store.py` — 完整
- Skill: `core/skill.py` — 完整
- Agent: `core/agent.py` — 完整（含生命周期、事件驱动、重试）
- SOP: `core/sop.py` — 完整

#### 12. 协议①-③ ✅
- 记忆层级继承: HierarchicalStore 单向读取链
- SOP宪法校验: `validate_sop` + `SOPValidator`
- 代际限制: `Agent.spawn()` + `max_spawn_generation`

#### 13. 免疫系统P0（心跳+Dead Man's Watch+死人开关）✅
- `skills/watchdog.py` — 心跳发送/监控
- `agents/elder.py` check_ancestor_alive — Dead Man's Watch
- `core/dead_mans_switch.py` — 死人开关
- 唯一缺失：孙辈300秒超时监控

#### 14. 府兵系统 ✅
- 拆解: `ancestor.run()`
- 组装: `assemble_agent()`
- 执行: `execute_stage()`
- 收割: `merge_from()` + 资产Store保存

#### 15. 交棒系统（基础）✅
- 提案: `propose_succession()`
- 执行: `execute_succession()`
- 记录: `family:succession_history`

#### 16. 技能图数据结构 ✅
- `core/skill_graph.py` — 7个dataclass + EdgeType枚举
- `sops/skill_cards/` — 5个技能卡YAML

#### 17. 驾驶舱系统（基础）✅
- `core/workbench.py` — 项目工作台、日终回顾、能量感知、业务雷达

---

## 三、V4.0 开发路线图

### V4.0 核心目标
**白皮书原文**: "V4.0: 情报系统工程化 + 技能图执行引擎 + 军师分析SOP + 斥候多实例并行"

**核心问题**: "家族如何从被动执行到主动进化？"

---

### Phase 1: 军师Agent（V4.0 P0 — 战略层）

**目标**: 创建军师Agent，实现战略审视SOP。

**任务**:
1. 创建 `agents/strategist.py`
   - 定义军师Agent（与府兵同构，携带分析Skill）
   - 配置战略审视SOP（STR-002 或类似）
2. 创建 `skills/strategic_analysis.py`
   - 财务分析Skill（读取 cost_log + revenue，产出简报）
   - 运营分析Skill（读取 task_stages + heartbeat，产出简报）
   - 治理分析Skill（读取 audit_log + succession_history，产出简报）
   - 客户分析Skill（读取客户反馈，产出简报）
   - 整合军师Skill（汇总各维度简报，生成创始人简报）
3. 创建 `skills/strategic_brief.py`
   - 将分析结果整合为创始人可读的简报

**验收标准**:
- 军师可定期执行战略审视SOP
- 产出包含财务/运营/治理/客户四维度简报
- 简报可被写入 Store，供君主查阅
- 测试覆盖 > 70%

---

### Phase 2: 数据采集终端（V4.0 P1 — 感知层）

**目标**: 创建情报系统的数据采集管道。

**任务**:
1. 创建 `skills/data_pipeline.py`
   - `collect_events()` — 从各模块收集原始事件
   - `clean_events()` — 清洗异常数据
   - `normalize_events()` — 标准化为统一格式
   - `store_intelligence()` — 写入 `intelligence_store`
2. 定义标准化数据格式（JSON Schema）
   - 事件类型、时间戳、Agent ID、任务ID、结果状态
3. 将 data_pipeline 接入现有模块
   - cost.py 写入成本事件
   - orchestration.py 写入阶段事件
   - watchdog.py 写入心跳事件

**验收标准**:
- 数据采集管道可自动运行
- 所有关键事件被标准化存储
- 数据可被军师分析Skill读取

---

### Phase 3: 斥候系统（V4.0 P2 — 输入层）

**目标**: 实现多斥候并行搜索 + 自动吸收闭环。

**任务**:
1. 创建 `skills/scout.py`
   - `create_scout_batch()` — 根据军师分析结果生成斥候配置
   - `parallel_search()` — 并行创建多个斥候Agent，各自搜索
   - `collect_results()` — 汇总各斥候搜索结果
2. 实现自动比对/校验/试炼
   - `compare_skill()` — 比对搜索到的Skill与现有基因库
   - `validate_skill()` — 校验Skill格式和合规性
   - `trial_skill()` — 试炼（小规模运行验证）
   - `absorb_skill()` — 择优归档到基因库
3. 创建定时触发机制（cron/schedule）
   - 持续优化搜索：每日定时
   - 预测性搜索：军师分析后触发
   - 机会性搜索：搜索过程中主动推送

**验收标准**:
- 可并行创建多个斥候
- 搜索结果自动比对、校验、试炼、吸收
- 定时任务可稳定运行

---

### Phase 4: 技能图执行引擎（V4.0 P3 — 执行层）

**目标**: 将技能图从数据结构转化为执行蓝图。

**任务**:
1. 创建 `core/graph_executor.py`
   - `GraphExecutor` 类
   - `load_subgraph()` — 从图谱检索匹配子图
   - `topological_sort()` — 按边类型排序（SEQUENCE/PARALLEL/CONDITIONAL）
   - `execute_subgraph()` — 调度节点执行
2. 创建 `core/platform_router.py`
   - `RoutePlatformSkill` — 将 SkillCard.bindings 解析为平台工具调用
   - 支持 deepseek / openai / local_gguf / web_search 等平台
3. 创建 `core/skill_card_loader.py`
   - 加载 YAML 技能卡 → 实例化 `SkillCard` dataclass
   - 验证字段完整性
4. 更新 `skills/assemble.py`
   - 当基因库命中时，优先使用技能图检索（而非关键词匹配）

**验收标准**:
- 可从YAML加载SkillCard并实例化
- GraphExecutor可按拓扑排序执行子图
- RoutePlatformSkill可正确路由到平台工具
- 测试覆盖 > 70%

---

### Phase 5: Human Agent接口（V4.0 P4 — 交互层）

**目标**: 实现君主（Human Agent）与家族的交互接口。

**任务**:
1. 创建 `agents/human_agent.py`
   - Human Agent类（与软件Agent同构，Skills内置）
   - 决策点暂停/唤醒机制
2. 创建 `skills/human_decision.py`
   - 当SOP遇到决策点时，暂停并通知君主
   - 接收君主决策（确认/驳回/修改）
   - 记录决策到族谱（审计可追溯）
3. 扩展驾驶舱（`core/workbench.py`）
   - 增加"君主决策面板"（待决策事项列表）
   - 增加"家族状态概览"（军师简报、长老审计、健康度）

**验收标准**:
- 当SOP遇到决策点时，流程可暂停
- 君主可通过CLI/Streamlit做出决策
- 决策被记录并可追溯
- 测试覆盖 > 70%

---

### Phase 6: 补完（V4.0 P5 — 协议补全）

**目标**: 补全协议④、⑤、⑥的缺失部分。

**任务**:
1. 质量评分闸门（`skills/quality_gate.py`）
   - 三方评分：客户反馈40% + 父辈审核35% + 孙辈自评25%
   - 标准差>30 → 触发长老仲裁
   - 平均分<阈值 → 丢弃产出
2. 呼吸监控（`skills/circuit_breaker.py`）
   - 连续两阶段失败 → 自动熔断
   - 暂停执行并上报祖辈
3. 盈利能力完整闭环（扩展 `core/cost.py`）
   - 收入录入接口
   - 成本归因（按项目/Agent/SOP）
   - 三级亏损预警（黄/红/灭门）
   - 盈利能力评估（ROI）

**验收标准**:
- 质量评分闸门可正确拦截低质量产出
- 呼吸监控可自动熔断连续失败
- 盈利能力管理可触发预警

---

## 四、V4.0 测试策略

每个Phase完成后，需补充对应测试：

| Phase | 测试文件 | 目标覆盖 |
|-------|---------|---------|
| P0 军师 | `tests/test_strategist.py` | 战略审视SOP、分析Skill、简报生成 |
| P1 数据管道 | `tests/test_data_pipeline.py` | 采集、清洗、标准化、存储 |
| P2 斥候 | `tests/test_scout.py` | 并行搜索、比对、校验、试炼、吸收 |
| P3 图谱执行 | `tests/test_graph_executor.py` | 子图加载、拓扑排序、平台路由 |
| P4 Human Agent | `tests/test_human_agent.py` | 决策点暂停、君主交互、决策记录 |
| P5 补完 | `tests/test_quality_gate.py` | 评分、熔断、预警 |

---

## 五、V4.0 → V5.0 演进方向

V4.0 完成后，家族将具备：
- ✅ 被动执行（府兵系统）
- ✅ 主动进化（军师 + 斥候 + 狩猎）
- ✅ 免疫监控（心跳 + 呼吸 + 体检）
- ✅ 人即系统（Human Agent接口）
- ✅ 图谱执行（从数据结构到执行蓝图）

V5.0 方向：
- 驾驶舱完整版（动态决策面板）
- 外联系统（跨家族协作 + 联邦协议）
- 撒豆成兵完整版（从图谱自动生成完整应用）
- 元认知与自优化（军师分析自己的分析方法论）

---

*映射完成。V4.0 的核心命题是：从被动执行到主动进化。军师是发动机，斥候是燃料，图谱是地图，Human Agent是舵手。*
