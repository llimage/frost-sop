# S-O-P v6.1 初始化测试指南

## 测试目标
验证 **初始化问卷 → 缺口识别 → 狩猎任务生成 → 触发狩猎闭环** 全链路

## 快速测试步骤

### 步骤 1: 运行初始化问卷

```bash
cd D:\my_ai\Solo-Ops-Platform\workspace\frost-sop

# 交互模式（推荐测试）
python -m skills.init.questionnaire

# 程序模式（快速验证）
python -c "
from skills.init.questionnaire import InitQuestionnaire
q = InitQuestionnaire()
result = q.run_full_pipeline(answers={
    'identity': 'IT小白，一人公司',
    'destination_6m': '零收入，想盈利',
    'destination_12m': '收入稳定',
    'destination_36m': '平台成熟',
    'assets': 'FROST框架',
    'constraints': '零预算，不懂代码',
    'content_strategy': '小红书',
    'growth_flywheel': '不知道',
})
print(f'识别到 {len(result[\"gaps\"])} 个缺口')
print(f'生成 {len(result[\"tasks\"])} 个任务')
"
```

### 步骤 2: 触发狩猎任务

```bash
python -m skills.init.task_trigger
```

这会：
1. 从 `init_results.json` 加载任务
2. 写入数据库（`project_id=INIT`）
3. 生成 `sops/generated/init_task_sop.md`
4. 触发第一个 P0 狩猎任务

### 步骤 3: 验证狩猎任务已写入

```bash
python -c "
from core.db import get_db
db = get_db()
tasks = db.select_all('tasks', where='project_id=?', params=['INIT'])
print(f'数据库中有 {len(tasks)} 个初始化任务')
for t in tasks:
    print(f'  - {t[\"id\"]}: {t[\"title\"]} [{t[\"status\"]}]')
"
```

### 步骤 4: 运行狩猎 Skill

根据生成的 `target_skill`，运行对应的狩猎：

```bash
# 例如：狩猎小红书运营能力
python main.py --hunt --hunt-target redbook_ops

# 或狩猎零预算工具栈
python main.py --hunt --hunt-target zero_budget_tools
```

## 预期结果

| 阶段 | 输出文件 | 说明 |
|------|----------|------|
| 问卷 | `init_results.json` | 包含 answers, gaps, tasks |
| 触发器 | `init_tasks.json` | 数据库回退模式 |
| 触发器 | `sops/generated/init_task_sop.md` | SOP 文档 |
| 数据库 | `tasks` 表 | project_id=INIT 的任务 |

## 狩猎闭环验证

1. **狩猎前**: 任务状态 = `pending`
2. **狩猎中**: 任务状态 = `running`
3. **狩猎后**: 任务状态 = `done` + 结果写入 `task:` Store

## 服务访问

| 服务 | URL |
|------|-----|
| NiceGUI 驾驶舱 | http://localhost:8080 |
| FastAPI 文档 | http://localhost:8000/docs |
| Next.js 前端 | http://localhost:3000 |
