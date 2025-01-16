from dataclasses import dataclass
from queue import Queue
from threading import Event
from typing import Dict, Any, Optional, List

from utils.thread_manager import ThreadManager


@dataclass
class PipelineQueues:
    """管理语音对话管道中的所有队列"""
    # 音频输入输出队列
    recv_audio_chunks_queue: Queue  # 原始音频输入队列
    send_audio_chunks_queue: Queue  # 最终音频输出队列
    
    # VAD和ASR相关队列
    spoken_prompt_queue: Queue  # VAD处理后的有效语音片段队列
    text_prompt_queue: Queue   # ASR输出的文本队列
    
    # LLM相关队列
    lm_response_queue: Queue   # LLM的响应队列


@dataclass
class PipelineStates:
    """管理语音对话管道中的所有状态
    
    状态流转说明：
    1. stop_event: 全局停止事件
       - 初始为 False
       - 当需要停止整个管道时设置为 True
       - 所有处理器需要定期检查此状态，收到 True 时优雅退出
    
    2. should_listen: 控制音频输入状态
       - 初始为 True（允许接收音频输入）
       - True: 系统正在监听用户输入
         a) VAD模块处理音频输入
         b) 允许接收新的音频数据
         c) ASR模块可以处理音频
       - False: 系统正在输出（说话），此时：
         a) 暂停接收新的音频输入，避免录到系统自己的声音
         b) VAD模块暂停处理
         c) ASR模块可以继续处理已在队列中的音频
         d) LLM模块可以继续处理已在队列中的文本
    
    3. 典型的状态流转顺序：
       a) 初始状态：
          - should_listen = True（系统开始监听）
          - VAD开始处理音频
       
       b) 检测到用户说话：
          - should_listen 保持 True
          - VAD处理音频并输出到 spoken_prompt_queue
          - ASR处理音频生成文本到 text_prompt_queue
          - LLM处理文本生成响应到 lm_response_queue
       
       c) 系统开始回复：
          - should_listen = False（停止接收新输入）
          - TTS处理LLM响应并播放
       
       d) 系统回复完成：
          - should_listen = True（重新开始监听）
          - 回到步骤a
    """
    stop_event: Event      # 全局停止事件
    should_listen: Event   # 是否应该监听音频输入（False时表示系统正在输出）
    current_session_id: str = ""  # 当前会话ID


class PipelineManager:
    """管理整个语音对话管道的核心类"""
    
    def __init__(self):
        # 初始化所有队列
        self.queues = PipelineQueues(
            recv_audio_chunks_queue=Queue(),
            send_audio_chunks_queue=Queue(),
            spoken_prompt_queue=Queue(),
            text_prompt_queue=Queue(),
            lm_response_queue=Queue()
        )
        
        # 初始化所有状态
        self.states = PipelineStates(
            stop_event=Event(),
            should_listen=Event()
        )
        # 默认开启监听
        self.states.should_listen.set()
        
        # 初始化线程管理器
        self.thread_manager = None
        
        # 存储所有处理器
        self.handlers = []

    def build_pipeline(self, handlers: List[Any]) -> None:
        """
        构建处理管道
        
        Args:
            handlers: 处理器列表，每个处理器需要实现 run 方法
        """
        self.handlers = handlers
        self.thread_manager = ThreadManager(self.handlers)

    def start(self):
        """启动管道"""
        if self.thread_manager:
            self.thread_manager.start()
        else:
            raise RuntimeError("Pipeline not built yet. Call build_pipeline first.")

    def stop(self):
        """停止管道"""
        if self.thread_manager:
            self.states.stop_event.set()
            self.thread_manager.stop()

    @property
    def queues_dict(self) -> Dict[str, Queue]:
        """获取所有队列的字典表示"""
        return {
            "recv_audio_chunks_queue": self.queues.recv_audio_chunks_queue,
            "send_audio_chunks_queue": self.queues.send_audio_chunks_queue,
            "spoken_prompt_queue": self.queues.spoken_prompt_queue,
            "text_prompt_queue": self.queues.text_prompt_queue,
            "lm_response_queue": self.queues.lm_response_queue
        }

    @property
    def states_dict(self) -> Dict[str, Any]:
        """获取所有状态的字典表示"""
        return {
            "stop_event": self.states.stop_event,
            "should_listen": self.states.should_listen,
            "current_session_id": self.states.current_session_id
        } 