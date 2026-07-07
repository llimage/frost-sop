# 初始化任务 SOP

生成时间: 2026-07-07T18:55:49.640265
来源: 初始化问卷自动触发

## 任务清单

⬜ [P0] INIT-HUNT-001: 初始狩猎：技术执行能力
   目标技能: tech_execution
   执行命令: `python main.py --hunt --hunt-target tech_execution`

⬜ [P0] INIT-HUNT-002: 初始狩猎：零预算工具栈
   目标技能: zero_budget_tools
   执行命令: `python main.py --hunt --hunt-target zero_budget_tools`

⬜ [P0] INIT-HUNT-003: 初始狩猎：小红书运营能力
   目标技能: redbook_ops
   执行命令: `python main.py --hunt --hunt-target redbook_ops`

## 执行顺序

1. 按优先级执行（P0 → P1 → P2）
2. 每个任务完成后更新状态
3. 所有 P0 完成后进入常规运营

---

本文件由 InitTaskTrigger 自动生成，请勿手动修改。
