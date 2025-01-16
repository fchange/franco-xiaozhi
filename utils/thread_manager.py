import threading
from typing import List


class ThreadManager:
    """
    统一管理多个线程的工具类。
    用于执行给定的handler任务。
    """

    def __init__(self, handlers: List):
        """
        初始化线程管理器
        
        Args:
            handlers: 需要在独立线程中运行的handler列表
        """
        self.handlers = handlers
        self.threads = []

    def start(self):
        """
        启动所有handler对应的线程
        """
        for handler in self.handlers:
            thread = threading.Thread(target=handler.run)
            thread.daemon = True  # 设置为守护线程，这样主程序退出时线程会自动结束
            self.threads.append(thread)
            thread.start()

    def stop(self):
        """
        停止所有正在运行的线程
        通过设置handler的stop_event来实现优雅停止
        """
        for handler in self.handlers:
            if hasattr(handler, 'stop_event'):
                handler.stop_event.set()
        
        for thread in self.threads:
            thread.join()
        
        self.threads.clear()

    def is_alive(self) -> bool:
        """
        检查是否有线程仍在运行
        
        Returns:
            bool: 如果有任何线程仍在运行则返回True，否则返回False
        """
        return any(thread.is_alive() for thread in self.threads) 