# FROST-SOP V7.4 — 武器狩猎设计文档

> **哲学**: 狩猎是去外部寻找，不是在系统内部扫描。外部发现 → 内部评估 → 决定是否入库。

---

## 1. 为什么需要武器狩猎

当前武器库的武器是人工预置的（`is_preset=True`）。当府兵遇到以下情况时，需要外部狩猎：

- 任务场景没有匹配的武器（`recommend_for_task` 返回空）
- 现有武器连续失败，进化后仍无法解决问题
- 用户提出全新需求类型，武器库无覆盖

---

## 2. 触发条件

```
触发器 1: 府兵空手而归
  条件: dispatch_for_task() 返回 0 个 SKILL + 0 个 TACTIC
  动作: 发布 WEAPON_HUNT_REQUESTED 事件

触发器 2: 武器进化失败
  条件: 武器进化 3 次后仍无法通过试炼（health_score < 30）
  动作: 发布 WEAPON_HUNT_REQUESTED 事件

触发器 3: 用户主动请求
  条件: 用户说"我需要 XXX 能力"
  动作: 直接启动狩猎流程
```

---

## 3. 狩猎目标（外部来源）

| 来源类型 | 示例 | 狩猎方式 |
|---------|------|---------|
| **开源代码库** | GitHub, PyPI, npm | 搜索相关项目，分析 README + API 文档 |
| **API 服务** | 第三方 SaaS API | 检索 API 文档，验证可用性 |
| **知识库** | Wikipedia, 技术博客 | 提取方法论/流程，转化为 TACTIC |
| **竞品分析** | 同类产品功能清单 | 逆向工程，提炼能力单元 |
| **社区资源** | Reddit, V2EX, 知乎 | 收集最佳实践，验证可行性 |

---

## 4. 狩猎 Agent 架构

```
HunterAgent（狩猎者）
  ├── Scout（侦察兵）: 去外部搜索候选武器
  ├── Appraiser（评估师）: 评估候选武器的质量和适用性
  └── Curator（策展人）: 决定是否入库，如何入库
```

### 4.1 Scout（侦察兵）

职责：根据任务描述，去外部搜索可能的解决方案。

输入：`task_description`（如"我需要自动化的社交媒体内容发布"）
输出：候选列表 `[{name, source_url, description, type}, ...]`

工具：
- `kimi_search_v2`: 搜索相关开源项目/工具
- `kimi_fetch_v2`: 抓取项目 README 和文档
- `mcp__github`: 搜索 GitHub 仓库（如果有此工具）

### 4.2 Appraiser（评估师）

职责：评估候选武器是否值得入库。

评估维度：
1. **功能匹配度**: 是否能解决触发狩猎的问题？
2. **质量指标**: 仓库 star 数、最近更新时间、issue 响应速度
3. **依赖复杂度**: 引入该武器需要多少额外依赖？
4. **许可兼容性**: 许可证是否允许商业使用？
5. **维护状态**: 是否仍在活跃维护？

输出：评估报告 `{candidate_id, score, verdict, concerns}`

### 4.3 Curator（策展人）

职责：决定是否将候选武器正式入库。

决策流程：
```
if score >= 80 and concerns == 0:
    直接入库（ACTIVE）
elif score >= 60 and len(concerns) <= 2:
    入库为 TRIALED（需要试炼）
else:
    拒绝入库，记录原因到狩猎日志
```

---

## 5. 武器狩猎 SOP

```yaml
sop_id: SOP-HUNT-001
name: 武器狩猎流程

phases:
  - id: trigger
    name: 触发确认
    description: 确认确实需要外部狩猎（内部武器库已穷尽）
    checks:
      - 武器库推荐是否为空？
      - 现有武器是否已尝试进化？
      - 用户是否确认需要新能力？

  - id: scout
    name: 外部侦察
    description: 搜索外部候选武器
    tools: [kimi_search_v2, kimi_fetch_v2]
    outputs: 候选列表（最多10个）

  - id: appraise
    name: 质量评估
    description: 对每个候选进行多维度评估
    criteria:
      - 功能匹配度: 0-100
      - 质量指标: 0-100
      - 依赖复杂度: 越低越好
      - 许可兼容性: 必须兼容
      - 维护状态: 活跃/停滞/废弃
    outputs: 评估报告

  - id: curate
    name: 入库决策
    description: 决定是否入库
    rules:
      - score >= 80 → ACTIVE
      - score >= 60 → TRIALED
      - score < 60 → REJECTED
    outputs: 入库结果

  - id: integrate
    name: 集成试炼
    description: 将新武器集成到武器库，开始试炼
    duration: 7天 / 10次使用
    success_criteria:
      - 成功率 >= 70%
      - 无严重副作用
    outputs: 试炼报告
```

---

## 6. 狩猎产物格式

狩猎发现的武器需要转换为标准 WeaponMetadata：

```python
WeaponMetadata(
    id="hunt:github_repo_name",  # 前缀标识来源
    name="人类可读名称",
    type=WeaponType.SKILL,  # 或 TACTIC
    category=WeaponCategory.EXECUTION,  # 根据功能推断
    description="从外部来源提取的描述",
    applicable_scenarios=["场景1", "场景2"],
    source_url="https://github.com/...",  # 原始来源
    created_from="hunted",  # 标识为狩猎产物
    confidence=0.85,  # 评估师给出的置信度
    state=WeaponState.TRIALED,  # 新狩猎产物默认需要试炼
)
```

---
## 7. 与其他组件的关系

```
府兵执行失败 / 推荐为空
    ↓
发布 WEAPON_HUNT_REQUESTED 事件
    ↓
HunterAgent.Scout 去外部搜索
    ↓
HunterAgent.Appraiser 评估候选
    ↓
HunterAgent.Curator 决策入库
    ↓
新武器注册到武器库（状态: TRIALED）
    ↓
WeaponLifecycle 管理试炼 → ACTIVE / REJECTED
    ↓
府兵下次执行时可从武器库获取
```

---

## 8. 待实现清单

- [ ] `agents/hunter.py` — HunterAgent 实现
- [ ] `skills/strategy/scout.py` — Scout Skill（搜索外部资源）
- [ ] `skills/strategy/appraiser.py` — Appraiser Skill（质量评估）
- [ ] `sops/SOP-HUNT-001.yaml` — 武器狩猎 SOP
- [ ] `core/event_bus.py` — 新增 WEAPON_HUNT_REQUESTED / WEAPON_HUNT_COMPLETED 事件
- [ ] 集成 `kimi_search_v2` / `kimi_fetch_v2` 进行外部搜索

---

## 9. 关键设计决策

**Q: 为什么不自动扫描内部代码文件？**  
A: 狩猎的本质是去外部世界寻找系统未知的解决方案。内部扫描只是整理已有资产，那是 WeaponLoader 的职责，不是 Hunter。

**Q: 狩猎产物如何保持更新？**  
A: 狩猎产物标记 `created_from="hunted"`，系统定期检查其 `source_url` 是否有更新（新版本发布），触发重新评估。

**Q: 如何防止狩猎滥用（每次失败都去外部找）？**  
A: 狩猎触发有冷却期：同一任务描述 7 天内只触发一次狩猎。同时优先尝试武器进化，进化无效才触发狩猎。
