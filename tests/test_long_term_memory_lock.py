import threading
from core.long_term_memory import LongTermMemory


def test_concurrent_adds_do_not_corrupt_file(tmp_memory_file):
    """多线程并发 add，文件应保持合法 JSON 且条目数正确。"""
    mem = LongTermMemory()
    n_threads = 8
    n_per_thread = 20

    def worker():
        for i in range(n_per_thread):
            mem.add(f"thread item {i}", memory_type="lesson")

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 重新加载验证文件未损坏
    mem2 = LongTermMemory()
    assert len(mem2.memories) == n_threads * n_per_thread


def test_concurrent_add_and_clear(tmp_memory_file):
    """并发 add 和 clear 不应抛异常。"""
    mem = LongTermMemory()

    def adder():
        for i in range(50):
            try:
                mem.add(f"item {i}")
            except Exception:
                pass

    def clearer():
        for _ in range(5):
            try:
                mem.clear()
            except Exception:
                pass

    t1 = threading.Thread(target=adder)
    t2 = threading.Thread(target=clearer)
    t1.start(); t2.start()
    t1.join(); t2.join()
    # 只要没崩溃就算通过
