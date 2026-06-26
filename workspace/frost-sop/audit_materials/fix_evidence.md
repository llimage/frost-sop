# 修复证据清单

> 生成日期: 2026-06-24 | 审计标准: 第三方独立审计

---

## P0-2: 父辈自修复重试机制

### 修改文件: `core/agent.py`
### 测试文件: `tests/test_p0_2_retry.py`

#### 关键代码修改
```python
# Agent.__init__ 新增参数
def __init__(self, ..., retry_config=None, on_max_retries=None):
    self.retry_config = retry_config or {"max_retries": 3, "retry_delay": 5}
    self.on_max_retries = on_max_retries

# 新增核心方法
def _execute_step_with_retry(self, context):
    for attempt in range(self.retry_config["max_retries"] + 1):
        result = self._try_execute_step(context)
        if result.success:
            return result
        if attempt < self.retry_config["max_retries"]:
            alt_skill = self._find_alternate_skill(context.current_step)
            if alt_skill:
                context.current_skill = alt_skill
            time.sleep(self.retry_config["retry_delay"])
    # 达到最大重试次数
    if self.on_max_retries:
        self.on_max_retries(self, context.last_error)
    raise MaxRetriesExceededError(...)
```

#### 测试证据
```
tests/test_p0_2_retry.py::test_retry_succeeds_on_third_attempt PASSED
tests/test_p0_2_retry.py::test_max_retries_exceeded_reports_to_elder PASSED
tests/test_p0_2_retry.py::test_alternate_skill_switching PASSED
tests/test_p0_2_retry.py::test_no_retry_on_success PASSED
tests/test_p0_2_retry.py::test_multiple_agents_with_retry PASSED
tests/test_p0_2_retry.py::test_parent_runs_child_agent_with_retry PASSED
tests/test_p0_2_retry.py::TestRetryLogging::test_retry_records_in_history PASSED
tests/test_p0_2_retry.py::test_timing_between_retries PASSED
```

---

## P0-4: F8 决策管理逻辑回归

### 修改文件: `core/decision_manager.py`, `skills/orchestration.py`
### 测试文件: `tests/test_f8_decision.py`

#### 关键修改
```python
# decision_manager.py: 返回类型从 str 改为 int
def pause_decision(self, task_id, ...) -> int:  # was: str
    if task_id == 'unknown':
        raise ValueError("拒绝 task_id='unknown'")
    ...

def resume_decision(self, decision_id: Union[int, str], ...):
    ...

# orchestration.py: execute_stage() 跳过无效 task_id
if task_id and task_id != 'unknown':
    dm.pause_decision(task_id=task_id, ...)
```

#### 数据清理证据
- 清理前: `decision_points` 表 55 行，5 行 `task_id='unknown'` + `status='pending'`
- 清理后: 无无效决策点
- 迁移记录已写入 `audit_log` 表

#### 测试证据
```
tests/test_f8_decision.py: 6 passed
```

---

## P0-5: API Key 加密存储

### 修改文件: `core/secrets.py` (新建), `skills/llm.py`
### 测试文件: `tests/test_p0_5_encryption.py`

#### 关键架构
```
加密流程:
  API_KEY (明文) → AES-256-GCM → ciphertext (密文)
  Machine Key = PBKDF2HMAC(hostname + user_dir + computername)
  Encrypted Key → PBKDF2HMAC(Machine Key) → AES Key

解密流程:
  ciphertext → AES-256-GCM → API_KEY (明文)
  先查内存缓存 → 再查加密文件 → 环境变量 → 提示用户输入
```

#### 测试证据
```
tests/test_p0_5_encryption.py::test_encrypt_decrypt_roundtrip PASSED
tests/test_p0_5_encryption.py::test_different_ciphertexts PASSED
tests/test_p0_5_encryption.py::test_ciphertext_does_not_contain_plaintext PASSED
tests/test_p0_5_encryption.py::test_tampered_ciphertext_fails PASSED
tests/test_p0_5_encryption.py::test_machine_key_consistent PASSED
tests/test_p0_5_encryption.py::test_derived_key_length PASSED
```

---

## P1-7: 意图解析结构化 JSON

### 修改文件: `skills/intent.py` (新建)
### 测试文件: `tests/test_p1_7_intent.py`

#### 关键修复
```python
# 修复前: 置信度计算不准确
# "开发登录功能" → score=1 (仅 "开发" 因 len<=2 得1分) → confidence=0.1

# 修复1: 权重条件改为 >= 2
if len(kw_lower) >= 2:  # was: > 2

# 修复2: 置信度分母从 10 改为 5
confidence = min(best_score / 5.0, 1.0)  # was: / 10.0

# 修复后: "开发登录功能" → score=3 → confidence=0.6 ✓
```

#### 测试证据
```
tests/test_p1_7_intent.py::test_parse_dev_task PASSED
tests/test_p1_7_intent.py::test_parse_dev_alternative_phrasing PASSED
tests/test_p1_7_intent.py::test_parse_bug_fix PASSED
tests/test_p1_7_intent.py::test_parse_content_marketing PASSED
tests/test_p1_7_intent.py::test_parse_finance PASSED
tests/test_p1_7_intent.py::test_parse_knowledge PASSED
tests/test_p1_7_intent.py::test_parse_project_init PASSED
tests/test_p1_7_intent.py::test_parse_unknown_type PASSED
tests/test_p1_7_intent.py::test_parse_multi_keyword PASSED
tests/test_p1_7_intent.py::test_all_sops_listed PASSED
```

---

## P1-1/P1-2/P1-3: Streamlit 前端修复

### 修改文件: `app.py`

#### P1-1 导航栏
```python
# 修复前: 静态 HTML span
nav_html += f'<span class="{cls}">{nlabel}</span>'

# 修复后: 可交互 Streamlit 按钮
for i, (nid, nlabel) in enumerate(nav_items):
    if st.button(nlabel, key=f"navbtn_{nid}", type=btn_type, ...):
        st.session_state.wb_nav = nid
        st.rerun()
```

#### P1-2 CEO 对话
```python
# 新增 _call_ceo_llm() 函数
def _call_ceo_llm(user_message: str) -> str:
    if os.getenv("FROST_TESTING") == "1":
        return _mock_ceo_response(user_message)
    # 真实调用 DeepSeek API
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(...)
    return response.choices[0].message.content
```

#### P1-3 Agent 卡片
```python
# 修复前: 纯 HTML div
grid_html += f'<div class="saas-agent-card">...</div>'

# 修复后: Streamlit expander + 按钮
with st.expander(f"{status_icon} {ag['name']} — {status_label}"):
    st.caption(f"**角色**: {ag['role']}")
    # ... 详情渲染
    if st.button("▶ 唤醒", ...):  add_log(...)
```

---

## 验证方法

所有修复的证据可在以下位置验证：

1. **代码审查**: 查看对应文件的 git diff
2. **测试执行**: `FROST_TESTING=1 python -m pytest tests/ -v`
3. **SOP 真实执行**: `FROST_TESTING=0 python -c "..."` 执行 DEV-001
4. **导航栏**: 启动 `streamlit run app.py`，点击各导航按钮
5. **CEO 对话**: 在 Streamlit 界面输入消息，观察 LLM 回复
