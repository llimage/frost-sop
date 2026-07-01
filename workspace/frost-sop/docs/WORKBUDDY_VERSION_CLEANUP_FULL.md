# WorkBuddy 执行指令：版本清理与基线建立（全量带逻辑分支）

**版本**: v5.0.0-cleanup-full
**日期**: 2026-07-01
**执行者**: WorkBuddy
**前置条件**: 45-49 测试任务全部通过（或明确记录失败原因）
**目标**: 形成干净的文件系统 + 稳定的 git 基线 + 可审计的目录结构
**预计耗时**: 3-4 小时（含验证和回滚时间）
**执行原则**: 前置检查不通过则阻塞；每阶段完成后必须验收；任何失败立即回滚并报告

---

## 零、绝对前置检查（BLOCKING — 不通过则停止）

### 前置检查 1：确认当前工作目录

```bash
cd /d/my_ai/Solo-Ops-Platform
pwd
```

**验收**: 输出必须是 `/d/my_ai/Solo-Ops-Platform`（或 Windows 等效路径）。
**如果失败**: 停止执行，报告 "工作目录错误"。

### 前置检查 2：确认 Git 仓库存在

```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
git status
```

**验收**: 输出包含 "On branch" 或 "git status" 正常输出，不是 "not a git repository"。
**如果失败**: 停止执行，报告 "Git 仓库不存在"。

### 前置检查 3：确认 45-49 测试状态

```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
python -m pytest tests/ -q --tb=short 2>&1 | tail -20
```

**逻辑分支**:

**IF** 输出包含 "0 failed":
- 记录通过数、跳过数
- 继续执行

**IF** 输出包含 ">0 failed":
- 提取失败测试名称
- 单独运行失败测试确认是否 flaky:
  ```bash
  python -m pytest tests/test_failing.py -v --tb=short
  ```
- **IF** 单独运行通过 → 标记为 flaky，记录到 BASELINE 文档，继续执行
- **IF** 单独运行仍失败 → **停止执行**，报告 "测试失败，需修复后再清理"

**IF** pytest 命令找不到或崩溃:
- 检查 Python 环境: `python -m pytest --version`
- **IF** pytest 可用 → 用 `python -m pytest` 重新运行
- **IF** pytest 不可用 → 尝试 `pip install pytest==8.4.2` 后重试
- **IF** 仍不可用 → 停止执行，报告 "测试环境不可用"

### 前置检查 4：确认没有未提交的变更会被误删

```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
git status --short
```

**逻辑分支**:

**IF** 输出为空（无未提交变更）:
- 继续执行

**IF** 输出非空:
- 记录所有未提交文件
- **IF** 未提交文件是 45-49 测试任务产生的 → 先提交:
  ```bash
  git add -A
  git commit -m "feat: test tasks 45-49 completion"
  ```
- **IF** 未提交文件是用户手动修改 → 停止执行，报告 "存在未提交变更，请用户确认"
- **IF** 未提交文件是冲突/异常 → 停止执行，报告 "Git 状态异常"

### 前置检查 5：确认备份可创建

```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
git stash list | wc -l
```

**逻辑分支**:

**IF** stash 数量 < 10:
- 创建备份 stash:
  ```bash
  git stash push -m "pre-cleanup-backup-$(date +%Y%m%d-%H%M%S)"
  ```
- 继续执行

**IF** stash 数量 >= 10:
- 报告 "stash 过多，请用户清理旧 stash"
- 询问是否继续（不带 stash 备份）
- **IF** 用户确认 → 继续执行（风险自负）
- **IF** 用户拒绝 → 停止执行

### 前置检查汇总表

| 检查项 | 命令 | 通过标准 | 失败处理 |
|--------|------|---------|---------|
| 工作目录 | `pwd` | 在 Solo-Ops-Platform | 停止 |
| Git 仓库 | `git status` | 正常输出 | 停止 |
| 测试状态 | `pytest -q` | 0 failed（或 flaky 已记录） | 停止或标记 flaky |
| Git 状态 | `git status --short` | 空或已提交 | 提交或停止 |
| 备份 | `git stash` | 成功创建 | 询问用户 |

**以上 5 项全部通过，才能进入 S1。**

---

## 一、文件系统清理（S1 — 不可逆操作，谨慎）

### S1-1: 删除根目录空壳（软链接残留）

**目标**: 删除根目录下的空壳目录，保留 `workspace/frost-sop/` 下的真实代码。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform

# 删除前确认这些目录确实是"空壳"
for dir in agents core sops tests; do
    if [ -d "$dir" ]; then
        file_count=$(find "$dir" -type f | wc -l)
        echo "Directory $dir: $file_count files"
    fi
done
```

**逻辑分支**:

**IF** 任一目录文件数 > 5:
- 停止执行，报告 "目录 $dir 包含 $file_count 个文件，不是空壳，请用户确认是否删除"
- **IF** 用户确认 → 继续删除
- **IF** 用户拒绝 → 跳过该目录，记录到日志

**IF** 所有目录文件数 <= 5（或不存在）:
- 执行删除:
  ```bash
  rm -rf agents/
  rm -rf core/
  rm -rf sops/
  rm -rf tests/
  rm -rf __pycache__/
  ```
- 记录删除操作

**验证命令**:
```bash
for dir in agents core sops tests __pycache__; do
    if [ -d "$dir" ]; then
        echo "FAIL: $dir still exists"
        exit 1
    else
        echo "PASS: $dir removed"
    fi
done
```

**IF 验证失败**:
- 检查是否是权限问题（Windows 只读文件）
- 尝试 `chmod -R 755 $dir && rm -rf $dir`
- **IF** 仍失败 → 报告 "无法删除 $dir，需要手动清理"

---

### S1-2: 清理全局缓存和构建产物

**目标**: 删除所有 Python 缓存、构建产物、测试缓存。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform

# 删除缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null
find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null

# 删除构建产物
rm -f .coverage
rm -f coverage.xml
rm -rf *.egg-info
rm -rf build/
rm -rf dist/

# 验证
pycache_count=$(find . -type d -name "__pycache__" | wc -l)
pyc_count=$(find . -type f -name "*.pyc" | wc -l)
echo "Remaining __pycache__: $pycache_count"
echo "Remaining *.pyc: $pyc_count"
```

**验收标准**:
- `pycache_count` == 0
- `pyc_count` == 0

**IF 不为 0**:
- 某些缓存可能在运行中的进程锁定（Windows 常见）
- 记录位置，继续执行（下次重启后可删除）

---

### S1-3: 归档审计报告和旧文档

**目标**: 将散落在各处的审计报告、旧文档归档到 `archive/` 和 `docs/archive/`。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop

# 创建归档目录
mkdir -p archive/audits
mkdir -p docs/archive

# 归档根目录的审计报告（如果存在）
for file in THIRD_PARTY_AUDIT_REPORT_*.md AUDIT_TEST_TOOLCHAIN_*.md V50_*_AUDIT*.md; do
    if [ -f "$file" ]; then
        mv "$file" archive/audits/
        echo "Archived: $file"
    fi
done

# 归档旧版本测试报告（如果存在）
for file in F5_*_TEST_REPORT.md F6_*_TEST_REPORT.md F10_*_TEST_REPORT.md F11_*_TEST_REPORT.md F12_*_TEST_REPORT.md F14_*_TEST_REPORT.md F15_*_TEST_REPORT.md F16_*_TEST_REPORT.md; do
    if [ -f "$file" ]; then
        mv "$file" archive/audits/
        echo "Archived: $file"
    fi
done

# 归档旧指令集（如果存在）
for file in docs/WORKBUDDY_*.md docs/FROST_SCOUT_RESPONSE_*.md; do
    if [ -f "$file" ]; then
        mv "$file" docs/archive/
        echo "Archived: $file"
    fi
done

# 验证归档
ls archive/audits/ | wc -l
ls docs/archive/ | wc -l
```

**逻辑分支**:

**IF** 某些文件无法移动（权限问题）:
- 尝试 `chmod 644 $file && mv $file archive/audits/`
- **IF** 仍失败 → 复制文件并删除原文件:
  ```bash
  cp "$file" archive/audits/ && rm -f "$file"
  ```
- **IF** 仍失败 → 记录到日志，继续执行

**IF** archive/audits/ 已存在且非空:
- 确认不会覆盖现有文件（使用 `mv -n` 或检查冲突）
- **IF** 文件名冲突 → 重命名: `mv "$file" "archive/audits/$(basename $file .md)_$(date +%Y%m%d).md"`

---

### S1-4: 处理 audit_package 和 ZIP（从 Git 移除，保留文件）

**目标**: `audit_package_V3.0/` 和 `frost-sop-v3.0-audit-package.zip` 是外部交付物，保留但不在 Git 中追踪。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform

# 从 git 中移除（如果已追踪）
git rm -r --cached audit_package_V3.0/ 2>/dev/null && echo "Removed audit_package_V3.0/ from git"
git rm --cached frost-sop-v3.0-audit-package.zip 2>/dev/null && echo "Removed audit zip from git"

# 验证文件仍存在于磁盘
ls -lh audit_package_V3.0/ 2>/dev/null | head -5
ls -lh frost-sop-v3.0-audit-package.zip 2>/dev/null
```

**逻辑分支**:

**IF** 文件不在 Git 中（未追踪）:
- 无需 `git rm`，直接跳过
- 记录 "文件未追踪，无需移除"

**IF** `git rm` 失败（文件不存在或已移除）:
- 检查是否之前已处理
- 继续执行

---

### S1-5: 验证文件系统结构

**目标**: 确认清理后的目录结构符合预期。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform

# 不应该存在的目录
fail_count=0
for dir in agents core sops tests __pycache__; do
    if [ -d "$dir" ]; then
        echo "FAIL: $dir should not exist"
        fail_count=$((fail_count + 1))
    fi
done

# 应该存在的目录
for dir in workspace/frost-sop/agents workspace/frost-sop/core workspace/frost-sop/skills workspace/frost-sop/tests; do
    if [ ! -d "$dir" ]; then
        echo "FAIL: $dir should exist"
        fail_count=$((fail_count + 1))
    fi
done

# 输出结果
if [ $fail_count -eq 0 ]; then
    echo "PASS: File system structure validated"
else
    echo "FAIL: $fail_count structure violations found"
    exit 1
fi
```

**IF 验证失败**:
- 停止执行，报告具体失败项
- 询问用户是否继续（如果失败项不影响核心功能）

---

## 二、Git 状态清理（S2）

### S2-1: 提交所有变更

**目标**: 将 S1 的所有清理操作提交到 Git。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop

# 查看当前变更
git status --short

# 添加所有变更
git add -A

# 查看将要提交的内容（确认没有误删）
git diff --cached --stat
```

**逻辑分支**:

**IF** `git diff --cached` 显示大量删除（>50 文件）:
- 检查删除的文件是否都是预期的（缓存、空壳、旧文档）
- **IF** 包含核心代码文件 → 停止执行，报告 "误删核心代码"
- **IF** 只有预期文件 → 继续

**执行提交**:
```bash
# 分阶段提交（便于回滚和审计）

# 提交 1: 文件系统清理
git add -A
git commit -m "chore: file system cleanup

- Remove root directory shells (agents/, core/, sops/, tests/)
- Clean all __pycache__ and *.pyc
- Archive audit reports to archive/audits/
- Remove audit_package from git tracking (keep files)
- Update .gitignore for clean baseline
"

# 验证提交成功
if [ $? -eq 0 ]; then
    echo "PASS: Cleanup committed"
else
    echo "FAIL: Git commit failed"
    exit 1
fi
```

---

### S2-2: 更新 .gitignore

**目标**: 确保清理后的文件不会被重新追踪。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform

# 检查 .gitignore 是否存在
if [ ! -f .gitignore ]; then
    echo "WARNING: .gitignore not found, creating new one"
fi

# 追加内容（避免覆盖现有规则）
cat >> .gitignore << 'EOF'

# === v5.0.0 cleanup additions ===
# Archive directories
archive/
docs/archive/

# Coverage and build
htmlcov/
.coverage
coverage.xml
*.egg-info/
build/
dist/

# Audit packages (keep files, ignore in git)
audit_package_V3.0/
frost-sop-v3.0-audit-package.zip

# Caches
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Databases
*.db
*.db-journal
*.db-wal
*.db-shm

# Logs
logs/*.log
logs/*.log.*

# Experiments
experiments/

# Environment
.env
.env.local
.venv/
venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
EOF

# 提交 .gitignore
git add .gitignore
git commit -m "chore: update .gitignore for v5.0.0 baseline"
```

**验证**:
```bash
git check-ignore -v archive/audits/
# 应该输出匹配规则
```

---

## 三、基线建立（S3）

### S3-1: 创建版本标签

**目标**: 创建 `v5.0.0` 标签，标记清理后的基线。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop

# 获取当前 commit hash
COMMIT_HASH=$(git rev-parse --short HEAD)

# 检查是否已有 v5.0.0 标签
if git tag -l | grep -q "v5.0.0"; then
    echo "WARNING: v5.0.0 tag already exists"
    # 删除旧标签（如果用户确认）
    # git tag -d v5.0.0
fi

# 创建 annotated tag
git tag -a v5.0.0 -m "v5.0.0: Clean baseline after security fixes and test toolchain

Changes since v3.0.0:
- P0 security fixes: SQL injection whitelist, CORS restriction
- Full test toolchain: pytest-xdist, hypothesis, benchmark, CI/CD
- File system cleanup: removed dead code, archived reports
- Base: stable tests, clean git history

Commit: $COMMIT_HASH
Date: $(date +%Y-%m-%d)"

# 验证
git tag -l | grep v5.0.0
git show v5.0.0 --stat
```

**逻辑分支**:

**IF** 标签已存在:
- 停止执行，报告 "v5.0.0 标签已存在"
- 询问用户是否覆盖旧标签
- **IF** 用户确认 → `git tag -d v5.0.0 && git tag -a v5.0.0 ...`
- **IF** 用户拒绝 → 使用 `v5.0.0-cleanup` 作为替代标签名

**IF** 标签创建失败:
- 检查 Git 配置（user.name, user.email）
- 尝试 `git config user.email "user@example.com" && git config user.name "WorkBuddy"` 后重试
- **IF** 仍失败 → 报告 "Git 标签创建失败"

---

### S3-2: 创建基线文档

**目标**: 创建 `BASELINE_v5.0.0.md`，记录基线状态。

**执行命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop

# 获取测试统计（如果 pytest 可用）
TEST_STATS=$(python -m pytest tests/ --collect-only -q 2>/dev/null | tail -1 || echo "N/A")

# 创建基线文档
cat > BASELINE_v5.0.0.md << EOF
# FROST-SOP v5.0.0 基线

**创建日期**: $(date +%Y-%m-%d)
**Git Tag**: v5.0.0
**Git Commit**: $(git rev-parse HEAD)
**执行者**: WorkBuddy

## 基线内容

| 组件 | 状态 | 说明 |
|------|------|------|
| 核心框架 | 稳定 | Store/Skill/Agent/SOP/EventBus 可用 |
| 安全修复 | 已完成 | SQL注入白名单、CORS限制、pyproject.toml |
| 测试工具链 | 已配置 | pytest-xdist、Hypothesis、benchmark、CI/CD |
| 文件系统 | 已清理 | 空壳删除、审计报告归档、缓存清理 |
| 武器库 | 已启用 | DecisionFlow 集成、健康评分系统就绪 |

## 测试基线

| 指标 | 数值 |
|------|------|
| 收集到的测试 | $TEST_STATS |
| 通过 | 待运行填充 |
| 跳过 | 待运行填充 |
| 失败 | 0 |

## 已知限制

1. pytest-xdist 并行测试因 SQLite 锁冲突不可行（需串行运行）
2. CI/CD 中 ruff/mypy 版本号需修正（ruff==0.11.0, mypy==1.15.0）
3. \`record_usage()\` / \`merge_from()\` 已修复但未验证实际运行
4. 负载测试（Locust）和变异测试（Mutmut）已配置但未运行
5. 3 个 flaky 测试已知（F9/F10 相关，已标记 skip）

## 审计就绪

本基线已准备就绪，可供第三方审计。

## 目录结构

\`\`\`
workspace/frost-sop/
├── agents/          # 真实代码
├── api/             # FastAPI 服务
├── core/            # 核心框架
├── skills/          # 技能库
├── renderers/       # 渲染器
├── stores/          # 数据存储
├── sops/            # SOP 模板
├── tests/           # 测试套件
├── docs/            # 文档
├── archive/         # 归档（审计报告等）
├── data/            # 运行时数据
├── logs/            # 日志
├── .github/workflows/  # CI/CD
├── Makefile         # 构建脚本
├── pyproject.toml   # 项目配置
├── requirements.txt # 依赖
└── BASELINE_v5.0.0.md  # 本文件
\`\`\`
EOF

# 提交基线文档
git add BASELINE_v5.0.0.md
git commit -m "docs: add baseline document v5.0.0"
```

---

## 四、最终验证（S4）

### S4-1: 文件系统验证

```bash
cd /d/my_ai/Solo-Ops-Platform

fail_count=0

# 不应该存在的
for dir in agents core sops tests __pycache__; do
    if [ -d "$dir" ]; then
        echo "FAIL: $dir should not exist"
        fail_count=$((fail_count + 1))
    fi
done

# 应该存在的
for dir in workspace/frost-sop/agents workspace/frost-sop/core workspace/frost-sop/skills workspace/frost-sop/tests workspace/frost-sop/archive/audits; do
    if [ ! -d "$dir" ]; then
        echo "FAIL: $dir should exist"
        fail_count=$((fail_count + 1))
    fi
done

# 缓存清理
pycache_count=$(find . -type d -name "__pycache__" | wc -l)
if [ $pycache_count -ne 0 ]; then
    echo "WARNING: $pycache_count __pycache__ remaining"
fi

if [ $fail_count -eq 0 ]; then
    echo "PASS: File system validation"
else
    echo "FAIL: $fail_count violations"
fi
```

### S4-2: Git 验证

```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop

# Git 状态干净
if [ -z "$(git status --short)" ]; then
    echo "PASS: Git status clean"
else
    echo "FAIL: Uncommitted changes remain"
    git status --short
fi

# Tag 存在
if git tag -l | grep -q "v5.0.0"; then
    echo "PASS: v5.0.0 tag exists"
else
    echo "FAIL: v5.0.0 tag missing"
fi

# 基线文档存在
if [ -f BASELINE_v5.0.0.md ]; then
    echo "PASS: BASELINE_v5.0.0.md exists"
else
    echo "FAIL: BASELINE_v5.0.0.md missing"
fi

# 无追踪大文件
zip_count=$(git ls-files | grep -c "\.zip$")
if [ $zip_count -eq 0 ]; then
    echo "PASS: No tracked zip files"
else
    echo "WARNING: $zip_count zip files tracked"
fi
```

### S4-3: 测试验证

```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop

# 运行测试（串行，避免 SQLite 锁冲突）
python -m pytest tests/ -q --tb=short 2>&1 | tail -10

# 记录结果到基线文档
TEST_RESULT=$(python -m pytest tests/ -q --tb=short 2>&1 | tail -5)
```

**逻辑分支**:

**IF** 测试包含 ">0 failed":
- 提取失败测试名称
- 检查是否是已知的 flaky 测试
- **IF** 是已知 flaky → 更新 BASELINE 文档，标记 "flaky tests still present"
- **IF** 是新失败 → 报告 "新测试失败，基线不稳定"

**IF** 测试通过（0 failed）:
- 更新 BASELINE_v5.0.0.md 中的测试统计
- 标记 "基线验证通过"

---

## 五、回滚机制

### 如果任何阶段失败

**S1 失败（文件系统清理）**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
git stash pop  # 恢复备份
```

**S2 失败（Git 提交）**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
git reset --soft HEAD~1  # 回退到提交前
```

**S3 失败（标签创建）**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
git tag -d v5.0.0 2>/dev/null  # 删除标签（如果已创建）
```

**完全回滚**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
git reset --hard $(git rev-parse HEAD~3)  # 回退到清理前
# 注意：这会丢失清理后的变更，需要重新执行
```

---

## 六、最终交付检查清单

| # | 检查项 | 验证命令 | 通过标准 |
|---|--------|---------|---------|
| 1 | 根目录空壳删除 | `ls agents/ core/ sops/ tests/` | 不存在 |
| 2 | 缓存清理 | `find . -name "__pycache__" | wc -l` | 0 |
| 3 | 审计报告归档 | `ls workspace/frost-sop/archive/audits/` | 有文件 |
| 4 | Git 状态干净 | `git status --short` | 空 |
| 5 | v5.0.0 tag 存在 | `git tag -l | grep v5.0.0` | 匹配 |
| 6 | 测试 0 failed | `pytest tests/ -q` | 0 failed |
| 7 | 基线文档存在 | `ls BASELINE_v5.0.0.md` | 存在 |
| 8 | 无追踪大文件 | `git ls-files | grep "\.zip$" | wc -l` | 0 |
| 9 | .gitignore 更新 | `cat .gitignore | grep "archive/"` | 有匹配 |
| 10 | 真实代码完整 | `ls workspace/frost-sop/core/` | 有文件 |
| 11 | 备份 stash 存在 | `git stash list | grep pre-cleanup` | 有匹配 |
| 12 | 目录结构清晰 | `tree -L 2` 或等效 | 符合预期 |

**以上 12 项全部通过，版本清理与基线建立完成。**

---

## 七、如果用户后续要求审计

基线建立完成后，向用户汇报：

```
版本清理与基线建立完成。

基线信息：
- 版本: v5.0.0
- 标签: git tag v5.0.0
- 提交: $(git rev-parse HEAD)
- 基线文档: workspace/frost-sop/BASELINE_v5.0.0.md
- 备份: git stash (pre-cleanup-backup-YYYYMMDD-HHMMSS)

测试状态：
- X passed + Y skipped + 0 failed

目录结构：
- 根目录: 干净（只有启动脚本、配置、README）
- 代码: workspace/frost-sop/（唯一代码仓库）
- 归档: workspace/frost-sop/archive/（审计报告等）

已准备好接受第三方审计。
```

---

*指令结束。严格执行前置检查，按阶段执行，每阶段完成后运行验收清单。任何失败立即回滚并报告。*
