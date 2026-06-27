import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import Store, HierarchicalStore


def test_store_save_and_load():
    """Test basic Store save and load operations."""
    store = Store()
    store.save("key1", "value1")
    assert store.load("key1") == "value1"
    assert store.load("nonexistent") is None
    print("[PASS] test_store_save_and_load")


def test_store_delete_and_list():
    """Test Store delete and list operations."""
    store = Store()
    store.save("a", 1)
    store.save("b", 2)
    store.save("c", 3)
    assert len(store.list_keys()) == 3
    store.delete("b")
    assert len(store.list_keys()) == 2
    assert store.load("b") is None
    print("[PASS] test_store_delete_and_list")


def test_hierarchical_store_readonly():
    """Test HierarchicalStore read-only key protection."""
    parent = HierarchicalStore(Store(), readonly_keys={"const.rule"})
    parent.save("const.rule", "cannot_be_changed")
    child = HierarchicalStore(Store(), parent=parent, readonly_keys={"const.rule"})
    assert child.load("const.rule") == "cannot_be_changed"
    try:
        child.save("const.rule", "try_to_modify")
        assert False, "Should raise PermissionError"
    except PermissionError:
        pass
    print("[PASS] test_hierarchical_store_readonly")


def test_hierarchical_store_merge_from():
    """Test HierarchicalStore merge_from operation."""
    parent = HierarchicalStore(Store())
    child_store = Store()
    child_store.save("result", "output_data")
    child_store.save("temp", "temporary_data")
    parent.merge_from(child_store, filter_func=lambda k: k == "result")
    assert parent.load("result") == "output_data"
    assert parent.load("temp") is None
    print("[PASS] test_hierarchical_store_merge_from")


if __name__ == "__main__":
    test_store_save_and_load()
    test_store_delete_and_list()
    test_hierarchical_store_readonly()
    test_hierarchical_store_merge_from()
    print("\n[ALL PASS] All Store tests passed!")
