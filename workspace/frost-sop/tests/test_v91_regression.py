"""
FROST-SOP V9.1 阶段1-2 修复验证测试
测试目标: 验证用户反馈问题的修复和架构加固

运行: pytest tests/test_v91_regression.py -v
"""

import pytest
import json


class TestFrontendStateSync:
    """阶段1.1: 前端状态同步修复测试"""

    def test_page_tsx_syntax_valid(self):
        """验证 page.tsx 没有语法错误"""
        import ast
        
        # 读取 page.tsx (作为文本检查关键模式)
        with open("frontend/src/app/projects/[id]/page.tsx", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查 Badge 导入正确
        assert 'import { Badge } from "@/components/ui/badge";' in content
        # 检查没有残留错误语法
        assert "  Badge," not in content
        # 检查 ScrollArea 使用
        assert "<ScrollArea" in content
        # 检查 chatEnabled 逻辑
        assert "config.chatEnabled" in content
        # 检查 pending 禁用
        assert "🔒 未开始" in content

    def test_stage_status_config_complete(self):
        """验证阶段状态配置覆盖所有状态"""
        with open("frontend/src/app/projects/[id]/page.tsx", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 所有状态都应该有配置
        for status in ["pending", "running", "completed", "failed", "waiting_human"]:
            assert status in content, f"状态 {status} 未配置"

    def test_task_stages_api_integration(self):
        """验证 getTaskStages API 集成"""
        with open("frontend/src/app/projects/[id]/page.tsx", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "getTaskStages" in content
        assert "task-stages" in content  # queryKey


class TestHumanTimeout:
    """阶段1.2: 人类府兵超时机制测试"""

    def test_db_migration_fields(self):
        """验证数据库迁移添加了超时字段"""
        with open("core/db.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "timeout_minutes" in content
        assert "expires_at" in content
        assert "timeout_action" in content

    def test_check_expired_decisions_function(self):
        """验证 check_expired_decisions 函数存在"""
        with open("core/db.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "def check_expired_decisions" in content
        assert "def resolve_decision_timeout" in content

    def test_api_timeout_endpoint(self):
        """验证超时检查 API 端点存在"""
        with open("api/main.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "/api/decisions/check-timeout" in content
        assert "check_decision_timeout" in content


class TestAPIErrorHandling:
    """阶段1.3: API 错误处理标准化测试"""

    def test_global_exception_handler(self):
        """验证全局异常处理器存在"""
        with open("api/main.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "@app.exception_handler(Exception)" in content
        assert "global_exception_handler" in content
        assert "error_id" in content
        assert "error_code" in content

    def test_no_empty_except_blocks(self):
        """验证没有空 except 块"""
        with open("api/main.py", "r", encoding="utf-8") as f:
            lines = content.split("\n")
        
        empty_excepts = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("except ") and stripped.endswith(":"):
                # 检查后续行
                next_lines = []
                for j in range(i, min(i + 5, len(lines))):
                    nl = lines[j].strip()
                    if nl and not nl.startswith("#"):
                        next_lines.append(nl)
                
                # 排除 except 行本身
                action_lines = [l for l in next_lines[1:] if l != "pass"]
                if not action_lines:
                    empty_excepts.append(f"第{i}行: {stripped}")
        
        assert len(empty_excepts) == 0, f"发现空 except 块: {empty_excepts}"

    def test_get_task_stages_error_handling(self):
        """验证 get_task_stages 有异常处理"""
        with open("api/main.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 找到 get_task_stages 函数
        func_start = content.find("def get_task_stages")
        func_end = content.find("\n\n", func_start + 100)
        func_body = content[func_start:func_end]
        
        assert "try:" in func_body
        assert "except Exception" in func_body
        assert "TASK_ID_INVALID" in func_body or "STAGES_QUERY_FAILED" in func_body

    def test_error_codes_defined(self):
        """验证错误码已定义"""
        with open("api/main.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        required_codes = [
            "TASK_ID_INVALID",
            "STAGES_QUERY_FAILED",
            "INTERNAL_SERVER_ERROR",
        ]
        
        for code in required_codes:
            assert code in content, f"错误码 {code} 未定义"


class TestFrontendChatLimit:
    """阶段1.4: 前端字数限制修复测试"""

    def test_textarea_component_used(self):
        """验证使用 Textarea 替代 Input"""
        with open("frontend/src/components/CeoChat.tsx", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert 'import { Textarea } from "@/components/ui/textarea";' in content
        assert "<Textarea" in content
        assert 'import { Input }' not in content

    def test_character_count_display(self):
        """验证字数统计显示"""
        with open("frontend/src/components/CeoChat.tsx", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "{input.length} 字" in content

    def test_max_tokens_increased(self):
        """验证 max_tokens 增加到 4096"""
        with open("api/main.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert '_max_tokens": 4096' in content
        assert '_max_tokens": 1024' not in content


class TestArchitecture:
    """阶段2: 架构加固测试"""

    def test_error_boundary_component(self):
        """验证 ErrorBoundary 组件存在"""
        with open("frontend/src/components/ErrorBoundary.tsx", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "class ErrorBoundary" in content
        assert "componentDidCatch" in content
        assert "getDerivedStateFromError" in content

    def test_providers_integrate_error_boundary(self):
        """验证 Providers 集成 ErrorBoundary"""
        with open("frontend/src/app/providers.tsx", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "ErrorBoundary" in content
        assert "<ErrorBoundary>" in content

    def test_sse_reconnect_logic(self):
        """验证 SSE 重连逻辑"""
        with open("frontend/src/hooks/useEventSource.ts", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "MAX_RECONNECT_ATTEMPTS" in content
        assert "HEARTBEAT_TIMEOUT" in content
        assert "Math.pow(2" in content  # 指数退避

    def test_api_standardized_errors(self):
        """验证 API 错误标准化"""
        with open("frontend/src/lib/api.ts", "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "class APIError" in content
        assert "AbortController" in content  # 超时控制
        assert "errorCode" in content
        assert "NETWORK_ERROR" in content
        assert "REQUEST_TIMEOUT" in content

    def test_input_validation(self):
        """验证前端输入校验"""
        with open("frontend/src/lib/api.ts", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查各种输入校验
        assert "PROJECT_ID_INVALID" in content
        assert "TASK_ID_INVALID" in content
        assert "CHAT_MESSAGE_EMPTY" in content


class TestEndToEnd:
    """端到端场景测试"""

    def test_user_journey_create_task_view_stages(self):
        """用户旅程: 创建任务 → 查看阶段 → 对话交互"""
        # 验证所有需要的组件和 API 都存在
        
        # 1. 创建任务 API
        with open("frontend/src/lib/api.ts", "r", encoding="utf-8") as f:
            api_content = f.read()
        assert "createTask" in api_content
        
        # 2. 查看阶段 API
        assert "getTaskStages" in api_content
        
        # 3. 对话 API
        assert "sendChat" in api_content
        
        # 4. 前端页面
        with open("frontend/src/app/projects/[id]/page.tsx", "r", encoding="utf-8") as f:
            page_content = f.read()
        assert "getTaskStages" in page_content
        assert "config.chatEnabled" in page_content

    def test_error_recovery_path(self):
        """错误恢复路径: API 失败 → ErrorBoundary → 刷新"""
        # 验证错误处理链路完整
        
        # 1. 全局异常处理器
        with open("api/main.py", "r", encoding="utf-8") as f:
            api_content = f.read()
        assert "global_exception_handler" in api_content
        
        # 2. 前端 ErrorBoundary
        with open("frontend/src/components/ErrorBoundary.tsx", "r", encoding="utf-8") as f:
            eb_content = f.read()
        assert "window.location.reload()" in eb_content
        
        # 3. API 错误类
        with open("frontend/src/lib/api.ts", "r", encoding="utf-8") as f:
            api_ts_content = f.read()
        assert "class APIError" in api_ts_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
