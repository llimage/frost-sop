"""
FROST-SOP API 负载测试 (Locust)

使用方式:
    cd workspace/frost-sop
    locust -f tests/load/locustfile.py --host=http://localhost:8000

然后打开 http://localhost:8089 配置并发用户数和生成速率。
"""

import json
import random
from locust import HttpUser, task, between, events


class FROSTAPIUser(HttpUser):
    """模拟 API 用户行为"""

    wait_time = between(1, 3)  # 请求间隔 1-3 秒

    def on_start(self):
        """用户初始化：获取 SOP 列表作为后续请求的基础数据。"""
        self.task_ids: list[str] = []
        self.sop_ids: list[str] = []
        self.agent_ids: list[str] = []

        # 获取 SOP 列表
        with self.client.get("/api/sops", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "sops" in data:
                    self.sop_ids = [s["sop_id"] for s in data["sops"]]
                elif isinstance(data, list):
                    self.sop_ids = [s.get("sop_id", "") for s in data if s.get("sop_id")]

    # ────────────────────────────────
    # SOP 相关接口
    # ────────────────────────────────

    @task(5)
    def list_sops(self):
        """获取 SOP 列表（高频操作）"""
        with self.client.get("/api/sops", name="GET /sops", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(3)
    def get_sop_detail(self):
        """获取单个 SOP 详情"""
        if not self.sop_ids:
            return
        sop_id = random.choice(self.sop_ids)
        with self.client.get(
            f"/api/sops/{sop_id}",
            name="GET /sops/{id}",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 404):
                resp.failure(f"Unexpected status: {resp.status_code}")

    # ────────────────────────────────
    # 任务相关接口
    # ────────────────────────────────

    @task(2)
    def create_task(self):
        """创建新任务"""
        payload = {
            "task_type": "feature_development",
            "sop_id": random.choice(self.sop_ids) if self.sop_ids else "DEV-001",
            "description": f"Load test task #{random.randint(1, 99999)}",
            "priority": random.choice(["low", "medium", "high"]),
            "tags": ["loadtest"],
        }
        with self.client.post(
            "/api/tasks",
            json=payload,
            name="POST /tasks",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                data = resp.json()
                task_id = data.get("task_id", "")
                if task_id:
                    self.task_ids.append(task_id)
            elif resp.status_code == 422:
                # 参数校验失败，可接受
                pass
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(3)
    def list_tasks(self):
        """获取任务列表"""
        with self.client.get("/api/tasks", name="GET /tasks", catch_response=True) as resp:
            if resp.status_code not in (200, 404):
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def get_task_detail(self):
        """获取单个任务详情"""
        if not self.task_ids:
            return
        task_id = random.choice(self.task_ids)
        with self.client.get(
            f"/api/tasks/{task_id}",
            name="GET /tasks/{id}",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 404):
                resp.failure(f"Unexpected status: {resp.status_code}")

    # ────────────────────────────────
    # Agent 相关接口
    # ────────────────────────────────

    @task(2)
    def list_agents(self):
        """获取 Agent 列表"""
        with self.client.get("/api/agents", name="GET /agents", catch_response=True) as resp:
            if resp.status_code not in (200, 404):
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def create_agent(self):
        """创建 Agent"""
        payload = {
            "agent_type": "grandchild",
            "parent_id": "parent_001",
            "task_id": random.choice(self.task_ids) if self.task_ids else "task_test",
            "config": {"max_retries": 3},
        }
        with self.client.post(
            "/api/agents",
            json=payload,
            name="POST /agents",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                data = resp.json()
                agent_id = data.get("agent_id", "")
                if agent_id:
                    self.agent_ids.append(agent_id)
            elif resp.status_code == 422:
                pass
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    # ────────────────────────────────
    # 健康检查
    # ────────────────────────────────

    @task(1)
    def health_check(self):
        """健康检查"""
        with self.client.get("/api/health", name="Health Check", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Health check failed: {resp.status_code}")

    @task(1)
    def root_status(self):
        """根路径状态"""
        with self.client.get("/", name="Root Status", catch_response=True) as resp:
            if resp.status_code not in (200, 404):
                resp.failure(f"Root returned: {resp.status_code}")


# ────────────────────────────────
# 事件钩子：收集自定义指标
# ────────────────────────────────

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Locust 初始化时的自定义配置。"""
    if environment.web_ui:
        environment.web_ui.app.config["CUSTOM_MESSAGE"] = "FROST-SOP Load Test"


# ────────────────────────────────
# 预设场景
# ────────────────────────────────

class SmokeTest(HttpUser):
    """轻量冒烟测试：少量用户，验证基本功能。"""

    wait_time = between(2, 5)

    @task
    def health_and_sops(self):
        """健康检查 + SOP列表（最小可用性验证）"""
        with self.client.get("/api/health", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure("Smoke: health check failed")
        with self.client.get("/api/sops", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure("Smoke: SOP list failed")


class StressTest(HttpUser):
    """压力测试：高并发，短间隔。"""

    wait_time = between(0.1, 0.5)

    @task(5)
    def rapid_fire_sops(self):
        self.client.get("/api/sops", name="STRESS: GET /sops")

    @task(3)
    def rapid_fire_health(self):
        self.client.get("/api/health", name="STRESS: Health")

    @task(2)
    def rapid_fire_tasks(self):
        self.client.get("/api/tasks", name="STRESS: GET /tasks")
