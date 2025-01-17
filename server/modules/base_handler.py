import logging
from time import perf_counter
from typing import Any, Generator
from queue import Queue, Empty
from threading import Event


class BaseHandler:
    """
    管道处理器的基类。每个处理器都有输入和输出队列。
    setup 方法可以用来设置处理器的特定参数。
    要正确停止处理器，设置 stop_event 并在输入队列中放入 b"END" 来避免队列死锁。
    process 方法处理输入队列中的对象，生成的结果会被放入输出队列。
    cleanup 方法处理停止时的清理工作，并在输出队列中放入 b"END"。
    """

    def __init__(self, stop_event: Event):
        """
        初始化处理器
        
        Args:
            stop_event: 用于控制处理器停止的事件
        """
        self.stop_event = stop_event
        self.input_queues = []
        self.output_queues = []
        self._times = []

    def add_input_queue(self, queue: Queue) -> None:
        """添加输入队列"""
        self.input_queues.append(queue)

    def add_output_queue(self, queue: Queue) -> None:
        """添加输出队列"""
        self.output_queues.append(queue)

    def setup(self, *args, **kwargs) -> None:
        """设置处理器参数"""
        pass

    def process(self, data: Any) -> Generator[Any, None, None]:
        """
        处理数据
        
        Args:
            data: 输入数据
            
        Yields:
            处理后的数据
        """
        print("process NotImplementedError")
        raise NotImplementedError

    def run(self) -> None:
        """运行处理器"""
        logging.info(f"Starting {self.__class__.__name__}")
        while not self.stop_event.is_set():
            # 从所有输入队列获取数据
            for queue in self.input_queues:
                try:
                    input_data = queue.get(timeout=0.1)  # 100ms超时
                    if isinstance(input_data, bytes) and input_data == b"END":
                        logging.info(f"{self.__class__.__name__}: 收到停止信号")
                        return
                    
#                     # logging.debug(f"{self.__class__.__name__}: Processing data of size {len(input_data)} bytes")
                    start_time = perf_counter()
                    for output in self.process(input_data):
                        self._times.append(perf_counter() - start_time)
                        if self.last_time > self.min_time_to_debug:
                            logging.info(f"{self.__class__.__name__}: Processing took {self.last_time:.3f} s")
                            
                        # 将输出发送到所有输出队列
                        for out_queue in self.output_queues:
                            out_queue.put(output)
#                             logging.debug(f"{self.__class__.__name__}: Sent output of size {len(output)} bytes")
                            
                        start_time = perf_counter()
                except Empty:
                    continue
                except Exception as e:
                    logging.error(f"Error in {self.__class__.__name__}: {e}", exc_info=True)

        logging.info(f"Stopping {self.__class__.__name__}")
        self.cleanup()
        # 向所有输出队列发送结束信号
        for queue in self.output_queues:
            queue.put(b"END")
            logging.debug(f"{self.__class__.__name__}: Sent END signal")

    @property
    def last_time(self) -> float:
        """获取最后一次处理的耗时"""
        return self._times[-1] if self._times else 0

    @property
    def min_time_to_debug(self) -> float:
        """获取需要记录日志的最小耗时"""
        return 0.001

    def cleanup(self) -> None:
        """清理资源"""
        pass
