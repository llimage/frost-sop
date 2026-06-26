# FROST-SOP 项目状态摘要（2026-06-24）

## 当前分支

```
分支: feature/workbench-rebuild
基线: v1.0.0-f10-baseline
```

F10 功能基线已打 tag，所有工作台开发在 `feature/workbench-rebuild` 分支进行。main 不动。

---

## 项目定位

FROST-SOP = 家族AI指挥平台。三代分形Agent架构（祖辈/父辈/孙辈），SOP驱动执行。Streamlit 驾驶舱。F1-F10 功能全部完成，**现在处于 F11 项目工作台 UI 精调阶段**。

---

## 当前 F11 工作台 UI 规范（SaaS 专业风格）

```
底色：中性冷灰 #F4F6F8（主背景）、白色 #FFFFFF（卡片）
主色：蓝色 #3B82F6（按钮、进度条、链接）
导航栏：深灰 #1E293B（顶部横向）
辅色：灰蓝 #64748B（辅文）、墨绿 #22C55E（成功状态）
文字：深灰 #0F172A（主文）、灰色 #64748B（辅文）
警告：琥珀 #F59E0B、危险 #EF4444
圆角：统一 6-8px
卡片边框：1px solid #E2E8F0
日志窗口：深色终端 #0F172A + 等宽字体
布局：左 7 / 右 3 分栏，Agent 网格 2 列
```

所有 CSS 在 `app.py` 的 `inject_css()` 函数中（第52行起）。

---

## 驾驶舱布局（自顶向下）

| 层级 | 内容 | 对应函数 |
|------|------|----------|
| 顶部导航栏 | 品牌 "FROST-SOP \| 家族AI指挥平台" + 菜单（仪表盘/技能库/成本/输出文档/设置）+ 右上角头像(L)+任务状态 | `render_commander_dashboard()` L653 |
| 项目概览 | 项目名+进度+状态标签+"CEO Agent 监控中" | 仪表盘主区 |
| KPI卡片(4列) | 任务进度 / 运行中Agent / 已消耗成本 / 预计完成 | 仪表盘主区 |
| Agent团队矩阵 | 8个Agent卡片网格（角色/状态/模型/依赖） | `get_agent_team()` L594 |
| 成本面板 | 预算消耗长条 + 模型成本细分（Anthropic/OpenAI等） | `render_cost_dashboard()` L1452 |
| 右侧面板 | CEO对话输入框 + 3快捷指令 + 模式切换 | `render_command_panel()` L1214 |
| 实时日志 | 深色终端窗口，最多显示20条 | 仪表盘底部 |
| 底部家族状态 | 祖辈/父辈/孙辈/月度Token | main() 底部区域 |

---

## 核心文件速查

| 文件 | 大小 | 说明 |
|------|------|------|
| `app.py` | 1927行 / 77k | Streamlit 驾驶舱入口。所有 UI + CSS + 渲染函数 |
| `core/workbench.py` | ~460行 | F11 工作台核心逻辑：项目默认值、任务推荐、日终回顾、业务雷达 |
| `core/db.py` | ~940行 | SQLite 数据库管理（单例 get_db()），17 张表 |
| `core/cost.py` | ~180行 | 成本追踪器（Token/API 用量） |
| `core/decision_manager.py` | ~275行 | F8 决策点管理 |
| `core/skill_extractor.py` | - | F10 Skill 自动提取 |
| `core/skill_version.py` | - | F10 Skill 版本管理 |
| `skills/llm.py` | - | LLM 调用 + mock 路由 |
| `skills/orchestration.py` | - | SOP 内化 + 阶段执行 |
| `skills/assemble.py` | - | 孙辈 Agent 动态组装 |
| `agents/parent.py` | - | 父辈 Agent |
| `agents/elder.py` | - | 长老审计 |
| `skills/evolution.py` | - | STR-002 自进化 |

---

## 数据库（17 张表）

`data/frost_sop.db`（SQLite），关键表：
- `projects` — 项目配置（sop_template/energy_level/config_ref/metadata）
- `tasks` — 任务记录
- `skills` / `skill_versions` — F10 Skill 基因库
- `decision_points` — F8 决策点（含 status=auto_cancelled 清理机制）
- `daily_reviews` — F11 日终回顾
- `config_snapshots` — F6.5 项目配置快照
- `project_skills` — 项目-Skill 关联
- `cost_log` — 成本日志
- `energy_log` — F9 能量日志
- `constitution` / `lessons` / `assets` — 宪法/错题本/资产 Store

---

## app.py 全部函数索引（1927行）

```
L52  inject_css()               — 全局 SaaS 风格 CSS
L430 is_mobile()                — URL参数 ?mobile=1
L461 add_log()                  — 日志追加
L472 render_decision_dialog()   — F8 决策弹窗（启动时自动清理残留）
L594 get_agent_team()           — Agent 团队数据
L653 render_commander_dashboard() — 仪表盘主渲染（入口函数）
L973 check_daily_review()       — 日终回顾检查（18:00后）
L1022 render_project_detail()   — 项目详情页
L1119 render_daily_review_detail() — 日终回顾详情
L1165 render_mobile_view()      — 移动端精简版
L1214 render_command_panel()    — 右侧 CEO 对话面板
L1285 execute_task()            — 任务执行
L1452 render_cost_dashboard()   — 成本面板
L1489 _count_gene_templates()   — 兵器库模板统计
L1496 _show_armory_templates()  — 浏览模板
L1519 _show_mercenaries()       — 查看雇佣兵
L1527 render_energy_logger()    — 能量记录器
L1584 render_schedule_page()    — 日程管理
L1647 render_health_dashboard() — 家族健康面板
L1684 init_family()             — 家族系统初始化
L1700 load_tasks_from_store()   — 从 Store 加载任务
L1719 auto_wake()               — F6.5 自动唤醒
L1734 save_tasks_to_store()     — 保存任务到 Store
L1740 create_task_internal()    — 内部创建任务
L1763 main()                    — 主入口（启动清理 + 视图路由）
L1861 render_sidebar()          — 侧边栏
```

---

## 测试状态

```
106 tests / 105 passed / 1 基线已知错误
```

那个 1 个（F8 test_audit_log_after_decision）是数据库状态泄漏问题，与工作台 UI 无关。

**运行测试命令**（Windows）：
```bash
cd workspace/frost-sop
set FROST_TESTING=1 && python -X utf8 -m pytest tests/ -v -s -q
```

---

## 一键启动

双击 `workspace/frost-sop/启动工作台.bat`（已修复编码为 GBK，不再乱码）。

启动后访问：
- 桌面版：`http://localhost:8501`
- 移动版：`http://localhost:8501/?mobile=1`

---

## 最近修复（2026-06-24）

1. **启动时弹出"决策点"对话框** — 修复：`main()` 里新增启动时自动清理逻辑，将数据库中所有旧 pending 决策标记为 `auto_cancelled`，仅本会话内新建的才弹出
2. **决策按钮英文问题** — 修复：`skills/orchestration.py` 默认值从 `["confirm","reject","modify"]` 改为 `["确认","驳回","修改"]`；`app.py` 渲染层加了英→中 fallback 映射
3. **启动脚本乱码** — 修复：`.bat` 文件改为 GBK 编码 + Python 绝对路径

---

## Store 前缀规则（全系统通用）

| 前缀 | 用途 | 读写 |
|------|------|------|
| `task:` | 任务资产 | 读写 |
| `constitution:` | 宪法规则 | 只读 |
| `lesson:` | 错题本 | 读写 |
| `skill_gene:` | 技能基因库 | 读写 |

---

## mock 模式

设置环境变量 `FROST_TESTING=1` 即可跳过真实 LLM 调用。mock 路由逻辑在 `skills/llm.py` 的 `_mock_response_for_prompt()` 中，按关键词匹配返回预设数据。

**Windows 注意**：Git Bash 里 `export` 不生效，必须用 `os.environ` 或 subprocess `env=` 参数显式传递。

---

## 项目目录结构

```
workspace/frost-sop/
├── agents/          # elder.py(祖), parent.py(父), (孙辈动态组装)
├── skills/          # llm.py, orchestration.py, assemble.py, evolution.py...
├── core/            # db.py, store.py, cost.py, workbench.py, decision_manager.py, skill_extractor.py, skill_version.py...
├── sops/            # SOP yaml 模板
├── stores/          # 运行时 Store 数据
├── assets/          # 静态资源
├── output/          # SOP 产出
├── tests/           # 27 个测试文件
├── data/            # frost_sop.db + 运行时数据
├── app.py           # Streamlit 驾驶舱（1927行）
├── main.py          # CLI 入口
├── requirements.txt
└── 启动工作台.bat    # 一键启动脚本（GBK编码）
```

---

## 调试建议

1. 启动后主要调试区域在 `render_commander_dashboard()`（L653）和 `inject_css()`（L52）
2. 如需调整 Agent 数据，改 `get_agent_team()`（L594）
3. 成本面板数据来自 `core/cost.py`，渲染在 `render_cost_dashboard()`（L1452）
4. 右侧面板改 `render_command_panel()`（L1214）
5. Streamlit 支持热重载，修改 `app.py` 后保存即刷新
6. 测试前务必 `set FROST_TESTING=1`，避免真实 LLM 扣费
