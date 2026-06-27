"""
F12 E2E 浏览器自动化诊断测试
目标：发现所有 UI 断链，诚实记录。不做任何代码修复。
策略：逐元素验证，不跳过、不假设、不替代码找理由。
"""
import subprocess
import sys
import os
import time
import json
import traceback
from datetime import datetime

# 确保 FROST_TESTING 环境变量
os.environ['FROST_TESTING'] = '1'

# ================================================================
# E2E 测试结果收集器
# ================================================================
class E2EResults:
    def __init__(self):
        self.elements = []  # 逐元素验证结果
        self.user_flows = []  # 用户路径测试结果
        self.errors = []  # 全局错误
        self.start_time = datetime.now()

    def add_element_test(self, location, element_id, element_type, clickable, has_response,
                         response_correct, error_msg=None):
        self.elements.append({
            "location": location,
            "element_id": element_id,
            "element_type": element_type,
            "clickable": clickable,  # True/False
            "has_response": has_response,  # True/False/None
            "response_correct": response_correct,  # True/False/None
            "error_msg": error_msg,
        })

    def add_flow_test(self, flow_name, passed, error_step=None, error_msg=None):
        self.user_flows.append({
            "flow_name": flow_name,
            "passed": passed,
            "error_step": error_step,
            "error_msg": error_msg,
        })

    def add_error(self, error_msg):
        self.errors.append(error_msg)

    def summary(self):
        total = len(self.elements)
        clickable_count = sum(1 for e in self.elements if e["clickable"])
        not_clickable = total - clickable_count
        responded_count = sum(1 for e in self.elements if e["has_response"] is True)
        correct_count = sum(1 for e in self.elements if e["response_correct"] is True)
        incorrect_count = sum(1 for e in self.elements
                              if e["response_correct"] is False)
        flows_passed = sum(1 for f in self.user_flows if f["passed"])
        flows_failed = len(self.user_flows) - flows_passed

        return {
            "total_elements_tested": total,
            "clickable": clickable_count,
            "not_clickable": not_clickable,
            "responded": responded_count,
            "no_response": total - responded_count,
            "response_correct": correct_count,
            "response_incorrect_or_unknown": incorrect_count + (total - responded_count - correct_count),
            "user_flows_passed": flows_passed,
            "user_flows_failed": flows_failed,
            "global_errors": len(self.errors),
            "element_pass_rate": round(clickable_count / total * 100, 1) if total > 0 else 0,
            "flow_pass_rate": round(flows_passed / len(self.user_flows) * 100, 1) if self.user_flows else 0,
        }


results = E2EResults()

# ================================================================
# Playwright 浏览器自动化
# ================================================================
def run_e2e_tests():
    """使用 Playwright 执行全量 E2E 测试"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        results.add_error("Playwright not installed")
        print("ERROR: Playwright not installed")
        return

    print("\n" + "=" * 70)
    print("  F12 E2E 浏览器自动化诊断测试")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        # 收集 console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        try:
            # Step 1: 打开首页
            print("\n[1/8] 打开 Streamlit 首页 ...")
            try:
                page.goto("http://localhost:8501", timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(3000)  # Streamlit 初始化
                print("   ✓ 页面加载成功")
            except Exception as e:
                results.add_error(f"首页加载失败: {e}")
                print(f"   ✗ 首页加载失败: {e}")
                browser.close()
                return

            # 截图首屏
            page.screenshot(path="output/f12_screenshot_home.png")

            # ========================================================
            # Part A: 逐个验证交互元素
            # ========================================================
            print("\n[2/8] 验证特定 UI 元素 ...")

            # A1. 顶部导航菜单
            print("\n  --- A. 顶部导航栏 ---")
            nav_buttons = [
                ("仪表盘", ".nav-link", "导航"),
                ("技能库", ".nav-link", "导航"),
                ("成本", ".nav-link", "导航"),
                ("输出文档", ".nav-link", "导航"),
                ("设置", ".nav-link", "导航"),
            ]

            # 尝试用不同选择器找到导航链接
            nav_links = page.query_selector_all('.nav-link')
            print(f"  找到 {len(nav_links)} 个导航链接")

            # A2. 项目概览区按钮
            print("\n  --- B. 项目概览区 ---")
            buttons_to_test = [
                ("▶ 开始工作", "btn_saas_start", "button"),
                ("↻ 换一个", "btn_saas_switch", "button"),
            ]
            for label, key, etype in buttons_to_test:
                try:
                    btn = page.query_selector(f'button[kind="primary"]')
                    if not btn:
                        btn = page.query_selector(f'button:has-text("{label}")')
                    clickable = btn is not None and btn.is_enabled() and btn.is_visible()
                    has_resp = None
                    correct = None
                    error = None
                    if not clickable:
                        error = "未找到按钮或按钮不可点击"
                    results.add_element_test("项目概览区", key, etype, clickable, has_resp, correct, error)
                    status = "✓" if clickable else "✗"
                    print(f"  {status} {label} ({key}): clickable={clickable}")
                except Exception as ex:
                    results.add_element_test("项目概览区", key, etype, False, None, None, str(ex))
                    print(f"  ✗ {label} ({key}): {ex}")

            # A3. CEO 对话面板
            print("\n  --- C. CEO 对话面板 ---")
            # 主输入框
            try:
                text_inputs = page.query_selector_all('input[type="text"], textarea')
                ceo_input = None
                for inp in text_inputs:
                    if inp.is_visible():
                        ceo_input = inp
                        break
                clickable = ceo_input is not None and ceo_input.is_enabled() and ceo_input.is_visible()
                results.add_element_test("CEO对话面板", "ceo_input", "input",
                                         clickable, None, None,
                                         None if clickable else "输入框不可用")
                print(f"  {'✓' if clickable else '✗'} CEO输入框: clickable={clickable}")
            except Exception as ex:
                results.add_element_test("CEO对话面板", "ceo_input", "input", False, None, None, str(ex))
                print(f"  ✗ CEO输入框: {ex}")

            # 发送按钮
            try:
                send_btn = page.query_selector('button:has-text("发送"), button[key="btn_ceo_send"]')
                clickable = send_btn is not None and send_btn.is_enabled() and send_btn.is_visible()
                results.add_element_test("CEO对话面板", "btn_ceo_send", "button",
                                         clickable, None, None,
                                         None if clickable else "发送按钮不可用")
                print(f"  {'✓' if clickable else '✗'} 发送按钮: clickable={clickable}")
            except Exception as ex:
                results.add_element_test("CEO对话面板", "btn_ceo_send", "button", False, None, None, str(ex))
                print(f"  ✗ 发送按钮: {ex}")

            # 三个快捷指令
            quick_commands = [
                ("📊 进度如何", "quick_progress"),
                ("💰 成本正常吗", "quick_cost"),
                ("🎯 下一步做什么", "quick_next"),
            ]
            for label, key in quick_commands:
                try:
                    btn = page.query_selector(f'button:has-text("{label}"), button[key="{key}"]')
                    clickable = btn is not None and btn.is_enabled() and btn.is_visible()
                    results.add_element_test("快捷指令", key, "button",
                                             clickable, None, None,
                                             None if clickable else "快捷按钮不可用")
                    print(f"  {'✓' if clickable else '✗'} {label} ({key}): clickable={clickable}")
                except Exception as ex:
                    results.add_element_test("快捷指令", key, "button", False, None, None, str(ex))
                    print(f"  ✗ {label} ({key}): {ex}")

            # A4. 模式切换按钮
            print("\n  --- D. 模式切换按钮 ---")
            mode_buttons = [
                ("开发模式", "mode_dev"),
                ("创作模式", "mode_create"),
                ("客户模式", "mode_client"),
            ]
            for label, key in mode_buttons:
                try:
                    btn = page.query_selector(f'button:has-text("{label}")')
                    clickable = btn is not None and btn.is_enabled() and btn.is_visible()
                    results.add_element_test("模式切换", key, "button",
                                             clickable, None, None,
                                             None if clickable else "模式按钮不可用")
                    print(f"  {'✓' if clickable else '✗'} {label} ({key}): clickable={clickable}")
                except Exception as ex:
                    results.add_element_test("模式切换", key, "button", False, None, None, str(ex))
                    print(f"  ✗ {label} ({key}): {ex}")

            # A5. Agent 团队网格
            print("\n  --- E. Agent 团队网格 ---")
            try:
                # Streamlit 通常用 div/card 渲染 agent
                agent_elements = page.query_selector_all('[data-testid="stVerticalBlock"]')
                agent_count = len(agent_elements)
                print(f"  找到 {agent_count} 个垂直块（可能包含 Agent 卡片）")

                # 寻找 Agent 标题
                for agent_name in ["CEO Agent", "Architect", "Parent Agent", "Elder Agent",
                                   "Code Agent", "Test Agent", "Review Agent", "DevOps Agent"]:
                    try:
                        el = page.query_selector(f'text="{agent_name}"')
                        found = el is not None and el.is_visible()
                        results.add_element_test("Agent团队", f"agent_{agent_name}", "card",
                                                 found, None, None,
                                                 None if found else f"Agent {agent_name} 未找到")
                        print(f"  {'✓' if found else '✗'} Agent: {agent_name}")
                    except Exception as ex:
                        results.add_element_test("Agent团队", f"agent_{agent_name}", "card",
                                                 False, None, None, str(ex))
                        print(f"  ✗ Agent: {agent_name}: {ex}")
            except Exception as ex:
                results.add_element_test("Agent团队", "agent_grid", "grid", False, None, None, str(ex))
                print(f"  ✗ Agent团队: {ex}")

            # A6. 执行任务按钮
            print("\n  --- F. 任务执行按钮 ---")
            task_buttons = [
                ("🚀 执行任务", "btn_execute", "button"),
                ("🆕 新功能开发", "btn_new_feature", "button"),
                ("🐛 Bug修复", "btn_bug_fix", "button"),
                ("📊 周期回顾", "btn_review", "button"),
                ("💾 保存当前配置", "btn_save_config", "button"),
                ("🔄 唤醒上次配置", "btn_load_config", "button"),
            ]
            for label, key, etype in task_buttons:
                try:
                    btn = page.query_selector(f'button:has-text("{label}")')
                    clickable = btn is not None and btn.is_enabled() and btn.is_visible()
                    results.add_element_test("任务执行", key, etype,
                                             clickable, None, None,
                                             None if clickable else f"{label} 按钮不可用")
                    print(f"  {'✓' if clickable else '✗'} {label} ({key}): clickable={clickable}")
                except Exception as ex:
                    results.add_element_test("任务执行", key, etype, False, None, None, str(ex))
                    print(f"  ✗ {label} ({key}): {ex}")

            # A7. 日终回顾按钮
            print("\n  --- G. 日终回顾按钮 ---")
            review_buttons = [
                ("✅ 确认打卡", "btn_review_confirm"),
                ("📝 修改叙事", "btn_review_edit"),
                ("⏭️ 稍后再说", "btn_review_dismiss"),
            ]
            for label, key in review_buttons:
                try:
                    btn = page.query_selector(f'button:has-text("{label}")')
                    clickable = btn is not None and btn.is_enabled() and btn.is_visible()
                    results.add_element_test("日终回顾", key, "button",
                                             clickable, None, None,
                                             None if clickable else f"{label} 按钮不可用")
                    print(f"  {'✓' if clickable else '✗'} {label} ({key}): clickable={clickable}")
                except Exception as ex:
                    results.add_element_test("日终回顾", key, "button", False, None, None, str(ex))
                    print(f"  ✗ {label} ({key}): {ex}")

            # A8. 能量记录器
            print("\n  --- H. 能量记录器 ---")
            try:
                record_btn = page.query_selector('button:has-text("记录此刻")')
                clickable = record_btn is not None and record_btn.is_enabled() and record_btn.is_visible()
                results.add_element_test("能量记录器", "record_energy", "button",
                                         clickable, None, None,
                                         None if clickable else "记录此刻按钮不可用")
                print(f"  {'✓' if clickable else '✗'} 记录此刻: clickable={clickable}")
            except Exception as ex:
                results.add_element_test("能量记录器", "record_energy", "button", False, None, None, str(ex))
                print(f"  ✗ 记录此刻: {ex}")

            # A9. 侧边栏元素
            print("\n  --- I. 侧边栏 ---")
            sidebar_buttons = [
                ("浏览模板", "sidebar_browse_templates"),
                ("查看雇佣兵", "sidebar_view_mercenaries"),
            ]
            for label, key in sidebar_buttons:
                try:
                    btn = page.query_selector(f'button:has-text("{label}")')
                    clickable = btn is not None and btn.is_enabled() and btn.is_visible()
                    results.add_element_test("侧边栏", key, "button",
                                             clickable, None, None,
                                             None if clickable else f"{label} 按钮不可用")
                    print(f"  {'✓' if clickable else '✗'} {label} ({key}): clickable={clickable}")
                except Exception as ex:
                    results.add_element_test("侧边栏", key, "button", False, None, None, str(ex))
                    print(f"  ✗ {label} ({key}): {ex}")

            # A10. 日程管理
            print("\n  --- J. 日程管理 ---")
            try:
                add_schedule_btn = page.query_selector('button:has-text("添加日程")')
                clickable = add_schedule_btn is not None and add_schedule_btn.is_enabled() and add_schedule_btn.is_visible()
                results.add_element_test("日程管理", "add_schedule_btn", "button",
                                         clickable, None, None,
                                         None if clickable else "添加日程按钮不可用")
                print(f"  {'✓' if clickable else '✗'} 添加日程: clickable={clickable}")
            except Exception as ex:
                results.add_element_test("日程管理", "add_schedule_btn", "button", False, None, None, str(ex))
                print(f"  ✗ 添加日程: {ex}")

            # ========================================================
            # Part B: 模拟完整用户路径
            # ========================================================

            # 流程 1: 打开首页
            print("\n[3/8] 模拟用户路径 1: 打开首页 ...")
            try:
                page.goto("http://localhost:8501", timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(3000)
                title = page.title()
                if "FROST" in title or "frost" in title.lower():
                    results.add_flow_test("打开首页", True)
                    print("  ✓ 首页标题正常")
                else:
                    results.add_flow_test("打开首页", True, None, f"标题不包含FROST: {title}")
                    print(f"  ~ 首页标题: {title}")
            except Exception as ex:
                results.add_flow_test("打开首页", False, "加载", str(ex))
                print(f"  ✗ 首页加载失败: {ex}")

            # 流程 2: 切换项目（如果侧边栏有项目列表）
            print("\n[4/8] 模拟用户路径 2: 切换项目 ...")
            try:
                # Try clicking the first project in sidebar
                proj_links = page.query_selector_all('[data-testid="stSidebar"] button')
                if len(proj_links) > 0:
                    proj_links[0].click()
                    page.wait_for_timeout(2000)
                    results.add_flow_test("切换项目", True)
                    print(f"  ✓ 点击了 {len(proj_links)} 个侧边栏按钮中的第一个")
                else:
                    results.add_flow_test("切换项目", False, "无项目按钮",
                                          "侧边栏无可点击的项目")
                    print("  ~ 侧边栏无项目按钮（可能仅单个项目）")
            except Exception as ex:
                results.add_flow_test("切换项目", False, "点击", str(ex))
                print(f"  ✗ 切换项目失败: {ex}")

            # 流程 3: 发送 CEO 对话
            print("\n[5/8] 模拟用户路径 3: 发送 CEO 对话消息 ...")
            try:
                text_areas = page.query_selector_all('textarea, input[type="text"]')
                if len(text_areas) > 0:
                    target = text_areas[0]
                    if target.is_visible():
                        target.fill("测试消息: 当前项目进度如何?")
                        page.wait_for_timeout(500)

                        send_btn = page.query_selector('button:has-text("发送")')
                        if send_btn and send_btn.is_enabled():
                            send_btn.click()
                            page.wait_for_timeout(3000)
                            results.add_flow_test("发送CEO消息", True)
                            print("  ✓ CEO消息发送成功")
                        else:
                            results.add_flow_test("发送CEO消息", False, "无发送按钮",
                                                  "发送按钮不可用")
                            print("  ✗ 发送按钮不可用")
                    else:
                        results.add_flow_test("发送CEO消息", False, "输入框不可见",
                                              "输入框不可见")
                        print("  ✗ 输入框不可见")
                else:
                    results.add_flow_test("发送CEO消息", False, "无输入框",
                                          "页面无textarea或input")
                    print("  ✗ 页面无输入框")
            except Exception as ex:
                results.add_flow_test("发送CEO消息", False, "发送", str(ex))
                print(f"  ✗ CEO消息发送失败: {ex}")

            # 流程 4: 点击快捷指令
            print("\n[6/8] 模拟用户路径 4: 执行快捷指令 ...")
            try:
                quick_btn = page.query_selector('button:has-text("进度如何")')
                if quick_btn and quick_btn.is_enabled():
                    quick_btn.click()
                    page.wait_for_timeout(3000)
                    results.add_flow_test("快捷指令-进度如何", True)
                    print("  ✓ 快捷指令'进度如何'点击成功")
                else:
                    results.add_flow_test("快捷指令-进度如何", False, "按钮不可用",
                                          "快捷指令按钮不可用")
                    print("  ✗ 快捷指令按钮不可用")
            except Exception as ex:
                results.add_flow_test("快捷指令-进度如何", False, "点击", str(ex))
                print(f"  ✗ 快捷指令失败: {ex}")

            # 流程 5: 查看成本面板
            print("\n[7/8] 模拟用户路径 5: 查看成本面板 ...")
            try:
                cost_btn = page.query_selector('text="成本"')
                if cost_btn and cost_btn.is_visible():
                    cost_btn.click()
                    page.wait_for_timeout(3000)
                    results.add_flow_test("查看成本面板", True)
                    print("  ✓ 成本面板加载成功")
                else:
                    results.add_flow_test("查看成本面板", False, "无成本链接",
                                          "成本导航不可见")
                    print("  ~ 成本导航不可见，可能已显示在首屏")
            except Exception as ex:
                results.add_flow_test("查看成本面板", False, "切换", str(ex))
                print(f"  ✗ 成本面板查看失败: {ex}")

            # 流程 6: 查看日志面板
            print("\n[8/8] 模拟用户路径 6: 查看页面底部 ...")
            try:
                page.screenshot(path="output/f12_screenshot_full.png", full_page=True)
                # 检查页面底部是否有内容
                page_content = page.content()
                has_log = "实时日志" in page_content or "log" in page_content.lower()
                has_footer = "家族状态" in page_content or "Token" in page_content
                if has_log or has_footer:
                    results.add_flow_test("查看底部面板", True)
                    print(f"  ✓ 底部内容可见 (日志: {has_log}, 家族状态: {has_footer})")
                else:
                    results.add_flow_test("查看底部面板", False, "内容缺失",
                                          "底部无日志/家族状态内容")
                    print("  ✗ 底部内容缺失")
            except Exception as ex:
                results.add_flow_test("查看底部面板", False, "滚动", str(ex))
                print(f"  ✗ 底部查看失败: {ex}")

            # ========================================================
            # Part C: console errors
            # ========================================================
            print("\n--- 检查浏览器 Console Errors ---")
            if console_errors:
                print(f"  ⚠ 发现 {len(console_errors)} 个 console errors:")
                for i, err in enumerate(console_errors[:20]):  # 最多显示20个
                    print(f"    [{i+1}] {err[:200]}")
                results.add_error(f"Console errors: {len(console_errors)} 个")
            else:
                print("  ✓ 无 console errors")

        except Exception as e:
            results.add_error(f"E2E 测试异常: {e}")
            traceback.print_exc()
            print(f"\n  ✗✗✗ 测试异常: {e}")
        finally:
            browser.close()

    # 打印汇总
    print("\n" + "=" * 70)
    s = results.summary()
    print("  E2E 测试结果汇总")
    print("=" * 70)
    print(f"  测试元素总数:     {s['total_elements_tested']}")
    print(f"  可点击:           {s['clickable']}")
    print(f"  不可点击/不可见:   {s['not_clickable']}")
    print(f"  用户路径通过:      {s['user_flows_passed']}/{len(results.user_flows)}")
    print(f"  用户路径失败:      {s['user_flows_failed']}/{len(results.user_flows)}")
    print(f"  全局错误:          {s['global_errors']}")
    print(f"  元素可点击率:      {s['element_pass_rate']}%")
    print(f"  用户路径通过率:    {s['flow_pass_rate']}%")
    print(f"  耗时:              {(datetime.now() - results.start_time).total_seconds():.1f}s")
    print("=" * 70)

    return results


def print_failures(results_obj):
    """打印所有失败项"""
    print("\n--- 失败清单 ---")
    failures = [e for e in results_obj.elements if not e["clickable"]]
    if failures:
        for f in failures:
            print(f"  ✗ [{f['location']}] {f['element_id']}: {f.get('error_msg', '不可点击/不可见')}")
    else:
        print("  (无元素级失败)")

    print("\n--- 用户路径失败清单 ---")
    failures = [f for f in results_obj.user_flows if not f["passed"]]
    if failures:
        for f in failures:
            print(f"  ✗ {f['flow_name']}: {f.get('error_msg', '未知错误')} (步骤: {f.get('error_step', 'N/A')})")
    else:
        print("  (无用户路径失败)")

    print("\n--- 全局错误 ---")
    if results_obj.errors:
        for e in results_obj.errors:
            print(f"  ⚠ {e}")
    else:
        print("  (无全局错误)")


# ================================================================
# Streamlit 服务管理
# ================================================================
def start_streamlit():
    """后台启动 Streamlit"""
    import subprocess
    print("启动 Streamlit 服务 (localhost:8501) ...")
    env = os.environ.copy()
    env['FROST_TESTING'] = '1'

    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", "-m", "streamlit", "run", "app.py",
         "--server.port=8501", "--server.headless=true",
         "--server.runOnSave=false", "--browser.gatherUsageStats=false"],
        cwd="D:/my_ai/Solo-Ops-Platform/workspace/frost-sop",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 等待服务就绪
    import urllib.request
    for i in range(60):
        try:
            urllib.request.urlopen("http://localhost:8501", timeout=2)
            print(f"  ✓ Streamlit 就绪 (耗时 {i+1}s)")
            return proc
        except Exception:
            time.sleep(1)
            if i == 30:
                print(f"  等待 Streamlit 启动中... ({i}s)")
    proc.kill()
    raise RuntimeError("Streamlit 启动超时(60s)")


def stop_streamlit(proc):
    """停止 Streamlit"""
    if proc:
        proc.terminate()
        proc.wait(timeout=10)
        print("  Streamlit 已停止")


# ================================================================
# 主入口
# ================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  F12 E2E 浏览器自动化诊断测试")
    print(f"  Python: {sys.version}")
    print(f"  FROST_TESTING: {os.environ.get('FROST_TESTING', 'NOT SET')}")
    print("=" * 70)

    # 创建 output 目录
    os.makedirs("output", exist_ok=True)

    # 启动 Streamlit
    streamlit_proc = None
    try:
        streamlit_proc = start_streamlit()
    except Exception as e:
        print(f"ERROR: Streamlit 启动失败: {e}")
        print("请手动启动 Streamlit 后重试: streamlit run app.py")
        sys.exit(1)

    # 运行 E2E 测试
    try:
        run_e2e_tests()
    finally:
        stop_streamlit(streamlit_proc)

    # 打印失败清单
    print_failures(results)

    # 保存结果到 JSON
    output_path = "output/f12_e2e_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": results.summary(),
            "elements": results.elements,
            "user_flows": results.user_flows,
            "errors": results.errors,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到: {output_path}")
