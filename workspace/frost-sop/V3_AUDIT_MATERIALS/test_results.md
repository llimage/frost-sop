# V3.0 测试明细

> 生成日期：2026-06-26 | 运行环境：Python 3.13.12, pytest 9.0.3, pytest-asyncio 1.4.0

---

## V3.0 专项测试（36/36 passed）

### test_v3_async_event_bus.py（12 passed）

| # | 测试名 | 覆盖点 |
|---|--------|--------|
| 01 | test_01_async_bus_not_subclass_of_sync_bus | AsyncEventBus 不继承 EventBus |
| 02 | test_02_async_bus_singleton | 单例模式 |
| 03 | test_03_get_async_event_bus_returns_singleton | get_async_event_bus 返回同一实例 |
| 04 | test_04_sync_and_async_subscribers_coexist | 同步/异步订阅者共存 |
| 05 | test_05_subscribe_async_registers_async_callback | subscribe_async 注册异步回调 |
| 06 | test_06_publish_returns_notified_count | publish 返回通知数量 |
| 07 | test_07_circular_event_protection | 循环事件防护 |
| 08 | test_08_subscriber_exception_isolation | 订阅者异常隔离 |
| 09 | test_09_task_timeout_event_type_exists | TASK_TIMEOUT 事件类型存在 |
| 10 | test_10_get_event_log_async | 异步获取事件日志 |
| 11 | test_11_sanitize_data | 敏感数据过滤 |
| 12 | test_12_unsubscribe | 取消订阅 |

### test_v3_ancestor_subscribe.py（5 passed）

| # | 测试名 | 覆盖点 |
|---|--------|--------|
| 01 | test_01_ancestor_v2_mode_no_subscription | V2 模式不订阅事件 |
| 02 | test_02_ancestor_v3_mode_subscribes_task_created | V3 模式订阅 TASK_CREATED |
| 03 | test_03_ancestor_publishes_task_decomposed | 分解后发布 TASK_DECOMPOSED |
| 04 | test_04_decomposition_contains_llm_response | 分解结果包含 LLM 响应 |
| 05 | test_05_ancestor_v2_mode_still_works | V2 模式 ancestor.run() 仍正常 |

### test_v3_parent_subscribe.py（8 passed）

| # | 测试名 | 覆盖点 |
|---|--------|--------|
| 01 | test_01_parent_v2_mode_no_subscription | V2 模式不订阅事件 |
| 02 | test_02_parent_v3_mode_subscribes_task_decomposed | V3 模式订阅 TASK_DECOMPOSED |
| 03 | test_03_parent_publishes_stage_events | 发布 STAGE_STARTED/COMPLETED |
| 04 | test_04_parent_publishes_task_completed | 全部阶段完成后发布 TASK_COMPLETED |
| 05 | test_05_stage_started_contains_stage_info | STAGE_STARTED 包含阶段信息 |
| 06 | test_06_sop_load_failure_publishes_task_failed | SOP 加载失败发布 TASK_FAILED |
| 07 | test_07_v2_mode_no_side_effects | V2 模式无副作用 |
| 08 | test_08_v2_mode_parent_run_works | V2 模式 parent.run() 仍正常 |

### test_v3_execute_stage_subscribe.py（6 passed）

| # | 测试名 | 覆盖点 |
|---|--------|--------|
| 01 | test_01_register_subscribes_to_stage_started | register 注册 STAGE_STARTED 订阅 |
| 02 | test_02_stage_started_triggers_stage_completed | STAGE_STARTED 触发 STAGE_COMPLETED |
| 03 | test_03_stage_completed_contains_status | STAGE_COMPLETED 包含状态字段 |
| 04 | test_04_no_subscription_without_register | 未 register 时不订阅 |
| 05 | test_05_multiple_stages_sequential | 多阶段顺序执行 |
| 06 | test_06_register_returns_true | register 返回 True |

### test_v3_main_async.py（5 passed）

| # | 测试名 | 覆盖点 |
|---|--------|--------|
| 01 | test_01_main_async_publishes_task_created | main_async 发布 TASK_CREATED |
| 02 | test_02_main_async_returns_on_completion | 任务完成后返回 |
| 03 | test_03_main_async_supports_timeout | 支持 timeout 参数 |
| 04 | test_04_timeout_publishes_task_timeout | 超时发布 TASK_TIMEOUT（非 TASK_FAILED） |
| 05 | test_05_main_sync_still_exists | V2.0 main() 同步入口保留 |

---

## 全量回归（250 passed, 1 error）

运行命令：
```bash
python -m pytest tests/ -v --asyncio-mode=auto -s --tb=short
```

结果：
```
250 passed, 61 warnings, 1 error in 95.44s
```

### 回归分解

| 类别 | 测试数 | 状态 |
|------|--------|------|
| V2.0 基线测试 | 214 | ✅ 全部通过 |
| V3.0 新增测试 | 36 | ✅ 全部通过 |
| test_f16_api.py | 1 | ⚠️ error（预存，非 V3.0 引入） |
| **合计** | **251** | **250 passed** |

### 预存 error 说明

- **文件：** `tests/test_f16_api.py`
- **原因：** 函数 `def test(name, method="GET", ...)` 被 pytest 误认为需要 `name` fixture
- **实际状态：** 函数内部手动运行 12 项 API 测试，全部通过（12 passed / 0 failed）
- **与 V3.0 关系：** 无关，V2.0 基线已存在此问题

---

## 测试运行环境

| 项目 | 版本 |
|------|------|
| Python | 3.13.12 |
| pytest | 9.0.3 |
| pytest-asyncio | 1.4.0 |
| asyncio mode | auto |
| FROST_TESTING | 1（mock 模式） |
| OS | Windows (win32) |
