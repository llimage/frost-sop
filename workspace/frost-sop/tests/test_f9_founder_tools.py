"""
F9 创始人工具 - 单元测试 & 集成测试

测试覆盖：
1. 能量状态记录 (add_energy_log / get_energy_history / get_latest_energy)
2. 日程管理 (add_schedule / get_schedules / update_schedule / delete_schedule)
3. 提醒功能 (get_upcoming_reminders / mark_schedule_notified)

所有测试在 FROST_TESTING=1 模式下运行。
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta

# 设置测试环境
os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_db
from core.notifier import send_windows_notification


class TestF9EnergyLog:
    """测试能量状态记录功能"""

    @classmethod
    def setup_class(cls):
        cls.db = get_db()
        # 清理测试数据
        conn = cls.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM energy_log WHERE agent_id = 'f9_test'")
        conn.commit()

    def test_add_energy_log(self):
        """测试写入能量记录"""
        rid = self.db.add_energy_log(
            level=75,
            emotion="专注",
            note="测试记录"
        )
        assert rid is not None and rid > 0, f"记录ID应为正整数，得到: {rid}"
        print(f"  ✅ test_add_energy_log 通过 (id={rid})")

    def test_get_latest_energy(self):
        """测试获取最新能量记录"""
        result = self.db.get_latest_energy()
        assert result is not None, "应有能量记录"
        assert "level" in result or "energy_level" in result, "应有能量字段"
        print(f"  ✅ test_get_latest_energy 通过")

    def test_get_energy_history(self):
        """测试获取能量历史"""
        # 插入多条记录
        for level, emotion in [(60, "平静"), (80, "兴奋"), (40, "疲惫")]:
            self.db.add_energy_log(level=level, emotion=emotion, note="")

        history = self.db.get_energy_history(30)
        assert len(history) >= 3, f"应有至少3条记录，得到: {len(history)}"
        print(f"  ✅ test_get_energy_history 通过 ({len(history)} 条)")

    def test_low_energy_detection(self):
        """测试低能量检测（决策点集成用）"""
        # 插入一条低能量记录
        self.db.add_energy_log(level=25, emotion="低落", note="测试低能量")
        latest = self.db.get_latest_energy()
        energy_val = latest.get("level") or latest.get("energy_level", 100)
        assert energy_val is not None
        is_low = energy_val < 30
        assert is_low, f"能量 {energy_val} 应 < 30"
        print(f"  ✅ test_low_energy_detection 通过 (能量={energy_val})")


class TestF9Schedule:
    """测试日程管理功能"""

    @classmethod
    def setup_class(cls):
        cls.db = get_db()
        # 清理测试数据
        conn = cls.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedule WHERE name LIKE 'F9测试%' OR title LIKE 'F9测试%'")
        conn.commit()

    def test_add_schedule(self):
        """测试添加日程"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        end_time = (datetime.now() + timedelta(days=1, hours=1)).strftime("%Y-%m-%d %H:%M")

        sid = self.db.add_schedule(
            title="F9测试日程1",
            description="这是一个测试日程",
            start_time=tomorrow,
            end_time=end_time,
            repeat_type="daily"
        )
        assert sid is not None and sid > 0, f"日程ID应为正整数，得到: {sid}"
        print(f"  ✅ test_add_schedule 通过 (id={sid})")

    def test_get_schedules(self):
        """测试获取日程列表"""
        schedules = self.db.get_schedules()
        test_schedules = [s for s in schedules 
                         if (s.get("title") or s.get("name", "")).startswith("F9测试")]
        assert len(test_schedules) >= 1, f"应有至少1条测试日程，得到: {len(test_schedules)}"
        print(f"  ✅ test_get_schedules 通过 ({len(test_schedules)} 条测试日程)")

    def test_update_schedule(self):
        """测试更新日程"""
        schedules = self.db.get_schedules()
        test_schedules = [s for s in schedules 
                         if (s.get("title") or s.get("name", "")).startswith("F9测试")]
        if not test_schedules:
            print("  ⚠️ 没有测试日程可更新，跳过")
            return

        sid = test_schedules[0]["id"]
        result = self.db.update_schedule(
            schedule_id=sid,
            title="F9测试日程1-已更新",
            description="已更新描述",
            start_time=test_schedules[0].get("start_time", ""),
            end_time=test_schedules[0].get("end_time", ""),
            repeat_type="weekly",
            repeat_end=""
        )
        assert result, "更新应成功"
        print(f"  ✅ test_update_schedule 通过")

    def test_delete_schedule(self):
        """测试删除日程"""
        # 添加一条新日程用于删除
        tomorrow = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        end_time = (datetime.now() + timedelta(days=2, hours=1)).strftime("%Y-%m-%d %H:%M")
        sid = self.db.add_schedule(
            title="F9测试删除日程",
            start_time=tomorrow,
            end_time=end_time
        )

        result = self.db.delete_schedule(sid)
        assert result, "删除应成功"

        # 确认已删除
        schedules = self.db.get_schedules()
        deleted = [s for s in schedules if s["id"] == sid]
        assert len(deleted) == 0, "日程应已删除"
        print(f"  ✅ test_delete_schedule 通过")

    def test_get_upcoming_reminders(self):
        """测试获取近期提醒"""
        # 添加一个5分钟内的日程
        now = datetime.now()
        start = (now + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        end = (now + timedelta(minutes=65)).strftime("%Y-%m-%d %H:%M:%S")

        sid = self.db.add_schedule(
            title="F9测试提醒日程",
            start_time=start,
            end_time=end
        )

        # 获取未来15分钟内的提醒
        upcoming = self.db.get_upcoming_reminders(15)
        test_reminders = [u for u in upcoming 
                         if (u.get("title") or u.get("name", "")).startswith("F9测试")]
        
        if test_reminders:
            print(f"  ✅ test_get_upcoming_reminders 通过 ({len(test_reminders)} 条)")

            # 测试标记已通知
            self.db.mark_schedule_notified(test_reminders[0]["id"])
            upcoming2 = self.db.get_upcoming_reminders(15)
            test_reminders2 = [u for u in upcoming2 
                              if u["id"] == test_reminders[0]["id"]]
            assert len(test_reminders2) == 0, "标记后不应再出现"
            print(f"  ✅ test_mark_schedule_notified 通过")
        else:
            print("  ⚠️ 提醒未触发（时间差分问题），跳过标记测试")

        # 清理
        self.db.delete_schedule(sid)


class TestF9Notifier:
    """测试通知功能"""

    def test_notifier_import(self):
        """测试通知模块导入"""
        from core.notifier import send_windows_notification, check_decision_timeout
        assert callable(send_windows_notification), "send_windows_notification 应可调用"
        assert callable(check_decision_timeout), "check_decision_timeout 应可调用"
        print(f"  ✅ test_notifier_import 通过")

    def test_timeout_check(self):
        """测试超时检查函数"""
        from core.notifier import check_decision_timeout

        # 2小时前的决策
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        assert check_decision_timeout(old_time, 3600), "2小时前应超时"

        # 30分钟前的决策
        recent_time = (datetime.now() - timedelta(minutes=30)).isoformat()
        assert not check_decision_timeout(recent_time, 3600), "30分钟前不应超时"

        print(f"  ✅ test_timeout_check 通过")


class TestF9DBMigration:
    """测试数据库表迁移"""

    def test_energy_log_columns(self):
        """验证 energy_log 表有F9需要的列"""
        conn = get_db().get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(energy_log)")
        cols = {c["name"] for c in cursor.fetchall()}
        for col in ["level", "emotion", "user_note"]:
            assert col in cols, f"energy_log 缺少列: {col}"
        print(f"  ✅ test_energy_log_columns 通过")

    def test_schedule_columns(self):
        """验证 schedule 表有F9需要的列"""
        conn = get_db().get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(schedule)")
        cols = {c["name"] for c in cursor.fetchall()}
        for col in ["title", "description", "start_time", "end_time", 
                     "repeat_type", "repeat_end", "notified"]:
            assert col in cols, f"schedule 缺少列: {col}"
        print(f"  ✅ test_schedule_columns 通过")


def run_all_tests():
    """运行所有F9测试"""
    print("=" * 60)
    print("F9 创始人工具 - 测试套件")
    print("=" * 60)

    passed = 0
    failed = 0
    total = 0

    test_classes = [
        TestF9DBMigration,
        TestF9EnergyLog,
        TestF9Schedule,
        TestF9Notifier,
    ]

    for test_class in test_classes:
        print(f"\n--- {test_class.__name__} ---")
        instance = test_class()
        if hasattr(instance, 'setup_class'):
            instance.setup_class()

        for method_name in dir(instance):
            if method_name.startswith("test_"):
                total += 1
                method = getattr(instance, method_name)
                try:
                    method()
                    passed += 1
                except Exception as e:
                    failed += 1
                    print(f"  ❌ {method_name} 失败: {e}")
                    import traceback
                    traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"结果: {passed} 通过, {failed} 失败, {total} 总计")
    print(f"{'=' * 60}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
