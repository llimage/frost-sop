# 审计请求：FROST-SOP V2.1（第二轮，首审修复验证）

---

## 致 Kimi Work

**欢迎回来。** 这是 FROST-SOP V2.1 的第二轮审计请求。

首轮审计（2026-06-26）您发现了 **4 P0 + 5 P1** 问题。V2.1 已按审计建议全部修复（详见 `V2.1_AUDIT_UPDATE.md`）。

本次审计重点：
1. **验证修复**：9 项首审问题是否真正解决
2. **扫描新风险**：V2.1 修补是否引入新问题
3. **合并建议**：`feature/v2-event-driven` 是否可以安全合并到 master

---

## 新增核心代码（V2.1 相比 V2.0）

### 安全加固

**敏感数据过滤**（`core/event_bus.py`）：
```python
_SENSITIVE_KEYS = {"api_key", "apikey", "token", "password", "secret",
                    "credential", "private_key", "access_key", "auth"}
def _sanitize_data(data):
    """递归过滤敏感键值 → "[FILTERED]" """
```

**循环事件防护**（`core/event_bus.py`）：
```python
# 跳过同名回调防止循环（排除 lambda）
if (hasattr(callback, '__name__') and callback.__name__ != '<lambda>'
        and callback.__name__ == event.source):
    continue
```

### 数据库修复

**agents 表 UPSERT**（`core/agent.py`）：
```python
# INSERT → INSERT OR REPLACE
conn.execute("INSERT OR REPLACE INTO agents ...")
```

**表结构完整**（`core/db.py`）：
```python
# energy_log/schedule/decision_points 的 CREATE TABLE 直接含所有列
```

### 事件完整性

**TASK_DECOMPOSED 事件**（`main.py`）：
```python
bus.publish(Event(
    event_type=EventType.TASK_DECOMPOSED,
    source="main",
    data={"task_id": task_id, "stage_count": N, "stages": [...]},
))
```

---

## 审计材料清单（V2.1 更新版）

| # | 文件 | 状态 | 用途 |
|---|------|------|------|
| 🆕 1 | `V2.1_AUDIT_UPDATE.md` | **新增** | 二审主文档：首审问题追踪 + 修复详情 |
| 📝 2 | `V2_AUDIT_SUMMARY.md` | 更新 | 审计摘要（含 V2.1 修补清单） |
| 📝 3 | `V2_ARCHITECTURE.md` | 已更新 | 架构设计（含定位声明） |
| 📝 4 | `V2_CODE_CHANGES.md` | 更新 | 代码变更（含 §11 V2.1 修补） |
| 📝 5 | `V2_TEST_REPORT.md` | 更新 | 测试报告（200 passed） |
| 6 | `V2_E2E_EVIDENCE.md` | 不变 | E2E 证据（334 条事件日志） |
| 7 | `V2_DESIGN_DECISIONS.md` | 不变 | 7 个关键设计决策 |
| 📝 8 | `V2_TECHNICAL_DEBT.md` | 更新 | 首审问题追踪表 |
| 9 | `V2_AUDIT_REQUEST.md` | 📝 本文件 | 二审请求单 |
| 📝 10 | `README_FOR_AUDITOR.md` | 更新 | 二审阅读指南 |
| 🆕 外部 | `V2.1_PATCH_REPORT.md` | 项目根目录 | 完整修补报告 |

---

## 二审输出要求

### 1. 修复验证评分

| 首审问题 | 是否修复 | 评分(1-10) | 说明 |
|----------|----------|------------|------|
| P0-1 表结构 | | | |
| P0-2 决策管理 | | | |
| P0-3 真实LLM | | | |
| P0-4 密钥加密 | | | |
| P1-5 架构定位 | | | |
| P1-6 TASK_DECOMPOSED | | | |
| P1-7 敏感数据 | | | |
| P1-8 循环防护 | | | |
| P1-9 UPSERT | | | |

### 2. 新问题扫描

- 是否有 V2.1 修补引入的新 P0/P1 问题？
- `_sanitize_data()` / 循环防护 / INSERT OR REPLACE 是否有副作用？

### 3. 最终结论

- **是否建议合并到 master？**
- **上线风险等级**（低/中/高）
- **是否有遗留问题需要在 V3.0 中解决？**
