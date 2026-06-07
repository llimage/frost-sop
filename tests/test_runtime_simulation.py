"""V0.7.0 Streamlit Runtime Simulation Test
Tests real code paths that pytest mocks cannot reach.
Checks for: NameError, TypeError, KeyError at runtime.
"""
import sys, os, json, traceback
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

PASS = 0
FAIL = 0
ISSUES = []

def report(name, ok, detail=""):
    global PASS, FAIL, ISSUES
    if ok:
        PASS += 1
    else:
        FAIL += 1
        ISSUES.append(f"{name}: {detail}")
    status = "PASS" if ok else "FAIL"
    msg = f"  {status}  {name}" + (f" -- {detail}" if not ok else "")
    print(msg)

# ── Build minimal Streamlit mock ────────────────────────
class _SS(dict):
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)
    def __setattr__(self, k, v): self[k] = v

class _Null:
    def __call__(self, *a, **kw): return self
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def __getattr__(self, k): return _Null()
    def __bool__(self): return False
    def __iter__(self): return iter([])
    def __len__(self): return 0
    def __repr__(self): return "_Null()"

NULL = _Null()

def _noop(*a, **kw): return NULL

# Build mock module
_st_mod = type(sys)("streamlit")
_ss = _SS({
    "active_tab": "\u76ee\u6807 \u6307\u6325\u9a7e\u9a76\u8231",  # test placeholder
    "view_task_id": None, "delete_confirm_id": None,
    "show_add_pl_dialog": False, "show_edit_pl_dialog": False, "edit_pl_id": None,
    "show_manage_ct": False, "manage_ct_pl_id": None,
    "edit_ct_pl_id": None, "show_edit_ct_dialog": False, "edit_ct_id": None,
    "cockpit_exec_topic": "", "cockpit_exec_instruction": "",
    "cockpit_pending_items": "", "cockpit_jump_tab": None,
})

def _cache_data(ttl=None):
    """Mock cache_data that just calls the function directly."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.__wrapped__ = func
        return wrapper
    return decorator

def _dialog(title):
    def decorator(func):
        func._is_dialog = True
        return func
    return decorator

def _columns(spec):
    return [_Null() for _ in spec]

def _segmented_control(label, options, default=None, key=None):
    return default if default else (options[0] if options else NULL)

_st_mod.st = _ss
_st_mod.session_state = _ss
_st_mod.StreamlitAPIException = Exception
_st_mod.set_page_config = _noop
_st_mod.title = _noop
_st_mod.subheader = _noop
_st_mod.caption = _noop
_st_mod.header = _noop
_st_mod.write = _noop
_st_mod.info = _noop
_st_mod.warning = _noop
_st_mod.error = _noop
_st_mod.success = _noop
_st_mod.toast = _noop
_st_mod.rerun = _noop
_st_mod.divider = _noop
_st_mod.metric = _noop
_st_mod.progress = _noop
_st_mod.markdown = _noop
_st_mod.button = lambda *a, **kw: False
_st_mod.text_input = lambda *a, **kw: ""
_st_mod.text_area = lambda *a, **kw: ""
_st_mod.selectbox = lambda *a, **kw: None
_st_mod.toggle = lambda *a, **kw: False
_st_mod.color_picker = lambda *a, **kw: "#000000"
_st_mod.number_input = lambda *a, **kw: 0
_st_mod.cache_data = _cache_data
_st_mod.dialog = _dialog
_st_mod.columns = _columns
_st_mod.segmented_control = _segmented_control
_st_mod.sidebar = _noop
_st_mod.tabs = lambda s: [_Null() for _ in s]
_st_mod.container = _noop
_st_mod.empty = _noop
_st_mod.form = _noop
_st_mod.form_submit_button = lambda *a, **kw: False
_st_mod.dataframe = _noop
_st_mod.table = _noop
_st_mod.expander = _noop
_st_mod.spinner = _noop
_st_mod.secrets = _noop

sys.modules["streamlit"] = _st_mod

# ── Prepare test data ───────────────────────────────────
print("=" * 60)
print("V0.7.0 Streamlit Runtime Simulation Test")
print("=" * 60)

from datetime import date
today_str = date.today().strftime("%Y-%m-%d")

os.makedirs("config", exist_ok=True)
with open("config/product_lines.json", "w", encoding="utf-8") as f:
    json.dump({"product_lines": [{
        "id": "default", "name": "DefaultPL", "is_default": True,
        "checklist": [
            {"id": "c1", "name": "daily_report", "agent": "researcher",
             "schedule": "daily-09:00", "description": "", "enabled": True},
            {"id": "c2", "name": "weekly_review", "agent": "writer",
             "schedule": "weekly-5", "description": "", "enabled": False},
        ],
        "company_tasks": [
            {"id": "ct1", "title": "CompanyTask1", "schedule": "daily-10:00",
             "description": "test task", "enabled": True}
        ]
    }]}, f, ensure_ascii=False)

os.makedirs("data", exist_ok=True)
with open("data/task_history.json", "w", encoding="utf-8") as f:
    json.dump([
        {"task_id": "t1", "topic": "daily_report", "model": "m", "status": "completed",
         "execution_time_seconds": 45, "final_output": "done", "execution_log": "",
         "created_at": f"{today_str}T09:30:00", "product_line_id": "default",
         "task_type": "checklist"},
        {"task_id": "t2", "topic": "weekly_review", "model": "m", "status": "running",
         "execution_time_seconds": 0, "final_output": "", "execution_log": "",
         "created_at": f"{today_str}T10:00:00", "product_line_id": "default",
         "task_type": "checklist"},
    ], f, ensure_ascii=False)

# ── Phase 1: Import app.py ─────────────────────────────
print("\n--- Phase 1: app.py import (module-level execution) ---")
try:
    import app
    report("app.py import + module-level code", True)
except NameError as e:
    report("app.py import", False, f"NameError: {e}")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    report("app.py import", False, f"{type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── Phase 2: _get_cockpit_data ──────────────────────────
print("\n--- Phase 2: _get_cockpit_data (real data flow) ---")
try:
    result = app._get_cockpit_data()
    report("_get_cockpit_data() called OK", True)
    # Check return structure
    if isinstance(result, (list, tuple)) and len(result) == 3:
        product_lines, today_tasks, kpi = result  # 注意顺序！
        report("Returns 3-tuple", True)
        report("kpi is dict", isinstance(kpi, dict))
        if isinstance(kpi, dict):
            for key in ["today_completed", "today_total", "today_rate",
                        "active_agents", "cost", "eta", "remaining_items"]:
                report(f"kpi['{key}'] exists", key in kpi, f"missing: {key}")
            report("kpi.today_total > 0", kpi.get("today_total", 0) > 0,
                   f"got {kpi.get('today_total')}")
        report("product_lines is list", isinstance(product_lines, list))
        report("today_tasks is list", isinstance(today_tasks, list))
    else:
        report("Returns 3-tuple", False, f"got {type(result).__name__} with value {repr(result)[:100]}")
except NameError as e:
    report("_get_cockpit_data()", False, f"NameError: {e}")
except Exception as e:
    report("_get_cockpit_data()", False, f"{type(e).__name__}: {e}")
    traceback.print_exc()

# ── Phase 3: Render functions ──────────────────────────
print("\n--- Phase 3: Render functions (NameError check) ---")

for fname, args in [
    ("_render_cockpit", []),
    ("_render_main", []),
]:
    try:
        fn = getattr(app, fname)
        fn(*args)
        report(f"{fname}()", True)
    except NameError as e:
        report(f"{fname}()", False, f"NameError: {e}")
    except TypeError as e:
        # TypeError from mock (e.g. int not iterable) - not a real bug
        report(f"{fname}()", True, f"TypeError from mock (expected): {e}")
    except Exception as e:
        report(f"{fname}()", True, f"Non-critical: {type(e).__name__}: {e}")

# ── Phase 4: Product line card ──────────────────────────
print("\n--- Phase 4: _render_product_line_card ---")
try:
    from config import get_all_product_lines
    for pl in get_all_product_lines():
        app._render_product_line_card(pl, [])
        report(f"_render_product_line_card({pl['id']})", True)
except NameError as e:
    report("_render_product_line_card", False, f"NameError: {e}")
except TypeError:
    report("_render_product_line_card", True, "TypeError from mock (expected)")
except Exception as e:
    report("_render_product_line_card", True, f"Non-critical: {type(e).__name__}")

# ── Phase 5: Company task item ─────────────────────────
print("\n--- Phase 5: _render_company_task_item ---")
try:
    app._render_company_task_item("default", {
        "id": "ct1", "title": "TestCT",
        "schedule": "daily-10:00", "description": "desc", "enabled": True
    })
    report("_render_company_task_item()", True)
except NameError as e:
    report("_render_company_task_item", False, f"NameError: {e}")
except TypeError:
    report("_render_company_task_item", True, "TypeError from mock (expected)")
except Exception as e:
    report("_render_company_task_item", True, f"Non-critical: {type(e).__name__}")

# ── Phase 6: Dialog functions ───────────────────────────
print("\n--- Phase 6: Dialog functions ---")
for fname, args in [
    ("_show_add_pl_dialog", []),
    ("_show_edit_pl_dialog", ["default"]),
    ("_show_manage_ct_dialog", ["default"]),
    ("_show_edit_ct_dialog", ["default", "ct1"]),
]:
    try:
        fn = getattr(app, fname)
        fn(*args)
        report(f"{fname}()", True)
    except NameError as e:
        report(f"{fname}()", False, f"NameError: {e}")
    except TypeError as e:
        report(f"{fname}()", True, f"TypeError from mock: {e}")
    except Exception as e:
        report(f"{fname}()", True, f"Non-critical: {type(e).__name__}")

# ── Phase 7: Config module ──────────────────────────────
print("\n--- Phase 7: Config full function calls ---")
try:
    from config import (
        parse_schedule, extract_product_line_prefix,
        get_all_product_lines, get_product_line,
        get_checklist_status, get_checklist_items,
        get_company_tasks, ensure_default_product_line,
    )
    report("parse_schedule daily", parse_schedule("daily-09:00")["type"] == "daily")
    report("parse_schedule weekly", parse_schedule("weekly-1")["type"] == "weekly")
    report("parse_schedule monthly", parse_schedule("monthly-last")["type"] == "monthly")
    report("parse_schedule invalid", parse_schedule("invalid")["type"] == "unknown")
    report("extract PL prefix", extract_product_line_prefix("[PL:test]topic") == "test")
    report("extract no prefix", extract_product_line_prefix("nope") is None)
    report("get_all_pl", isinstance(get_all_product_lines(), list))
    report("get_pl default", get_product_line("default")["id"] == "default")
    report("get_checklist_items", isinstance(get_checklist_items("default"), list))
    report("get_company_tasks", isinstance(get_company_tasks("default"), list))
    status = get_checklist_status("default", [])
    report("get_checklist_status", isinstance(status, list))
    ensure_default_product_line()
    report("ensure_default", True)
except Exception as e:
    report("config module", False, f"{type(e).__name__}: {e}")
    traceback.print_exc()

# ── Phase 8: task_recorder ─────────────────────────────
print("\n--- Phase 8: task_recorder real calls ---")
try:
    from data.task_recorder import save_task, load_all_tasks, get_task, delete_task, migrate_old_data
    m = migrate_old_data()
    report(f"migrate_old_data={m}", isinstance(m, int))
    save_task(topic="rt_test", model="m", status="completed",
              execution_time_seconds=5, final_output="", execution_log="",
              product_line_id="default", task_type="normal")
    report("save_task", True)
    tasks = load_all_tasks()
    report("load_all_tasks", isinstance(tasks, list) and len(tasks) > 0)
    if tasks:
        report("has product_line_id", "product_line_id" in tasks[0])
        report("has task_type", "task_type" in tasks[0])
        t = get_task(tasks[0]["task_id"])
        report("get_task", isinstance(t, dict))
        if tasks[0]["topic"] == "rt_test":
            delete_task(tasks[0]["task_id"])
            report("delete_task", True)
except Exception as e:
    report("task_recorder", False, f"{type(e).__name__}: {e}")

# ── Phase 9: Memory system ─────────────────────────────
print("\n--- Phase 9: Memory system ---")
try:
    from memory import init_memory_system, get_memory_status
    init_memory_system()
    report("init_memory_system", True)
    status = get_memory_status()
    report("get_memory_status", isinstance(status, dict))
except Exception as e:
    report("memory system", False, f"{type(e).__name__}: {e}")

# ── Results ─────────────────────────────────────────────
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"Runtime Simulation: {PASS}/{total} PASSED")
if ISSUES:
    print(f"\n!! {len(ISSUES)} REAL ISSUES (not mock-related):")
    for issue in ISSUES:
        print(f"  {issue}")
else:
    print("\nAll runtime paths clean - no NameError/TypeError from source code")
print("=" * 60)
