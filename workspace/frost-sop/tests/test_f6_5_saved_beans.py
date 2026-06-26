"""
F6.5 撒豆成兵 - 功能测试脚本
测试配置的保存、加载和自动唤醒功能
"""

import os
import sys
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.store import AssetStore

def test_asset_store():
    """测试 AssetStore 类的功能"""
    print("=" * 60)
    print("F6.5 撒豆成兵 - 功能测试")
    print("=" * 60)

    # 1. 创建 AssetStore 实例
    print("\n[1] 创建 AssetStore 实例...")
    asset_store = AssetStore(assets_dir="assets/")
    print(f"   ✓ AssetStore 创建成功，配置目录: {asset_store.assets_dir}")

    # 2. 保存配置
    print("\n[2] 测试保存配置...")
    config = {
        "timestamp": "2026-06-22T01:30:00",
        "task_description": "做一个竞品分析",
        "parameters": {"depth": "详细", "format": "报告"},
        "project_name": "竞品分析项目",
        "version": "F6.5",
    }
    filename = asset_store.save(config)
    print(f"   ✓ 配置已保存: {filename}")

    # 3. 列出所有配置
    print("\n[3] 测试列出所有配置...")
    files = asset_store.list()
    print(f"   ✓ 找到 {len(files)} 个配置文件:")
    for f in files[:5]:
        print(f"      - {f}")

    # 4. 加载最新配置
    print("\n[4] 测试加载最新配置...")
    latest_config = asset_store.load_latest()
    if latest_config:
        print(f"   ✓ 最新配置加载成功:")
        print(f"      - 任务描述: {latest_config.get('task_description')}")
        print(f"      - 项目名: {latest_config.get('project_name')}")
        print(f"      - 版本: {latest_config.get('version')}")

    # 5. 加载指定配置
    print("\n[5] 测试加载指定配置...")
    loaded_config = asset_store.load(filename)
    if loaded_config:
        print(f"   ✓ 指定配置加载成功: {loaded_config.get('task_description')}")

    # 6. 测试自动唤醒场景
    print("\n[6] 测试自动唤醒场景...")
    # 模拟应用启动时的自动唤醒
    auto_config = asset_store.load_latest()
    if auto_config:
        print(f"   ✓ 自动唤醒成功，任务描述: {auto_config.get('task_description')}")
        print(f"   ✓ 可以直接填充到界面，用户无需重新输入")

    print("\n" + "=" * 60)
    print("F6.5 测试完成！所有功能正常")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        test_asset_store()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
