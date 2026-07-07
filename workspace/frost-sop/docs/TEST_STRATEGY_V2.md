# FROST-SOP 测试策略 V2.0

> **从"测了这么多还有Bug"到"系统化防止Bug"**

**版本**: V2.0
**日期**: 2026-07-04
**作者**: 合伙人
**状态**: 生效中

---

## 📖 背景

### 事件回顾

**2026-07-04**，我们发现了一个Bug：
- **现象**: 创建任务时，如果 `data/assets.json` 为空文件，系统崩溃
- **错误**: `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
- **根因**: `stores/asset.py` 的 `FileStore.__init__()` 未检查空文件

**矛盾点**：
- 测试数量：124个
- 核心覆盖率：94.55%
- **但还是有Bug**

### 问题分析

**为什么测了这么多还有Bug？**

1. **覆盖率 ≠ 质量**
   - 94.55%覆盖率 = 代码被执行过
   - 但执行的都是"快乐路径"（正常场景）
   - 空文件、损坏JSON等"异常路径"没被测试

2. **测试环境的理想化**
   - 测试时文件总是包含有效JSON
   - 真实环境中文件可能为空、损坏、部分写入

3. **假设的漏洞**
   - 代码假设"文件存在 = 文件有效"
   - 但这个假设没被验证

4. **集成测试的缺失**
   - 单个模块都测试了
   - 但模块组合起来没测试

---

## 🎯 新测试策略

### 核心原则

**不仅测试"它能工作"，还要测试"它怎么失败"**

### 三大测试类型

```
测试策略 V2.0
├── 1. 快乐路径测试（Happy Path）
│   └── 验证：正常场景下功能正确
│
├── 2. 异常路径测试（Exception Path）  ← 新增重点
│   └── 验证：异常场景下系统不崩溃
│
└── 3. 崩溃恢复测试（Crash Recovery）  ← 新增重点
    └── 验证：进程崩溃后数据不丢失
```

---

## 1️⃣ 快乐路径测试（Happy Path）

### 目标
验证功能在正常输入下正确工作。

### 覆盖范围
- ✅ 有效输入
- ✅ 正常流程
- ✅ 预期输出

### 示例

```python
def test_create_task_with_valid_input(self):
    """测试：使用有效输入创建任务"""
    req = TaskCreateRequest(
        description="有效任务描述",
        sop_id="DEV-001",
        project_id="default"
    )

    result = create_and_run_task(req)

    self.assertEqual(result.status, "completed")
    self.assertGreater(len(result.stages), 0)
```

### 当前状态
- ✅ 已覆盖（124个测试）
- ⚠️ 但不够，需要补充异常路径

---

## 2️⃣ 异常路径测试（Exception Path）

### 目标
**验证系统在异常输入下不崩溃，优雅处理错误。**

### 覆盖范围

#### 2.1 边界条件
- 空字符串
- 空文件
- 最大值/最小值
- None值

#### 2.2 格式错误
- 无效JSON
- 无效XML
- 无效日期格式
- 编码错误

#### 2.3 资源限制
- 文件不存在
- 无权限
- 磁盘满
- 内存不足

#### 2.4 网络故障
- 超时
- 连接断开
- API返回错误

### 示例

```python
def test_filestore_empty_file(self):
    """异常路径：文件存在但是空的"""
    # 创建空文件
    with open(self.test_file, 'w') as f:
        pass  # 空文件

    # 应该不崩溃
    store = FileStore(self.test_file)

    # 应该返回空字典
    self.assertEqual(store._memory, {})

def test_filestore_corrupted_json(self):
    """异常路径：文件包含无效JSON"""
    with open(self.test_file, 'w') as f:
        f.write("{invalid json}")

    # 应该不崩溃
    store = FileStore(self.test_file)

    # 应该返回空字典
    self.assertEqual(store._memory, {})
```

### 实施指南

**每个public函数，都要测试：**
1. 输入为None
2. 输入为空字符串
3. 输入为无效格式
4. 输入为边界值

**每个文件操作，都要测试：**
1. 文件不存在
2. 文件为空
3. 文件损坏
4. 无读取权限

**每个网络调用，都要测试：**
1. 超时
2. 连接失败
3. 返回500错误
4. 返回格式错误

---

## 3️⃣ 崩溃恢复测试（Crash Recovery）

### 目标
**验证进程崩溃后，数据完整性和可恢复性。**

### 覆盖范围

#### 3.1 数据持久化
- 任务执行到一半崩溃 → 重启后能恢复
- 文件写入到一半崩溃 → 文件不损坏

#### 3.2 状态一致性
- 数据库事务回滚
- 文件原子写入

#### 3.3 重启恢复
- 从检查点恢复
- 重新执行未完成任务

### 示例

```python
def test_crash_during_file_write(self):
    """崩溃恢复：文件写入中途崩溃"""
    store = FileStore(self.test_file)

    # 模拟写入中途崩溃（使用mock）
    with patch('json.dump', side_effect=KeyboardInterrupt):
        try:
            store.save("key", "value")
        except KeyboardInterrupt:
            pass

    # 验证：文件要么完整，要么不存在（不应该是损坏状态）
    if os.path.exists(self.test_file):
        with open(self.test_file) as f:
            data = json.load(f)  # 应该能正常解析
            self.assertEqual(data["key"], "value")
```

### 实施指南

**关键操作必须使用原子写入：**
```python
# ✅ 正确：原子写入
temp_file = filepath + ".tmp"
with open(temp_file, 'w') as f:
    json.dump(data, f)
os.replace(temp_file, filepath)  # 原子操作

# ❌ 错误：直接写入
with open(filepath, 'w') as f:
    json.dump(data, f)  # 写入中途崩溃 → 文件损坏
```

**数据库操作必须使用事务：**
```python
# ✅ 正确：使用事务
conn = get_db_connection()
try:
    conn.execute("BEGIN")
    conn.execute("INSERT ...")
    conn.execute("UPDATE ...")
    conn.commit()
except:
    conn.rollback()
    raise
```

---

## 🛠️ 实施计划

### 阶段1：补充异常路径测试（本周）

**任务**：
1. ✅ 已完成：`test_filestore_boundary.py`（8个测试）
2. 待完成：为所有文件操作添加异常路径测试
3. 待完成：为所有JSON解析添加异常路径测试
4. 待完成：为所有LLM调用添加异常路径测试

**覆盖模块**：
- `stores/asset.py` ✅
- `core/db.py`
- `skills/llm.py`
- `api/main.py`

### 阶段2：添加集成测试（本周）

**任务**：
1. ✅ 已完成：`test_integration_full_flow.py`（7个测试）
2. 待完成：添加更多SOP模板的集成测试
3. 待完成：添加错误场景的集成测试

### 阶段3：实施崩溃恢复测试（下周）

**任务**：
1. 为所有文件写入添加原子写入
2. 为所有数据库操作添加事务
3. 创建崩溃恢复测试用例

### 阶段4：混沌工程（下下周）

**任务**：
1. 模拟文件系统故障
2. 模拟网络中断
3. 模拟进程崩溃

---

## 📊 测试覆盖率目标

| 测试类型 | 当前覆盖 | 目标覆盖 |
|---------|---------|---------|
| 快乐路径 | 90% | 95% |
| 异常路径 | 10% | 80% |
| 崩溃恢复 | 0% | 70% |
| 集成测试 | 20% | 90% |

---

## ✅ 测试检查清单

### 写测试前
- [ ] 这个函数有哪些输入？
- [ ] 每个输入的可能异常值是什么？
- [ ] 外部依赖可能怎么失败？

### 写测试时
- [ ] 不仅测试快乐路径，还测试异常路径
- [ ] 不仅测试输出正确，还测试错误信息清晰
- [ ] 不仅测试正常流程，还测试中断恢复

### 测试完成后
- [ ] 运行测试：`python -m pytest tests/ -v`
- [ ] 检查覆盖率：`python -m pytest --cov=core --cov=stores`
- [ ] 思考：还有什么场景没测到？

---

## 💡 最佳实践

### 1. 测试应该是确定性的
- 不使用当前时间作为预期值
- 不使用随机值
- 不依赖测试执行顺序

### 2. 测试应该快速
- 单元测试 < 1秒
- 集成测试 < 10秒
- 慢测试标记为 `@pytest.mark.slow`

### 3. 测试应该独立
- 不依赖外部服务（使用mock）
- 不依赖数据库状态（每次重建）
- 不依赖文件系统中的现有文件

### 4. 测试应该可读
- 测试名称清晰：`test_filestore_empty_file`
- 测试结构清晰：Arrange-Act-Assert
- 断言消息清晰：`assert result.status == "completed", f"期望completed，实际{result.status}"`

---

## 📝 附录：Good Test vs Bad Test

### ❌ Bad Test

```python
def test_create_task(self):
    """不好的测试"""
    result = create_task("test")
    assert result is not None  # 太模糊
```

### ✅ Good Test

```python
def test_create_task_with_valid_input(self):
    """好的测试：明确、完整、可读"""
    # Arrange
    req = TaskCreateRequest(
        description="测试任务",
        sop_id="DEV-001",
        project_id="default"
    )

    # Act
    result = create_and_run_task(req)

    # Assert
    self.assertEqual(result.status, "completed",
                   "任务应该成功完成")
    self.assertGreater(len(result.stages), 0,
                      "应该至少有一个阶段")
    self.assertIn("完成", result.message,
                 "消息应该包含'完成'")
```

---

## 🎓 总结

**从这次Bug学到的：**

1. **覆盖率 ≠ 质量**
   - 要覆盖"异常路径"，不只是"快乐路径"

2. **测试要模拟现实**
   - 现实中有空文件、损坏数据
   - 测试中要模拟这些场景

3. **假设必须验证**
   - 代码中的每个假设都要测试
   - "文件存在 = 文件有效" 是错误的假设

4. **防御性编程**
   - 不信任任何外部输入
   - 为失败做好准备

**新的测试策略：**
- ✅ 快乐路径（功能正确）
- ✅ 异常路径（优雅失败）
- ✅ 崩溃恢复（数据安全）

**目标**：
> 让FROST-SOP在真实世界的残酷环境下依然可靠
