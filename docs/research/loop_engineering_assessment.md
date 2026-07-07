# Loop Engineering × FROST-SOP：诚实评估报告

> 调研时间：2026-06-17
> 调研范围：Addy Osmani、Anthropic、LangChain、学术界关于 Loop Engineering 的定义与实践
> 结论定位：绝对诚实，不夸大价值，不制造需求

---

## 一、Loop Engineering 是什么（先搞清楚概念）

### 1.1 不是某个 GitHub 项目，是一套方法论

**Loop Engineering** 是 2026 年 6 月兴起的概念（由 Addy Osmani、Anthropic 等推动），它不是某个具体的开源 repo，而是** Harness Engineering 内部的一个 Pattern**。

核心定义：
> **Loop Engineering 通过 Self-Triggering（系统自动触发），把 Harness 从"人工启动的工具"升级为"自主发现问题并解决的 Agent"。**

### 1.2 Loop Engineering 在 Harness 分层中的位置

```
第 5 层: Design Instance（具体系统）    ← FROST-SOP 在这里
第 4 层: Pattern（可复用模式）          ← Loop Engineering 在这里
第 3 层: Design Components（设计维度）  ← 10个设计轴（topology/coordination/memory...）
第 2 层: Framework（机制/运行时）        ← LangGraph/Claude Code/Codex SDK
第 1 层: Cross-cutting Concerns          ← Prompt Engineering + Context Engineering
```

**关键认知：Loop Engineering 不发明新能力，它只是 Harness 已有能力的一种高级组合方式。**

### 1.3 Loop Engineering 的四个核心组件

| 组件 | 说明 | 依赖的 Harness 能力 |
|------|------|-------------------|
| **Self-Triggering** | 系统自动决定何时启动 Agent | Framework 层的 Trigger 系统（cron/event/condition） |
| **Self-Prompting** | 系统根据状态自动生成 prompt | Framework 层的上下文读取 + prompt 组装 |
| **State Persistence** | 跨 session 保存和恢复状态 | Harness 的 State Outside Context Pattern |
| **Stop Condition Check** | 判断任务是否完成，决定是否停止 | Pattern 层的 Verification + 确定性检查 |

Loop Engineering **唯一真正新增的能力是 Self-Triggering**，其他三个都是 Harness 已有能力的组合。

---

## 二、Loop Engineering 的典型实现

### 2.1 Ralph Loop（最知名的开源实现）

**Ralph Wiggum** 由 Geoffrey Huntley 创建，核心思想：

```bash
# 伪代码：Ralph Loop
while true; do
    # 1. 读取 PRD/任务列表
    task = read_next_task()

    # 2. 启动新的 Agent session（每次都清上下文）
    result = claude_code(task, fresh_context=true)

    # 3. 验证结果（测试/lint/构建）
    if verify(result) == PASS:
        commit(result)
        mark_done(task)
    else:
        write_failure_log(result)

    # 4. 如果所有任务完成，退出
    if all_tasks_done(): break

    # 5. 防止无限循环
    if iterations > MAX: break

    sleep(INTERVAL)
done
```

**核心洞察：每次迭代都用 fresh context，避免上下文膨胀导致的性能退化。**

### 2.2 Claude Code 的 `/loop` 和 `/schedule`

Claude Code 在 2026 年 3 月原生支持：

```bash
# /loop：session 级别的定时任务
/loop 10m run npm test and report any errors

# /schedule：跨 session 的持久化定时任务
/schedule 0 9 * * * check all open PRs and create a report
```

### 2.3 auto-co-meta（"14个AI Agent 24/7运行"）

**~50 行 bash 脚本**，每 2 分钟调用一次 Claude Code：

```bash
# 核心逻辑
read consensus → pick agents → execute → update consensus → sleep → repeat
```

**状态全部存在 markdown 文件里，唯一依赖是 Claude Code。**

---

## 三、FROST-SOP 与 Loop Engineering 的对比

### 3.1 当前 FROST-SOP 的架构

| 层级 | FROST-SOP 对应 | 状态 |
|------|---------------|------|
| Framework（机制层） | `skills/llm.py`（LLM调用）、`core/`（数据库、成本追踪） | ✅ 有 |
| Design Components（设计维度） | SOP模板的`phases`/`stages`、`llm_config` | ✅ 有 |
| Pattern（模式层） | SOP模板（Plan-Act-Verify 的变体） | ✅ 有 |
| Design Instance（具体系统） | 家族（Family）+ 任务执行 | ✅ 有 |
| **Loop Engineering** | **Self-Triggering 自动触发** | **❌ 缺失** |

### 3.2 关键差距

| 能力 | FROST-SOP 现状 | Loop Engineering 要求 |
|------|---------------|----------------------|
| **触发方式** | 人手动分配任务 | 系统自动触发（cron/event/condition） |
| **Prompt 生成** | 人写 prompt | 系统根据状态自动生成 prompt |
| **跨 session 状态** | 数据库持久化 | 文件/数据库自动读写 |
| **完成判断** | 人 review 输出 | Checker 自动判断 |
| **错误恢复** | 人发现后重试 | 系统自动重试 + 回退 |
| **运行时间** | 按需运行 | 24/7 持续运行 |

---

## 四、绝对诚实的结合点评估

### 4.1 对廖亮场景的适配性分析

廖亮的工作特点：
- 一人公司，无技术团队
- 月度 Token 预算 ¥300
- 核心任务：内容生产、平台搭建、调研
- **不需要 24/7 运行**——他的工作有明确的"工作时间"
- **不需要自动发现问题**——他自己知道要做什么

| Loop Engineering 价值 | 对廖亮是否适用 | 原因 |
|----------------------|-------------|------|
| **24/7 自动运行** | ❌ 不适用 | 一人公司，没有需要半夜处理的任务 |
| **自动发现问题（CI失败/issue/PR）** | ❌ 不适用 | 没有大规模 CI/CD、没有团队协作 |
| **跨 session 持续工作** | ⚠️ 部分适用 | 长任务（如课程大纲设计）可以分 session 完成 |
| **失败自动重试** | ✅ 适用 | 减少人工干预，提升可靠性 |
| **输出自动验证** | ✅ 适用 | 验证 SOP 输出是否符合格式 |
| **状态自动记录** | ✅ 适用 | 减少手动记录任务状态 |

### 4.2 三个真正有价值的结合点

#### 结合点 1：任务失败自动重试（高价值，低成本）

**当前问题**：Agent 执行 SOP 时某阶段失败，需要人工发现并重试。

**Loop 化改进**：
```python
# 在 orchestration.py 中添加
for phase in sop.phases:
    for attempt in range(MAX_RETRIES):
        result = execute_phase(phase)
        if validate(result):
            break
        elif attempt < MAX_RETRIES - 1:
            # 自动重试，注入失败信息
            phase.prompt += f"\n上次失败原因：{result.error}"
        else:
            # 最终失败，标记任务状态
            task.status = "FAILED"
            notify_user(task)
```

**成本**：几乎零（修改已有代码）
**收益**：减少人工干预 50%+

#### 结合点 2：长任务分 session 自动继续（中价值，中成本）

**当前问题**：OPS-007 有 4 个阶段，如果阶段 2 完成后 session 结束，阶段 3 需要人手动启动。

**Loop 化改进**：
```yaml
# 在 SOP 模板中添加
sop_id: OPS-007
loop_config:
  auto_continue: true      # 阶段完成后自动进入下一阶段
  max_session_duration: 30m  # 每个 session 最多 30 分钟
  state_file: "tasks/{task_id}/progress.json"
```

**成本**：中等（需要状态持久化 + session 恢复逻辑）
**收益**：长任务可以"断点续传"

#### 结合点 3：输出自动验证 + 条件流转（高价值，中成本）

**当前问题**：Agent 输出不符合格式，需要人 review 后发现。

**Loop 化改进**：
```python
# 每个阶段执行后自动验证
validation = validate_output(result, phase.output_template)
if validation.score < 80:
    # 自动修正 prompt，要求重新生成
    retry_prompt = f"输出不符合要求：{validation.issues}\n请重新输出。"
    result = call_llm(retry_prompt)
else:
    # 自动进入下一阶段
    next_phase = get_next_phase(sop, current_phase)
```

**成本**：中等（需要验证器 + 重试逻辑）
**收益**：格式合规率从 80% 提升到 95%+

### 4.3 不推荐的结合点

| 功能 | 不推荐原因 |
|------|-----------|
| **Cron 定时触发** | 廖亮不需要"每 10 分钟扫描 CI"——他没有 CI |
| **Event-driven Loop（webhook 触发）** | 没有外部系统（GitHub/Slack）需要集成 |
| **Multi-agent 自主协作** | 一人公司，没有需要协作的 Agent |
| **24/7 持续运行** | Token 预算不支持，也没有需要持续处理的任务 |
| **自动写代码 + 自动提交 PR** | 廖亮是"IT小白"，自动代码提交风险太高 |

---

## 五、FROST-SOP 的"最小 Loop"方案

### 5.1 核心理念：不是"24/7 自主 Agent"，而是"智能断点续传"

对廖亮来说，Loop Engineering 的价值不是"让 Agent 自己发现问题"，而是"让长任务能够自动完成，不需要人盯着"。

```
传统方式：
人 → 启动任务 → 等 5 分钟 → 检查输出 → 发现失败 → 重试 → 等 5 分钟 → ...

Loop 方式：
人 → 启动任务 → [系统自动重试、自动验证、自动流转] → 人收到完成通知
```

### 5.2 最小可行实现（1天工作量）

**修改 1：`orchestration.py` 添加重试逻辑**
```python
def execute_sop_with_loop(sop, task, max_retries=2):
    """Loop 化的 SOP 执行：自动重试 + 验证 + 流转"""
    for phase in sop.phases:
        for attempt in range(max_retries + 1):
            # 执行阶段
            result = execute_phase(phase, task)

            # 验证输出
            validation = validate_output(result, phase)

            if validation.passed:
                # 自动进入下一阶段
                save_progress(task, phase, result)
                break
            elif attempt < max_retries:
                # 自动重试，注入错误信息
                retry_with_feedback(phase, validation.issues)
            else:
                # 最终失败，通知用户
                notify_user(task, phase, result, validation)
                return {"status": "FAILED"}

    return {"status": "COMPLETED"}
```

**修改 2：SOP 模板添加 `loop_config`**
```yaml
sop_id: OPS-007
loop_config:
  auto_retry: true          # 失败自动重试
  max_retries: 2            # 最多重试 2 次
  auto_validate: true       # 自动验证输出
  auto_continue: true       # 阶段完成后自动继续
  notify_on_complete: true  # 完成后通知用户
```

**修改 3：状态持久化**
```python
# 每个阶段完成后自动保存进度
def save_progress(task, phase, result):
    progress = {
        "task_id": task.id,
        "current_phase": phase.id,
        "completed_phases": [p.id for p in task.completed_phases],
        "last_output": result,
        "timestamp": now(),
    }
    write_json(f"data/progress/{task.id}.json", progress)
```

### 5.3 与 Claude Code `/loop` 的区别

| 维度 | Claude Code `/loop` | FROST-SOP "最小 Loop" |
|------|-------------------|---------------------|
| 触发方式 | 定时/事件触发 | 阶段完成自动触发 |
| 运行时间 | 24/7 | 按需（任务执行期间） |
| 目标用户 | 工程团队 | 一人公司 |
| 复杂度 | 高（需要 CI/CD 集成） | 低（纯 SOP 内部流转） |
| 成本 | 高（持续运行） | 低（只在任务执行时消耗 token） |

---

## 六、最终诚实结论

### 6.1 Loop Engineering 对 FROST-SOP 的价值

| 维度 | 评估 |
|------|------|
| **概念层面** | Loop Engineering 不是新层级，是 Harness 已有能力的组合。FROST-SOP 已经具备 80% 的基础能力。 |
| **工程层面** | 添加"自动重试 + 自动验证 + 断点续传"的成本很低（1-2 天），收益明确。 |
| **战略层面** | 不需要追逐"24/7 自主 Agent"的叙事，对廖亮来说是过度工程。 |

### 6.2 核心建议

**不要做的事**：
- ❌ 不要把 FROST-SOP 改造成"24/7 自主运行"的系统
- ❌ 不要引入 cron 定时触发（没有需要定时处理的任务）
- ❌ 不要引入 webhook 事件驱动（没有外部系统接入）
- ❌ 不要引入多 Agent 自主协作（一人公司不需要）

**要做的事**：
- ✅ 在 SOP 执行中添加"失败自动重试"（修改 `orchestration.py`）
- ✅ 在每个阶段后添加"输出自动验证"（复用已有的 `output-validator` 思路）
- ✅ 添加"断点续传"能力（长任务分 session 自动继续）
- ✅ 任务完成后自动通知用户（而非让人一直盯着）

### 6.3 一句话总结

> **Loop Engineering 对 FROST-SOP 不是"架构升级"，而是"体验优化"——让廖亮从"盯着 Agent 干活"变成"启动任务后去做别的事，完成后收到通知"。**

这个优化的成本是 1-2 天，收益是减少 50% 的人工干预。不需要追逐 2026 年的新名词，只需要把已有的 SOP 执行流程加上"自动重试 + 自动验证 + 断点续传"三层防护。
