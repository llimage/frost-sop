"""
F8 新增：Windows 桌面通知模块

当决策点超过指定时间未响应时，触发桌面通知提醒用户。
"""

import sys
import time


def send_windows_notification(title: str, message: str, duration: int = 5):
    """
    发送 Windows 桌面通知。

    优先使用 win10toast，如果失败则尝试使用 plyer。
    如果都失败，则降级为控制台输出。

    Args:
        title: 通知标题
        message: 通知内容
        duration: 通知显示时长（秒）

    Returns:
        bool: 是否成功发送通知
    """

    # 方法1：尝试使用 win10toast
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=duration, threaded=True)
        return True
    except ImportError:
        pass  # win10toast 未安装，尝试下一个方法
    except Exception as e:
        print(f"⚠️ win10toast 通知失败: {e}")

    # 方法2：尝试使用 plyer
    try:
        import plyer
        plyer.notification(
            title=title,
            message=message,
            app_icon=None,  # 可以指定图标路径
            timeout=duration
        )
        return True
    except ImportError:
        pass  # plyer 未安装，尝试下一个方法
    except Exception as e:
        print(f"⚠️ plyer 通知失败: {e}")

    # 方法3：降级为控制台输出（跨平台兼容）
    print("\n" + "=" * 60)
    print(f"🔔 桌面通知（降级模式）")
    print(f"标题: {title}")
    print(f"内容: {message}")
    print("=" * 60 + "\n")

    return False


def check_decision_timeout(decision_created_at, timeout_seconds: int = 3600):
    """
    检查决策是否超时。

    Args:
        decision_created_at: 决策创建时间（字符串或 datetime 对象）
        timeout_seconds: 超时时间（秒），默认 3600 秒（1小时）

    Returns:
        bool: 是否超时
    """
    from datetime import datetime

    # 解析决策创建时间
    if isinstance(decision_created_at, str):
        try:
            # 尝试解析 ISO 格式时间字符串
            created_at = datetime.fromisoformat(decision_created_at.replace("Z", "+00:00"))
        except ValueError:
            # 如果解析失败，假设未超时
            return False
    else:
        created_at = decision_created_at

    # 计算时间差
    now = datetime.now()
    time_diff = (now - created_at).total_seconds()

    return time_diff > timeout_seconds


def send_timeout_notification(decision_id: str, task_id: str, stage_id: str):
    """
    发送决策超时通知。

    Args:
        decision_id: 决策ID
        task_id: 任务ID
        stage_id: 阶段ID

    Returns:
        bool: 是否成功发送通知
    """
    title = "FROST-SOP 决策超时"
    message = f"任务 {task_id} 已在决策点等待超过1小时，请尽快处理！\n决策ID: {decision_id}\n阶段: {stage_id}"

    return send_windows_notification(title, message, duration=10)


# 测试代码
if __name__ == "__main__":
    print("测试 Windows 通知...")

    # 测试1：发送普通通知
    result = send_windows_notification(
        title="FROST-SOP 测试通知",
        message="这是一条测试通知，用于验证通知功能是否正常。",
        duration=5
    )
    print(f"通知发送结果: {result}")

    # 测试2：检查超时
    from datetime import datetime, timedelta
    old_time = datetime.now() - timedelta(hours=2)  # 2小时前
    is_timeout = check_decision_timeout(old_time, timeout_seconds=3600)
    print(f"超时检查（2小时前创建，1小时超时）: {is_timeout}")

    # 测试3：发送超时通知
    result = send_timeout_notification(
        decision_id="test_decision_001",
        task_id="test_task_001",
        stage_id="test_stage_001"
    )
    print(f"超时通知发送结果: {result}")
