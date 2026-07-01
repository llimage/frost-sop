# FROST V4.0 统一武器库（Armory）架构设计

**版本**: V4.0-设计稿
**状态**: 定稿
**日期**: 2026-06-28

---

## 一、设计目标

FROST 家族目前的核心资产散落在三个地方：
1. `skills/*.py` — 独立的 Python 模块，各 Skill 之间无结构化关系
2. `sops/templates/*.yaml` — 独立的 SOP YAML，与 Skill 之间无显式依赖声明
3. `asset_store["skill_gene:*"]` — 能力基因条目，格式不统一，检索靠关键词匹配

**本次优化的目标：**

| # | 问题 | 优化方向 |
|---|------|---------|
| 1 | 资产无统一身份 | 所有资产（Skill/SOP/情报/免疫规则/平台绑定）统一为 **Weapon**，拥有唯一ID和完整元数据 |
| 2 | 检索靠关键词 | 建立 **多维索引**（类型×功能域×场景×评分×状态），军师可按需求语义检索 |
| 3 | 依赖关系隐含 | 显式声明 **武器依赖关系**（一个SOP需要哪些Skill，一个Skill需要哪些前置条件） |
| 4 | 进化无数据驱动 | 引入 **健康评分**（使用频率+成功率+时效性），自然选择淘汰低分武器 |
| 5 | 配发靠硬编码 | 建立 **武器配发器**（ArmoryDispatcher），府兵不自备武器，出征时从兵器库配发 |
| 6 | 生命周期无管理 | 建立 **七态生命周期**（DISCOVERED → VALIDATED → TRIALED → ARCHIVED → ACTIVE → DEPRECATED → RETIRED） |

---

## 二、核心概念：武器（Weapon）

### 2.1 武器的重新定义

> **武器 = 元数据驱动的能力单元**

武器不是代码文件，而是一个**完整的元数据包**，携带以下信息：

- **身份**：唯一ID、名称、类型、版本
- **能力**：功能域（分类）、适用场景、不适用场景
- **关系**：依赖哪些武器、被哪些武器依赖、需要哪些平台
- **健康**：使用次数、成功率、平均执行时间、健康评分
- **来源**：手工创建/提取/合成/狩猎
- **生命周期**：当前状态（发现→验证→试炼→归档→活跃→废弃→退役）
- **扩展**：技能卡（SkillCard）、技能图节点ID

**代码和 YAML 文件只是武器的载体，武器本身是元数据。**

### 2.2 武器类型（WeaponType）

| 类型 | 标识 | 定义 | 示例 |
|------|------|------|------|
| **SKILL** | `skill:` | 纯函数能力单元 | `skill:call_llm`、`skill:assemble_agent` |
| **SOP** | `sop:` | 标准操作程序 | `sop:DEV-001`、`sop:STR-002` |
| **INTEL** | `intel:` | 情报产物（简报、报告） | `intel:financial_brief_20260628` |
| **IMMUN** | `immun:` | 免疫规则（阈值、策略） | `immun:heartbeat_120s`、`immun:circuit_breaker_2` |
| **BIND** | `bind:` | 平台绑定（配置） | `bind:deepseek_v3`、`bind:openai_gpt4` |
| **GENE** | `gene:` | 能力基因（未归档的Skill模板） | `gene:call_llm`、`gene:spawn` |

### 2.3 武器功能域（WeaponCategory）

| 功能域 | 定义 | 包含的典型武器 |
|--------|------|---------------|
| **COGNITIVE** | 认知能力 | call_llm、analyze_trends、generate_suggestions |
| **EXECUTION** | 执行能力 | write_code、deploy、file_operation |
| **GOVERNANCE** | 治理能力 | validate_sop、audit_family、compliance_check |
| **STRATEGY** | 战略能力 | analyze_financial、analyze_operational、integrate_brief |
| **IMMUNE** | 免疫能力 | send_heartbeat、monitor_heartbeat、circuit_breaker |
| **ORCHESTRATE** | 编排能力 | spawn、merge_from、emit、execute_stage |
| **SEARCH** | 搜索能力 | search_web、search_gitee、compare_skill |
| **COMM** | 通信能力 | present_for_approval、notify_founder、generate_brief |

**军师检索武器时，按功能域+场景双维度匹配。**

---

## 三、武器生命周期（七态流转）

```
DISCOVERED ──→ VALIDATED ──→ TRIALED ──→ ARCHIVED ──→ ACTIVE ──→ DEPRECATED ──→ RETIRED
     ↑                                                              │
     └──────────────────────────── 复活/降级 ───────────────────────┘
```

| 状态 | 含义 | 转换条件 |
|------|------|---------|
| **DISCOVERED** | 狩猎发现，尚未验证 | 自动：斥候带回外部Skill时初始状态 |
| **VALIDATED** | 格式/结构校验通过 | 手动：武器库管理员校验通过 |
| **TRIALED** | 小规模试炼通过 | 手动：至少运行1次，成功率≥70% |
| **ARCHIVED** | 已归档入库，可供配发 | 手动：试炼通过，正式入库 |
| **ACTIVE** | 当前活跃使用 | 自动：首次被府兵配发使用；或从ARCHIVED升级（成功率>80%+使用>10次） |
| **DEPRECATED** | 标记废弃，不再推荐 | 自动：连续30天未使用且非预置；手动：有更好替代品 |
| **RETIRED** | 已退役，不可使用 | 自动：健康评分<20；手动：发现严重安全/合规问题 |

**关键规则**：
- 只有 **ACTIVE** 状态的武器才能被配发给府兵
- 预置武器（`is_preset=True`）不自动废弃/退役，但参与评分排序
- 废弃武器可降级为退役，也可复活为活跃（如果重新被使用）

---

## 四、武器注册表（ArmoryRegistry）

### 4.1 核心职责

武器注册表是家族兵器的**唯一索引中心**，替代当前散落在 `skills/`、`sops/`、`asset_store` 中的松散结构。

### 4.2 多维索引体系

```
ArmoryRegistry
├── _weapons: Dict[str, WeaponMetadata]          # 主索引：ID → 武器
├── _by_type: Dict[WeaponType, Set[str]]         # 类型索引
├── _by_category: Dict[WeaponCategory, Set[str]] # 功能域索引
├── _by_scenario: Dict[str, Set[str]]            # 场景索引
├── _by_state: Dict[WeaponState, Set[str]]         # 生命周期状态索引
└── _dependents: Dict[str, Set[str]]             # 被依赖关系索引
```

### 4.3 检索能力

| 检索方式 | 输入 | 输出 | 使用场景 |
|---------|------|------|---------|
| `get(id)` | 武器ID | 单个武器 | 精确配发 |
| `find_by_type(type)` | 类型 | 武器列表 | 浏览所有SOP |
| `find_by_category(cat)` | 功能域 | 武器列表 | 军师浏览所有战略能力 |
| `find_by_scenario(scenario)` | 场景 | 武器列表 | 按任务场景匹配 |
| `find_by_scenarios([scenarios], match_all)` | 多个场景 | 武器列表 | 多场景交集/并集匹配 |
| `find_by_keyword(keyword)` | 关键词 | 武器列表 | 模糊搜索 |
| `find_dependents(id)` | 武器ID | 依赖它的武器列表 | 删除前检查影响 |
| `find_by_health_score(min, max)` | 评分范围 | 武器列表 | 自然选择淘汰 |
| `recommend(requirement, type, top_k)` | 需求描述 | 按评分排序的武器列表 | 军师自动推荐 |
| `recommend_bundle(task, categories)` | 任务描述 | 按功能域分组的武器套装 | 动态配发 |

### 4.4 推荐算法

军师推荐武器的逻辑：

1. **关键词匹配**：在武器名称、适用场景、ID中匹配需求描述关键词
2. **状态过滤**：只推荐 ACTIVE 状态
3. **评分过滤**：过滤掉健康评分<30的武器
4. **排序**：按 `health_score` 降序 → `usage_count` 降序 → `success_rate` 降序

**推荐结果不是静态列表，而是动态计算的——每次推荐都反映当前武器库的真实状态。**

---

## 五、武器配发器（ArmoryDispatcher）

### 5.1 核心职责

> **府兵不自备武器，武器由朝廷兵器库统一配发。出征时领取，战后归还。**

武器配发器负责：
1. 根据任务描述，从武器库检索最佳武器组合
2. 将武器实例（Skill/SOP）交付给府兵
3. 记录配发日志（使用次数+1）

### 5.2 配发流程

```
任务描述 → 军师推荐(recommend_bundle) → 武器检索 → 实例化 → 交付府兵
                              │
                              ▼
                    [按功能域分组推荐]
                    COGNITIVE: [skill:call_llm, skill:analyze_xxx]
                    EXECUTION: [sop:DEV-001]
                    GOVERNANCE: [skill:validate_sop]
```

### 5.3 配发记录

每次配发后，武器元数据更新：
- `usage_count += 1`
- `last_used = 当前时间`
- 任务完成后记录成功/失败，更新 `health_score`

---

## 六、武器健康评分（自然选择引擎）

### 6.1 评分公式

```
health_score = 0.4 × success_rate × 100
             + 0.3 × log(usage_count + 1) / log(101) × 100
             + 0.3 × recency_factor × 100
```

| 维度 | 权重 | 说明 |
|------|------|------|
| **成功率** | 40% | 成功次数 / 总使用次数。武器是否可靠 |
| **使用频率** | 30% | 使用次数的对数衰减。使用100次达到满分 |
| **时效性** | 30% | 最近使用时间的衰减。当前简化=1.0（未衰减） |

### 6.2 自然选择规则

| 条件 | 结果 |
|------|------|
| health_score ≥ 80 | 优先推荐，军师简报中标记"精良" |
| 50 ≤ health_score < 80 | 正常推荐 |
| 30 ≤ health_score < 50 | 谨慎推荐，标注"使用频率低" |
| health_score < 30 | 不推荐，触发狩猎搜索替代品 |
| health_score < 20 | 自动退役（非预置武器） |
| 连续30天未使用 | 自动标记废弃（非预置武器） |

---

## 七、统一武器加载器（WeaponLoader）

### 7.1 三种来源的统一加载

| 来源 | 当前格式 | 加载后类型 | 加载方式 |
|------|---------|-----------|---------|
| **Python 模块** | `skills/llm.py` 等 | SKILL | 模块导入，提取 `Skill` 实例 |
| **SOP YAML** | `sops/templates/DEV-001.yaml` | SOP | 解析 YAML，提取 stages + 依赖 |
| **技能卡 YAML** | `sops/skill_cards/call_llm.yaml` | GENE | 解析 YAML，提取 intent + 场景 |
| **Store 基因** | `skill_gene:xxx` | GENE | 从 Store 读取 dict，提取 name + 场景 |

### 7.2 加载规则

- 模块加载的 Skill 视为 **预置武器**（`is_preset=True`），不可自动退役
- YAML 加载的 SOP/技能卡 视为 **预置武器**
- Store 基因 视为 **非预置**（可进化、可淘汰）
- 同ID武器版本冲突时，**高版本覆盖低版本**

### 7.3 发现与扫描

`discover_all()` 一键扫描项目目录：
1. 扫描指定 Skill 模块列表
2. 扫描指定 SOP YAML 目录
3. 扫描指定技能卡 YAML 目录
4. 扫描 Store 中的基因条目

**扫描结果自动注册到武器库。**

---

## 八、现有资产迁移方案

### 8.1 当前资产清单

| 资产类型 | 数量 | 当前位置 | 迁移后ID示例 |
|---------|------|---------|------------|
| Skill | 5+ | `skills/*.py` | `skill:call_llm`, `skill:assemble_agent` |
| SOP | 7 | `sops/templates/*.yaml` | `sop:DEV-001`, `sop:STR-002` |
| 技能卡 | 5 | `sops/skill_cards/*.yaml` | `gene:call_llm`, `gene:spawn` |
| 能力基因 | 9 | `asset_store["skill_gene:*"]` | `gene:需求分析`, `gene:代码生成` |
| 免疫规则 | 2 | `skills/watchdog.py` | `immun:heartbeat_120s` |

### 8.2 迁移步骤

**Step 1**: 运行 `discover_all()` 扫描所有现有资产，自动注册到武器库
**Step 2**: 为每个 Skill 模块补充功能域和场景元数据（在 `WeaponLoader.load_from_module` 中维护映射表）
**Step 3**: SOP YAML 自动解析依赖关系（从 stages 中引用的 skills 提取）
**Step 4**: 技能卡 YAML 自动解析适用场景（从 `applicable_when` 字段提取）
**Step 5**: 武器库持久化到 `armory:registry` Store 条目

### 8.3 代码层面调整

| 当前代码 | 调整后 |
|---------|--------|
| `from skills.llm import call_llm_skill` | `dispatcher = get_armory_dispatcher(); skill = dispatcher.dispatch("skill:call_llm")` |
| `SOP.load_from_yaml("sops/templates/DEV-001.yaml")` | `dispatcher = get_armory_dispatcher(); sop = dispatcher.dispatch_sop("DEV-001")` |
| `asset_store.load("skill_gene:需求分析")` | `registry = get_armory_registry(); weapon = registry.get("gene:需求分析")` |
| `assemble_agent` 中硬编码技能列表 | `registry.recommend_bundle(requirement, [COGNITIVE, EXECUTION])` |

---

## 九、V4.0 武器库演进路线图

### Phase 1: 武器库核心（已完成）
- ✅ `core/armory.py` — 统一武器库架构
- ✅ 武器元数据模型（WeaponMetadata）
- ✅ 多维注册表（ArmoryRegistry）
- ✅ 生命周期管理（WeaponLifecycle）
- ✅ 统一加载器（WeaponLoader）
- ✅ 武器配发器（ArmoryDispatcher）

### Phase 2: 现有资产迁移（V4.0 P0）
- 运行 `discover_all()` 扫描所有现有资产
- 为每个 Skill 补充功能域映射
- 持久化武器库到 Store
- 验证迁移后武器库完整度

### Phase 3: 军师武器锻造（V4.0 P1）
- 创建军师分析 Skills（`analyze_financial`, `analyze_operational`, `analyze_governance`, `analyze_customer`）
- 每个新 Skill 作为 Weapon 注册到武器库
- 定义 `sop:STR-002`（战略审视SOP）
- 军师执行 STR-002 时，从武器库自动配发分析 Skills

### Phase 4: 斥候武器锻造（V4.0 P2）
- 创建斥候搜索 Skills（`search_external`, `compare_skill`, `validate_skill`, `trial_skill`, `absorb_skill`）
- 定义 `sop:HUNT-001`（狩猎SOP）
- 斥候执行 HUNT-001 时，从武器库自动配发搜索 Skills

### Phase 5: 免疫武器锻造（V4.0 P3）
- 将现有 watchdog Skills 注册为 IMMUN 类型武器
- 创建 `immun:heartbeat_30s`、`immun:circuit_breaker_2` 等规则武器
- 定义 `sop:IMMUN-001`（免疫监控SOP）

### Phase 6: 武器图执行引擎（V4.0 P4）
- 将 `core/skill_graph.py` 的数据结构与武器库打通
- 武器注册时自动创建/关联 SkillNode
- GraphExecutor 从武器库检索武器，按拓扑排序执行

---

## 十、关键设计决策记录

| 决策 | 理由 |
|------|------|
| 所有资产统一为 Weapon | 消除 Skill/SOP/情报/免疫的边界模糊，统一检索和进化 |
| 武器元数据驱动 | 代码是载体，元数据是本质。元数据驱动检索、推荐、进化 |
| 七态生命周期 | 完整覆盖从狩猎发现到退役淘汰的完整闭环 |
| 健康评分 = 成功率×频率×时效 | 三维评分防止单一维度被游戏（如刷使用次数） |
| 预置武器不可自动淘汰 | 核心能力（call_llm、validate_sop）不能被自然选择淘汰 |
| 武器配发器统一入口 | 府兵不自备武器，所有武器从兵器库配发，配发记录驱动进化 |
| 三种来源统一加载 | 现有代码不动，通过加载器统一纳入武器库框架 |
| 功能域×场景双维度检索 | 军师需要按"能力类型"和"任务场景"两个维度匹配武器 |
| 武器依赖显式声明 | SOP 自动解析依赖，Skill 手动声明依赖，防止运行时缺失 |
| 武器图与武器库打通 | 技能图是空间维度，武器库是时间维度（健康评分），两者互补 |

---

## 附录：武器ID命名规范

| 类型 | ID格式 | 示例 |
|------|--------|------|
| SKILL | `skill:{skill_name}` | `skill:call_llm` |
| SOP | `sop:{sop_id}` | `sop:DEV-001` |
| INTEL | `intel:{brief_type}_{date}` | `intel:financial_brief_20260628` |
| IMMUN | `immun:{rule_name}` | `immun:heartbeat_120s` |
| BIND | `bind:{platform_name}` | `bind:deepseek_v3` |
| GENE | `gene:{gene_name}` | `gene:需求分析` |

---

*文档结束。武器库是家族资产的统一注册表、检索器和生命周期管理者。军师、斥候、府兵的所有武器都从这里配发、进化、退役。*
