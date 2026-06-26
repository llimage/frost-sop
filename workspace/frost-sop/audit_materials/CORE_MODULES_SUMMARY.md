# CORE_MODULES_SUMMARY — 核心模块代码摘要

> 本文档列出每个核心文件的代码行数、职责和关键函数。标注 [FULL CODE] 的文件建议审计师重点审查。

## 一、core/ 核心抽象层 (13 文件, 3,598 行)

### [FULL CODE] core/db.py (936 行)
**职责**: SQLite 单例数据库管理器，管理 17 张表的连接、初始化、迁移和 CRUD

**关键类/函数**:
```python
class DBManager:
    def __new__(cls)                    # 单例模式
    def __init__(self)
    def get_connection()                # 获取/创建 SQLite 连接
    def close()                         # 关闭连接
    def init_tables()                   # 初始化所有表（含迁移检查）
    def _migrate_*_table(self, cursor)  # 5个迁移方法
    def insert(self, table, data)       # 通用 INSERT
    def update(self, table, data, where)
    def delete(self, table, where)
    def select_one(self, table, where)
    def select_all(self, table, ...)
    def execute_sql(self, sql, params)

    # 业务方法
    def save_task(data)
    def get_task(task_id)
    def save_agent(data)
    def get_agent(agent_id)
    def log_cost(task_id, agent_id, model, ...)
    def log_audit(agent_id, action, details)
    def get_monthly_cost(year, month)
    def get_table_counts()

    # 能量管理
    def add_energy_log(agent_id, energy_level, ...)
    def get_energy_history(agent_id)
    def get_latest_energy(agent_id)

    # 日程管理
    def add_schedule(data)
    def get_schedules()
    def update_schedule(id, data)
    def delete_schedule(id)
    def get_upcoming_reminders()
    def mark_schedule_notified(id)

# 模块级便捷函数
def get_db()      # DBManager 单例
def close_db()
def get_db_connection()
```

### [FULL CODE] core/store.py (308 行)
**职责**: 三级键值存储体系 — Store (基础) / HierarchicalStore (层级继承) / AssetStore (文件持久化)

**关键类/函数**:
```python
class Store:
    def __init__(self, db: DBManager = None)
    def save(self, key, value)          # 写入 + SQLite 持久化
    def load(self, key)                 # 读取
    def delete(self, key)
    def list_keys(self)
    def _persist_to_sqlite(self, key, value)
    def _delete_from_sqlite(self, key)

class HierarchicalStore(Store):
    def __init__(self, own_store, parent, frozen_keys)
    def save(self, key, value)          # 检查 frozen_keys 只读保护
    def load(self, key)                 # 先查自己，再查父辈
    def delete(self, key)
    def list_keys(self, include_parent=True)
    def list_own_keys(self)
    def merge_from(self, other_store, filter_func)  # 经验合并

class AssetStore:
    def __init__(self, assets_dir)      # JSON 文件持久化
    def save(self, key, value)
    def load(self, key)
    def list(self)
    def load_latest(self, prefix)
```

### [FULL CODE] core/agent.py (245 行)
**职责**: 家族神经元，持有记忆(Store)和能力(Skills)，行为完全由外部 SOP 步骤决定

**关键类/函数**:
```python
class Agent:
    def __init__(self, name, store, skills, generation, role, parent)
    def run(self, sop_steps, initial_context)       # 同步执行 SOP 步骤
    async def run_async(self, sop_steps, initial_context)  # 异步执行
    def spawn(self, name, store, skills, ...)       # 孵化子 Agent
    def teach(self, child, sop_steps)               # 教子 Agent
    def receive_teaching(self, sop_steps)           # 接受教学
    def internalize(self)                           # 内化自身经验
    def learn(self, key, value)                     # 学习存储
    def recall(self, key)                           # 回忆存储
    def get_history(self, limit)
```

### [FULL CODE] core/skill.py (35 行)
**职责**: 最小能力单元（类似生物蛋白质），无状态，接收 context dict 返回更新后的 context dict

**关键类/函数**:
```python
class Skill:
    def __init__(self, name, func)
    def execute(self, context) -> dict
```

### [FULL CODE] core/sop.py (104 行)
**职责**: SOP 宪法文本定义 + 执行前治理校验

**关键类/函数**:
```python
class SOP:
    def __init__(self, sop_id, name, version, stages, ...)
    @classmethod
    def load_from_yaml(cls, filepath) -> SOP

class SOPValidator:
    def validate(self, sop, rules) -> dict
```

### core/skill_extractor.py (316 行)
**职责**: 从工具调用日志自动提取可复用 Skill 模式，支持草稿→扫描→验证→激活流程

**关键类/函数**:
```python
class SkillExtractor:
    def __init__(self, tool_calls_dir)
    def scan_successful_calls(self, limit)    # 扫描成功日志
    def _generate_skill_id(self, skill_name)  # 生成 skill_ext_xxx_yyy ID
    def extract_skill_from_call(self, call)   # 从单条日志提取
    def generate_skill_draft(self, call)      # 生成 Skill 草案
    def scan_and_extract_all(self)            # 批量扫描提取
    def validate_skill(self, skill_id, test_runs)  # mock LLM 测试3次
    def validate_all_drafts(self)             # 批量验证
```

### core/skill_version.py (230 行)
**职责**: Skill 版本管理（创建/回滚/历史/清理旧版本）

**关键类/函数**:
```python
class SkillVersionManager:
    def __init__(self, skills_dir)
    def _get_skill_dir(self, skill_name)
    def create_new_version(self, ...)        # 递增主版本
    def rollback(self, skill_id, target_version)
    def get_versions(self, skill_id)
    def get_latest_version(self, skill_id)
    def _cleanup_old_versions(self, skill_id)  # 保留最多5个
```

---

## 二、agents/ Agent 工厂层 (4 文件, 238 行)

### agents/ancestor.py (37 行)
**职责**: 始祖 Agent 工厂 (generation=0)，持有宪法 Store，最高权限

```python
def create_ancestor(constitution_store, asset_store) -> Agent:
    # 创建 gen=0 始祖 Agent
    # 持有 ConstitutionStore (只读)
    # 持有 AssetStore (基因模板库)
```

### agents/parent.py (67 行)
**职责**: 父辈 Agent 工厂 (generation=1)，预装 13 个本能 Skill

```python
def create_parent(name, coordination_store) -> Agent:
    # 注册 skill_gene: 前缀下所有 Skill（orchestration/llm/assemble/evolution/tools）
    # 调用 ancestor.spawn() 孵化
```

### agents/elder.py (134 行)
**职责**: 长老 Agent（退休祖辈），独立审计权，不参与执行与决策

```python
def create_elder(name, asset_store, constitution_store) -> Agent:
    # 创建独立审计 Agent
    # 持有 ConstitutionStore (只读) + AssetStore (只读)

def audit_family(context) -> dict:
    # 扫描 task: 前缀的 Store 数据
    # 检查 5 条宪法合规性
    # 写入 lesson: 前缀的错题本
```

---

## 三、skills/ 能力模块层 (12 文件, 2,218 行)

### [FULL CODE] skills/orchestration.py (357 行)
**职责**: SOP 编排中枢 — 管理 Agent 生命周期和执行流程

**关键函数**:
```python
def spawn(context) -> dict         # 孵化子 Agent（调用 parent.spawn）
def emit(context) -> dict          # 产出交付物（写入 output/）
def validate_sop(context) -> dict  # SOP 宪法合规校验
def merge_from(context) -> dict    # 合并子 Agent 经验到父辈
def internalize_sop(context) -> dict  # 内化 SOP 为 Agent 知识
def execute_stage(context) -> dict    # 核心：执行单个 SOP 阶段
    # 1. 提取 stage 定义
    # 2. 匹配 skill (语义搜索 + LLM 合成)
    # 3. assemble_agent 或直接 call_llm
    # 4. 写入 task_stages 表
    # 5. 纪录 cost_log
```

### [FULL CODE] skills/llm.py (284 行)
**职责**: LLM 共享神经系统 — 真实 API 调用 + Mock 测试路由

**关键函数**:
```python
def _mock_response_for_prompt(prompt) -> str:
    # mock 路由优先级（关键词匹配）:
    # 1. Agent 组装 → JSON 配置
    # 2. Skill 合成 → JSON 基因数据
    # 3. 语义匹配 → JSON
    # 4. LLM 产出生成 → 结构化内容
    # 5. 业务关键词 → 对应内容

def call_llm(context) -> dict:
    # 入口：
    # - FROST_TESTING=1 → _mock_response_for_prompt
    # - 否则 → OpenAI API (DeepSeek)
    # - 写入 cost_log
```

### [FULL CODE] skills/assemble.py (283 行)
**职责**: 孙辈 Agent 动态组装 — 能力基因来自资产 Store，缺失时由 LLM 合成

**关键函数**:
```python
def _make_output_skill_func(name, desc, reason_prefix, output_type):
    # 创建输出 Skill（代码/文档/报告等类型）

def assemble_agent(context) -> dict:
    # 1. 搜索 skill_gene: 前缀匹配已有 Skill
    # 2. 缺失 Skill → LLM synthesize_skill
    # 3. 创建 gen=2+ 孙辈 Agent
    # 4. 返回 assembled_agent

def create_skill_from_gene(gene, output_type) -> Skill
def synthesize_skill(skill_name, requirement, asset_store, output_type) -> Skill
```

### skills/evolution.py (212 行)
**职责**: 家族自进化 — 从历史数据提炼优化建议

**关键函数**:
```python
def load_task_history(context) -> dict    # 加载 task: 前缀数据
def analyze_trends(context) -> dict       # 识别成功/失败模式
def generate_suggestions(context) -> dict # 生成优化建议
def present_for_approval(context) -> dict # 提交人类确认
```

### skills/tools.py (112 行)
**职责**: 真实工具 Skill — 文件写入、LLM 输出等

**关键函数**:
```python
def write_file(context) -> dict           # 写入文件到 output/
def call_llm_for_output(context) -> dict  # 调用 LLM 生成结构化输出
```

---

## 四、api/ FastAPI 层 (3 文件, 676 行)

### [FULL CODE] api/main.py (523 行)
**职责**: FastAPI REST 层，13 个端点

**端点列表**:
```python
GET  /api/projects                     # 项目列表
GET  /api/projects/{project_id}        # 项目详情
POST /api/tasks                        # 创建并执行任务
GET  /api/tasks                        # 任务列表
GET  /api/tasks/{task_id}/stages       # 任务阶段详情
GET  /api/costs                        # 成本汇总
GET  /api/agents                       # Agent 列表
POST /api/chat                         # CEO 对话
GET  /api/logs                         # 实时日志 (SSE)
GET  /api/skills                       # 技能库
GET  /api/schedule                     # 日程列表
POST /api/schedule                     # 创建日程
GET  /api/health                       # 健康检查
```

### api/models.py (153 行)
**职责**: Pydantic 请求/响应数据模型（13 个模型类）

```python
class ProjectResponse(BaseModel)
class TaskCreateRequest(BaseModel)
class TaskResponse(BaseModel)
class TaskStageResponse(BaseModel)
class TaskExecuteResponse(BaseModel)
class AgentResponse(BaseModel)
class CostLogResponse(BaseModel)
class CostSummaryResponse(BaseModel)
class ChatRequest(BaseModel)
class ChatResponse(BaseModel)
class SkillResponse(BaseModel)
class ScheduleCreateRequest(BaseModel)
class ScheduleResponse(BaseModel)
```

---

## 五、app.py / main.py 入口

### [FULL CODE] app.py (1,927 行)
**职责**: Streamlit 家族 AI 指挥平台 (F11 项目工作台)

**关键函数**:
```python
def main()                              # Streamlit 入口
def init_family()                       # 初始化三代 Agent
def execute_task(task_text)             # 执行用户任务
def render_commander_dashboard()        # 指挥官驾驶舱
def render_cost_dashboard()             # 成本仪表盘
def render_health_dashboard()           # 家族健康面板
def render_schedule_page()              # 日程管理
def render_energy_logger()              # 能量记录
def render_decision_dialog()            # 决策对话框
def check_daily_review()                # 日终回顾
```

### [FULL CODE] main.py (311 行)
**职责**: CLI 命令行入口，支持 `python main.py --task "xxx" --sop DEV-001`

---

## 六、frontend/ Next.js 前端 (3,813 行)

### [FULL CODE] frontend/src/app/page.tsx (231 行)
**职责**: 驾驶舱首页 — 组合 AgentGrid + LogTerminal + CeoChat + CostDashboard

```tsx
export default function Dashboard() {
  // react-query 加载 agents/projects/costs
  // 左侧: AgentGrid (2列网格)
  // 右上: LogTerminal (深色终端)
  // 右下: CeoChat (对话面板)
  // 底部: CostDashboard (成本进度条)
}
```

### [FULL CODE] frontend/src/lib/api.ts (78 行)
**职责**: 前端 API 调用层，封装所有后端请求

```typescript
export async function getProjects()
export async function getProject(id: string)
export async function createTask(description, sopId, projectId)
export async function getTasks(limit?)
export async function getTaskStages(taskId: string)
export async function getCosts()
export async function getAgents()
export async function sendChat(message: string)
export async function getSkills()
export async function getSchedules()
export async function createSchedule(data)
```

### frontend/src/lib/store.ts (27 行)
**职责**: Zustand 全局状态管理

```typescript
interface AppState {
  currentProjectId: string | null
  currentMode: 'dev' | 'creative' | 'client'
  logs: LogEntry[]
  setProjectId, setMode, addLog, clearLogs
}
export const useStore = create<AppState>(...)
```

### frontend/src/components/
- **Navbar.tsx** (132 行) — 顶部导航，3 模式切换 + 5 页面链接 + 移动端 Sheet 菜单
- **Sidebar.tsx** (110 行) — 侧边栏，项目列表 (react-query) + 快速概览
- **AgentCard.tsx** (138 行) — Agent 卡片 + 2 列网格布局，shadcn Card + Badge
- **LogTerminal.tsx** (92 行) — 实时日志终端，深色主题 + ScrollArea
- **CeoChat.tsx** (209 行) — 指令聊天框，真实 API + 快捷指令 Badge
- **CostBar.tsx** (121 行) — 成本进度条 + 仪表板 (Progress + recharts)

### frontend/src/components/ui/ (19 个 shadcn 组件, 1,917 行)
avatar, badge, button, calendar, card, command, dialog, input, input-group,
popover, progress, scroll-area, select, separator, sheet, switch, table, tabs, textarea
