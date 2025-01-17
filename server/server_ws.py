import logging

# 设置日志配置
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler('server.log')  # 同时保存到文件
    ]
)

import os
import sys

# 将项目根目录添加到Python路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

import socket
from threading import Event
from queue import Queue
import argparse
from typing import Optional, List

from utils.pipeline_manager import PipelineManager
from server.modules.audio_saver import AudioSaverHandler
from server.modules.vad_handler import VADHandler
from server.modules.asr_handler import AsrHandler


def create_handlers(pipeline: PipelineManager, args: argparse.Namespace) -> List:
    """
    创建处理器列表
    
    Args:
        pipeline: 管道管理器实例
        args: 命令行参数

    Returns:
        List: 处理器列表
    """
    handlers = []
    
    # 1. 创建Socket接收器
    receiver = SocketReceiver(
        host=args.host,
        port=args.port,
        queue=pipeline.queues.recv_audio_chunks_queue
    )
    handlers.append(receiver)
    
    # 2. 创建VAD处理器
    vad_handler = VADHandler(stop_event=pipeline.states.stop_event)
    vad_handler.add_input_queue(pipeline.queues.recv_audio_chunks_queue)
    vad_handler.add_output_queue(pipeline.queues.spoken_prompt_queue)
    vad_handler.setup(should_listen=pipeline.states.should_listen)
    pipeline.states.should_listen.set()
    handlers.append(vad_handler)

    # 3. 创建原始音频保存处理器
    raw_audio_saver = AudioSaverHandler(stop_event=pipeline.states.stop_event)
    raw_audio_saver.add_input_queue(pipeline.queues.spoken_prompt_queue)
    raw_audio_saver.setup(
        save_dir=args.audio_save_dir,
        sample_rate=args.sample_rate,
        channels=args.channels
    )
    handlers.append(raw_audio_saver)
    
    # 4. asr
    asr_handler = AsrHandler(stop_event=pipeline.states.stop_event)
    asr_handler.add_input_queue(pipeline.queues.spoken_prompt_queue)
    asr_handler.add_output_queue(pipeline.queues.text_prompt_queue)
    asr_handler.setup()
    handlers.append(asr_handler)
    
    return handlers


class SocketReceiver:
    """Socket接收器，用于接收音频数据"""
    
    def __init__(self, host: str, port: int, queue: Queue):
        self.host = host
        self.port = port
        self.queue = queue
        self.stop_event = Event()

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            s.settimeout(1)  # 设置超时，这样可以定期检查stop_event
            
            while not self.stop_event.is_set():
                try:
                    conn, addr = s.accept()
                    logging.info(f"Connected by {addr}")
                    with conn:
                        conn.settimeout(1)
                        while not self.stop_event.is_set():
                            try:
                                data = conn.recv(1024)
                                if not data:
                                    break
                                self.queue.put(data)
                            except socket.timeout:
                                continue
                            except Exception as e:
                                logging.error(f"Error receiving data: {e}")
                                break
                except socket.timeout:
                    continue
                except Exception as e:
                    logging.error(f"Error accepting connection: {e}")
                    if self.stop_event.is_set():
                        break


class SocketSender:
    """Socket发送器，用于发送音频数据"""
    
    def __init__(self, host: str, port: int, queue: Optional[Queue] = None):
        self.host = host
        self.port = port
        self.queue = queue
        self.stop_event = Event()

    def send(self, data: bytes) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                s.sendall(data)
        except Exception as e:
            logging.error(f"Error sending data: {e}")

    def run(self):
        if self.queue is None:
            return
            
        while not self.stop_event.is_set():
            try:
                data = self.queue.get(timeout=1)
                self.send(data)
            except Exception:
                continue


def main():
    """主函数"""
    # 设置日志级别为DEBUG以查看更详细的信息
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='语音对话服务器')
    # 服务器配置
    parser.add_argument('--host', default='localhost', help='服务器地址')
    parser.add_argument('--port', type=int, default=65432, help='服务器端口')
    
    # 音频配置
    parser.add_argument('--audio-save-dir', default='audio_saves', help='音频保存目录')
    parser.add_argument('--sample-rate', type=int, default=16000, help='音频采样率')
    parser.add_argument('--channels', type=int, default=1, help='音频声道数')
    
    # VAD配置
    parser.add_argument('--chunk-size', type=int, default=200, help='VAD处理的音频块大小(ms)')
    parser.add_argument('--min-speech-ms', type=int, default=300, help='最小语音时长(ms)')
    
    args = parser.parse_args()
    
    # 创建并配置管道
    pipeline = PipelineManager()
    try:
        # 创建处理器列表
        handlers = create_handlers(pipeline, args)
        
        # 构建处理管道
        pipeline.build_pipeline(handlers)
        
        # 启动管道
        logging.info(f"Starting server on {args.host}:{args.port}")
        pipeline.start()
        
        # 等待用户中断
        try:
            input("按回车键停止服务器...\n")
        except KeyboardInterrupt:
            logging.info("接收到停止信号")
        
    finally:
        # 停止管道
        logging.info("正在停止服务器...")
        pipeline.stop()
        logging.info("服务器已停止")


if __name__ == "__main__":
    main()