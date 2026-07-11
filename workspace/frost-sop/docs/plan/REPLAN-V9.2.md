# FROST-SOP V9.2 重构/修复计划

**日期**: 2026-07-09  
**对应文档**: PRD-V2.0.md, DDD-V2.0.md, alignment_audit_v92.md  
**目标**: 基于差距分析，按优先级排序，制定可执行的重构路线图

---

## 1. 重构原则

1. **渐进式重构**: 不一次性重写全部代码，按模块逐步替换
2. **向后兼容**: 每次重构保持现有 API 不变，新增 API 逐步迁移
3. **编码→测试→审计**: 每个模块严格遵循软件工程步骤
4. **用户价值优先**: 先实现用户最痛点的功能（愿景初始化、前端易用性）

---

## 2. 重构路线图

### 阶段 A: 基础架构重构（V9.2-A）
**目标**: 补齐缺失的核心领域类，建立统一状态机
**预计工期**: 2-3 周
**风险**: 低（新增代码，不影响现有功能）

#### A1: Vision 模块（🔴 最高优先级）

**问题**: 愿景初始化是整个流程的起点，完全缺失导致无法开始任务

**任务**:
- [ ] 创建 `core/vision.py` — Vision 领域类 + 多轮问卷澄清算法
- [ ] 创建 `api/visions.py` — Vision REST API 端点
- [ ] 创建前端愿景创建界面 — 多轮问卷交互 UI
- [ ] 集成到任务创建流程 — 创建任务时先创建愿景

**验收标准**:
- 用户输入 "创建一个AI培训项目" → 系统返回 3-5 个澄清问题
- 用户回答后 → 生成结构化愿景文档 → 用户确认 → 自动初始化 SOP
- 置信度 < 0.8 时继续澄清，最多 3 轮

**依赖**: 无（独立模块）

#### A2: 统一状态机引擎（🔴 最高优先级）

**问题**: 状态管理分散在多个文件中，没有统一的状态机

**任务**:
- [ ] 创建 `core/state_machine.py` — 通用状态机框架
- [ ] 重构 `core/agent.py` — 使用状态机管理 Agent 生命周期
- [ ] 重构 `core/sop.py` — SOPStage 使用状态机
- [ ] 重构 `core/project.py` — Task 使用状态机
- [ ] 重构 `core/decision_manager.py` — DecisionPoint 使用状态机

**状态机设计**:
```python
class StateMachine:
    def __init__(self, states: List[str], transitions: List[Transition]):
        self.states = states
        self.transitions = transitions
        self.current_state = states[0]
    
    def can_transition(self, event: str) -> bool:
        # 检查当前状态下是否允许该事件
        pass
    
    def transition(self, event: str, context: dict) -> bool:
        # 执行状态转换，触发副作用
        pass
    
    def on_enter(self, state: str, callback: Callable):
        # 注册进入状态的回调
        pass
    
    def on_exit(self, state: str, callback: Callable):
        # 注册离开状态的回调
        pass
```

**验收标准**:
- 所有实体（Agent, Task, Stage, Decision）使用统一状态机
- 状态转换有明确的触发条件和副作用
- 非法状态转换抛出异常，不静默失败

**依赖**: 无（基础框架）

#### A3: HumanFootman 机制（🔴 最高优先级）

**问题**: 人类只是 DecisionManager 的调用方，没有作为 Agent 的状态管理

**任务**:
- [ ] 创建 `core/human_footman.py` — HumanFootman 领域类
- [ ] 扩展 `core/decision_manager.py` — 添加超时自动处理
- [ ] 创建 `api/human_footman.py` — 人类府兵 API 端点
- [ ] 创建前端决策面板 — 待决策队列、超时提醒

**HumanFootman 设计**:
```python
class HumanFootman(Agent):
    """人类作为特殊 Agent"""
    
    def __init__(self, footman_id: str, name: str):
        super().__init__(
            name=name,
            agent_type="human",
            generation=0,  # 人类是第 0 代
        )
        self.footman_id = footman_id
        self.status = "idle"  # idle | busy | offline
        self.pending_decisions = []
        self.max_concurrent = 3
        self.default_timeout_minutes = 30
        self.timeout_action = "escalate"
    
    def assign_decision(self, decision: DecisionPoint):
        """分配决策任务"""
        if len(self.pending_decisions) >= self.max_concurrent:
            raise TooManyDecisionsError()
        self.pending_decisions.append(decision)
        self.status = "busy"
        self.notify_user(decision)
    
    def respond_decision(self, decision_id: str, decision: str, reason: str):
        """响应决策"""
        dp = self.find_decision(decision_id)
        dp.resolve(decision, reason)
        self.pending_decisions.remove(dp)
        if not self.pending_decisions:
            self.status = "idle"
    
    def check_timeout(self):
        """检查超时决策"""
        for dp in self.pending_decisions:
            if dp.is_expired():
                self.handle_timeout(dp)
```

**验收标准**:
- 人类有 idle/busy/offline 状态
- 最多 3 个并行决策
- 30 分钟超时自动 escalate/abort/auto_approve
- 前端显示待决策队列和超时倒计时

**依赖**: A2（状态机）

---

### 阶段 B: 核心能力补齐（V9.2-B）
**目标**: 实现自进化、隐私保护、本地 LLM 等差异化能力
**预计工期**: 3-4 周
**风险**: 中（涉及多个模块联动）

#### B1: EvolutionEngine 完整闭环（🟡 高优先级）

**问题**: 只有 lesson_archivist.py 做教训归档，没有完整的 6 阶段闭环

**任务**:
- [ ] 创建 `core/evolution_engine.py` — 完整自进化引擎
- [ ] 实现 6 阶段闭环: 错误检测 → 教训归档 → 趋势分析 → 复盘决策 → 系统进化 → 验证回滚
- [ ] 创建 `api/evolution.py` — 进化 API（V9.1 已部分实现）
- [ ] 创建前端进化仪表盘 — 错误趋势、优化建议、版本历史
- [ ] 集成到现有任务执行流程 — 失败自动触发进化

**EvolutionEngine 设计**:
```python
class EvolutionEngine:
    """自进化引擎: 错误记录 → 教训归档 → 趋势分析 → 复盘决策 → 系统进化 → 验证回滚"""
    
    def __init__(self, store: Store, llm_client: LLMClient):
        self.store = store
        self.llm_client = llm_client
        self.lesson_archivist = LessonArchivist(store, llm_client)
    
    def run_cycle(self):
        """执行一个完整的进化周期"""
        # 阶段1: 错误检测与记录
        errors = self.detect_errors()
        for error in errors:
            self.record_error(error)
        
        # 阶段2: 教训归档
        for error in errors:
            if not error.lesson_id:
                lesson = self.lesson_archivist.archive(error)
                error.lesson_id = lesson.id
        
        # 阶段3: 趋势分析
        trends = self.analyze_trends(time_range="7d")
        
        # 阶段4: 生成优化建议
        proposals = self.generate_proposals(trends)
        
        # 阶段5: 等待人类确认（决策点）
        for proposal in proposals:
            decision = self.create_decision(proposal)
            # 人类确认后执行进化
            if decision.status == "approved":
                self.apply_evolution(proposal)
        
        # 阶段6: 验证与回滚
        for evolution in self.pending_validations:
            if not self.validate(evolution):
                self.rollback(evolution)
```

**验收标准**:
- 任务失败自动记录错误、生成教训
- 每周自动生成趋势分析报告
- 优化建议需要人类确认（30 分钟超时）
- 进化失败自动回滚到上一版本

**依赖**: A1（Vision）, A2（状态机）, A3（HumanFootman）

#### B2: 隐私脱敏 + 本地 LLM（🟡 高优先级）

**问题**: 用户明确要求隐私保护，当前所有数据直接发送到云端 LLM

**任务**:
- [ ] 创建 `core/privacy.py` — 脱敏引擎
- [ ] 创建 `core/local_llm.py` — Ollama 客户端封装
- [ ] 实现脱敏规则: 姓名→[NAME], 电话→[PHONE], 金额→[AMOUNT]
- [ ] 实现本地 LLM 调用: 简单任务本地处理，复杂任务脱敏后云端处理
- [ ] 创建前端本地 LLM 配置界面 — 模型选择、启动/停止
- [ ] 创建 `docs/local_llm_setup.md` — 本地 LLM 安装指南

**脱敏策略**:
```python
class PrivacyEngine:
    """隐私保护引擎"""
    
    RULES = {
        "name": {"pattern": r"[\u4e00-\u9fa5]{2,4}", "replacement": "[NAME]"},
        "phone": {"pattern": r"1[3-9]\d{9}", "replacement": "[PHONE]"},
        "email": {"pattern": r"[\w.-]+@[\w.-]+\.\w+", "replacement": "[EMAIL]"},
        "amount": {"pattern": r"¥?\d{1,3}(,\d{3})*(\.\d+)?", "replacement": "[AMOUNT]"},
        "company": {"pattern": r"(?:公司|企业|集团)", "replacement": "[COMPANY]"},
    }
    
    def sanitize(self, text: str) -> str:
        """脱敏文本，保留语义"""
        for rule_name, rule in self.RULES.items():
            text = re.sub(rule["pattern"], rule["replacement"], text)
        return text
    
    def desanitize(self, text: str, mapping: dict) -> str:
        """根据映射恢复原始数据"""
        for placeholder, original in mapping.items():
            text = text.replace(placeholder, original)
        return text
```

**本地 LLM 配置**:
```python
class LocalLLMClient:
    """Ollama 本地 LLM 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.available_models = []
    
    def list_models(self) -> List[str]:
        """列出可用的本地模型"""
        response = requests.get(f"{self.base_url}/api/tags")
        return [m["name"] for m in response.json()["models"]]
    
    def chat(self, model: str, messages: List[dict], **kwargs) -> str:
        """本地聊天"""
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={"model": model, "messages": messages, **kwargs}
        )
        return response.json()["message"]["content"]
```

**验收标准**:
- 敏感数据在发送到云端 LLM 前自动脱敏
- 本地 LLM 可处理简单任务（愿景澄清、意图识别）
- 用户可选择使用本地 LLM 或云端 LLM
- 提供 Ollama 安装和配置指南

**依赖**: 无（独立模块）

#### B3: 成本熔断完善（🟡 中优先级）

**问题**: 当前只有月度预算，缺少日预算、熔断阈值、自动暂停

**任务**:
- [ ] 扩展 `core/cost.py` — 添加日预算、熔断阈值
- [ ] 实现自动暂停: 超预算时暂停非关键任务
- [ ] 实现成本预警: 50%/80%/100% 预算使用时通知
- [ ] 创建前端成本预警组件 — 横幅提醒、预算设置

**验收标准**:
- 日预算超支自动暂停新任务
- 单次调用超过 ¥1000 熔断
- 前端显示预算使用进度条和预警

**依赖**: 无（独立模块）

---

### 阶段 C: 前端重构（V9.2-C）
**目标**: 补齐缺失的前端页面，提升用户体验
**预计工期**: 2-3 周
**风险**: 中（前端是用户痛点）

#### C1: 愿景创建界面（🔴 最高优先级）

**问题**: 用户无法通过前端创建愿景，整个流程无法开始

**任务**:
- [ ] 创建 `app/visions/page.tsx` — 愿景列表
- [ ] 创建 `app/visions/new/page.tsx` — 创建愿景（多轮问卷）
- [ ] 创建 `app/visions/[id]/page.tsx` — 愿景详情
- [ ] 创建 `components/VisionClarifier.tsx` — 多轮问卷组件

**设计**:
```
┌─────────────────────────────────────────┐
│  创建新愿景                              │
│                                         │
│  请输入你的项目愿景:                      │
│  ┌─────────────────────────────────┐   │
│  │ 创建一个AI在线培训项目           │   │
│  └─────────────────────────────────┘   │
│                                         │
│  [提交]                                 │
│                                         │
│  ─────────────────────────────────────  │
│  系统需要澄清几个问题:                  │
│                                         │
│  Q1: 培训的目标受众是谁？               │
│  ┌─────────────────────────────────┐   │
│  │ 心理咨询师和社工                 │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Q2: 培训形式是什么？                   │
│  [视频] [文字] [互动] [混合]            │
│                                         │
│  [确认并生成愿景]                       │
│                                         │
│  ─────────────────────────────────────  │
│  愿景文档:                              │
│  ┌─────────────────────────────────┐   │
│  │ 结构化目标: ...                  │   │
│  │ 成功标准: ...                   │   │
│  │ 置信度: 92%                      │   │
│  └─────────────────────────────────┘   │
│                                         │
│  [确认] [重新澄清] [修改]               │
└─────────────────────────────────────────┘
```

**验收标准**:
- 用户输入愿景 → 系统返回澄清问题 → 用户回答 → 生成愿景文档 → 确认
- 最多 3 轮澄清
- 置信度实时显示

**依赖**: A1（Vision API）

#### C2: 决策面板（🔴 高优先级）

**问题**: 有 API 但没有对应的 UI，人类无法响应决策

**任务**:
- [ ] 创建 `components/DecisionPanel.tsx` — 待决策列表
- [ ] 创建 `components/DecisionCard.tsx` — 单个决策卡片
- [ ] 集成到项目详情页 — 显示当前项目的待决策
- [ ] 实现 SSE 实时推送 — 新决策到达时通知

**设计**:
```
┌─────────────────────────────────────────┐
│  待决策 (3)                              │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ ⚠️ 决策点 #123                   │   │
│  │ 任务: AI培训项目-需求分析        │   │
│  │ 问题: 是否使用视频作为主要形式？   │   │
│  │ 超时: 剩余 15 分钟               │   │
│  │                                 │   │
│  │ [是] [否] [修改]                │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ ⚠️ 决策点 #124                   │   │
│  │ 任务: AI培训项目-技术选型        │   │
│  │ 问题: 技术栈选择 React 还是 Vue？ │   │
│  │ 超时: 剩余 28 分钟               │   │
│  │                                 │   │
│  │ [React] [Vue] [其他]            │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

**验收标准**:
- 显示所有待决策，按超时时间排序
- 每个决策显示问题、选项、超时倒计时
- 响应后实时更新状态
- 超时决策标记为红色

**依赖**: A3（HumanFootman API）

#### C3: 进化仪表盘（🟡 中优先级）

**问题**: 自进化能力没有可视化界面

**任务**:
- [ ] 创建 `app/evolution/page.tsx` — 进化仪表盘
- [ ] 创建 `components/ErrorTrendChart.tsx` — 错误趋势图
- [ ] 创建 `components/LessonList.tsx` — 教训列表
- [ ] 创建 `components/OptimizationProposalCard.tsx` — 优化建议卡片

**验收标准**:
- 显示本周错误趋势（折线图）
- 显示已归档教训列表
- 显示待确认优化建议
- 显示进化历史（版本时间线）

**依赖**: B1（EvolutionEngine API）

---

### 阶段 D: 架构优化（V9.2-D）
**目标**: 提升代码质量，降低技术债务
**预计工期**: 1-2 周
**风险**: 低（重构为主，不影响功能）

#### D1: API 层与领域层分离

**问题**: api/main.py 既处理 HTTP 又处理业务逻辑

**任务**:
- [ ] 创建 `services/` 目录 — 业务逻辑层
- [ ] 将 api/main.py 中的业务逻辑移到 services/
- [ ] api/main.py 只负责: 路由、参数校验、调用 services、返回响应

**目录结构**:
```
api/
  main.py          # 只负责路由注册和 HTTP 协议
  models.py        # Pydantic 模型
  dependencies.py  # 依赖注入
services/
  task_service.py      # 任务业务逻辑
  agent_service.py     # Agent 业务逻辑
  vision_service.py    # 愿景业务逻辑
  decision_service.py  # 决策业务逻辑
  cost_service.py      # 成本业务逻辑
  evolution_service.py # 进化业务逻辑
```

**验收标准**:
- api/main.py 每行代码不超过 20 行
- 所有业务逻辑在 services/ 中
- 单元测试可以直接测试 services/ 而不需要启动 HTTP

#### D2: 前端类型安全

**问题**: 前端大量使用 `any` 类型

**任务**:
- [ ] 创建 `types/` 目录 — 共享类型定义
- [ ] 定义核心类型: Task, Agent, Stage, Decision, Vision, Skill
- [ ] 逐步替换 `any` 为具体类型
- [ ] 启用 TypeScript strict 模式

**验收标准**:
- `any` 使用量减少 80%
- `tsc --noEmit` 无错误

#### D3: 测试覆盖提升

**问题**: 只有 8 个回归测试，缺少单元测试

**任务**:
- [ ] 为核心领域类添加单元测试: Store, Skill, SOP, Agent, Vision
- [ ] 为 services/ 添加单元测试
- [ ] 为 API 端点添加集成测试
- [ ] 目标: 核心模块 80% 覆盖率

---

## 3. 执行计划表

### 3.1 按阶段排序

| 阶段 | 模块 | 优先级 | 工期 | 依赖 | 风险 |
|------|------|--------|------|------|------|
| **A1** | Vision 模块 | 🔴 | 1 周 | 无 | 低 |
| **A2** | 统一状态机 | 🔴 | 1 周 | 无 | 低 |
| **A3** | HumanFootman | 🔴 | 1 周 | A2 | 低 |
| **C1** | 愿景前端 | 🔴 | 1 周 | A1 | 中 |
| **C2** | 决策面板 | 🔴 | 1 周 | A3 | 中 |
| **B1** | EvolutionEngine | 🟡 | 2 周 | A1,A2,A3 | 中 |
| **B2** | 隐私+本地LLM | 🟡 | 2 周 | 无 | 中 |
| **B3** | 成本熔断 | 🟡 | 0.5 周 | 无 | 低 |
| **C3** | 进化仪表盘 | 🟡 | 1 周 | B1 | 中 |
| **D1** | API分层 | 🟢 | 1 周 | 无 | 低 |
| **D2** | 类型安全 | 🟢 | 1 周 | 无 | 低 |
| **D3** | 测试覆盖 | 🟢 | 1 周 | D1 | 低 |

### 3.2 按时间线排序（推荐执行顺序）

**第 1-2 周: 基础架构**
- A1: Vision 模块
- A2: 统一状态机
- C1: 愿景前端（与 A1 并行）

**第 3-4 周: 核心机制**
- A3: HumanFootman
- C2: 决策面板（与 A3 并行）
- B3: 成本熔断（独立）

**第 5-6 周: 差异化能力**
- B1: EvolutionEngine
- B2: 隐私+本地LLM（与 B1 并行）

**第 7-8 周: 前端补齐**
- C3: 进化仪表盘
- D1: API 分层（后台）

**第 9-10 周: 质量提升**
- D2: 类型安全
- D3: 测试覆盖

---

## 4. 资源需求

### 4.1 开发资源

| 角色 | 工作量 | 说明 |
|------|--------|------|
| 后端开发 | 60% | Python/FastAPI 领域类、API、状态机 |
| 前端开发 | 30% | Next.js/React 页面、组件、类型 |
| 测试/审计 | 10% | 单元测试、集成测试、代码审计 |

### 4.2 外部依赖

| 依赖 | 状态 | 风险 |
|------|------|------|
| Ollama 本地 LLM | 需安装 | 低（用户自行安装） |
| DeepSeek API Key | 已有 | 低 |
| Next.js 16 + React 19 | 已有 | 低 |
| SQLite | 已有 | 低 |

### 4.3 成本估算

| 项目 | 估算 |
|------|------|
| LLM 调用（开发测试）| ¥200-300 |
| 本地 LLM 运行（电费）| 可忽略 |
| 总开发成本 | ¥300-500 |

---

## 5. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解策略 |
|------|--------|------|----------|
| 前端开发进度慢 | 高 | 高 | 优先核心页面，使用现成组件库 |
| 状态机重构引入 Bug | 中 | 高 | 逐步替换，保持向后兼容，充分测试 |
| 本地 LLM 性能不足 | 中 | 中 | 量化模型降级，云端兜底 |
| 自进化效果不佳 | 中 | 中 | 人类确认环节，回滚机制 |
| 重构周期过长 | 中 | 高 | 按阶段交付，每阶段可独立发布 |

---

## 6. 验收里程碑

### 里程碑 1: 基础架构完成（第 2 周末）
- [ ] Vision 模块可用（创建、澄清、确认）
- [ ] 统一状态机运行（Agent, Task, Stage）
- [ ] 愿景前端可用

### 里程碑 2: 核心机制完成（第 4 周末）
- [ ] HumanFootman 机制运行（状态、超时、队列）
- [ ] 决策面板可用
- [ ] 成本熔断运行

### 里程碑 3: 差异化能力完成（第 6 周末）
- [ ] 自进化闭环运行（错误→教训→趋势→建议→进化→验证）
- [ ] 隐私脱敏运行
- [ ] 本地 LLM 可配置

### 里程碑 4: 完整产品（第 10 周末）
- [ ] 所有 PRD 需求实现
- [ ] 前端所有页面可用
- [ ] 测试覆盖 80%+
- [ ] 代码审计通过

---

## 7. 下一步行动

**立即开始**: 阶段 A1 — Vision 模块

1. 创建 `core/vision.py` — Vision 领域类
2. 创建 `api/visions.py` — Vision API 端点
3. 创建前端愿景创建界面

**按照你的节奏，编码→测试→审计全量严格执行。**

---

*本计划基于 alignment_audit_v92.md 的差距分析，按优先级排序，确保每次重构都有明确的用户价值。*
