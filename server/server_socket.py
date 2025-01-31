import argparse
import asyncio
import logging
import socket
import threading
from queue import Empty, Queue
from threading import Event
from typing import List

from server.modules.asr_handler import AsrHandler
from server.modules.llm_handler import LLMHandler
from server.modules.tts_siliconflow_handler import TTSSiliconflowHandler
from server.modules.vad_handler import VADHandler
from utils.pipeline_manager import PipelineManager


def setup_and_start_pipeline(args: argparse.Namespace, socket_handler):
    pipeline = PipelineManager()
    handlers = create_handlers(pipeline, args)
    # 在handlers头部追加一个对socket conn的处理handler
    socket_handler.setup(
        should_listen=pipeline.states.should_listen,
        queue_in=pipeline.queues.recv_audio_chunks_queue,
        queue_out=pipeline.queues.send_audio_chunks_queue,
    )
    handlers.insert(0, socket_handler)

    pipeline.build_pipeline(handlers)
    pipeline.start()


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
    
    # 1. 创建VAD处理器
    vad_handler = VADHandler(stop_event=pipeline.states.stop_event)
    vad_handler.add_input_queue(pipeline.queues.recv_audio_chunks_queue)
    vad_handler.add_output_queue(pipeline.queues.spoken_prompt_queue)
    vad_handler.setup(should_listen=pipeline.states.should_listen)
    pipeline.states.should_listen.set()
    handlers.append(vad_handler)

    # 2. 创建原始音频保存处理器
    # raw_audio_saver = AudioSaverHandler(stop_event=pipeline.states.stop_event)
    # raw_audio_saver.add_input_queue(pipeline.queues.spoken_prompt_queue)
    # raw_audio_saver.setup(
    #     save_dir=args.audio_save_dir,
    #     sample_rate=args.sample_rate,
    #     channels=args.channels
    # )
    # handlers.append(raw_audio_saver)
    
    # 3. asr
    asr_handler = AsrHandler(stop_event=pipeline.states.stop_event)
    asr_handler.add_input_queue(pipeline.queues.spoken_prompt_queue)
    asr_handler.add_output_queue(pipeline.queues.text_prompt_queue)
    asr_handler.setup()
    handlers.append(asr_handler)

    # 4. llm
    llm_handler = LLMHandler(stop_event=pipeline.states.stop_event)
    llm_handler.add_input_queue(pipeline.queues.text_prompt_queue)
    llm_handler.add_output_queue(pipeline.queues.lm_response_queue)
    llm_handler.setup(
        model_name=args.llm_model_name,
        base_url=args.llm_base_url,
        api_key=args.llm_api_key,
        stream=True,
    )
    handlers.append(llm_handler)

    # 5. tts
    # tts_handler = TTSHandler(stop_event=pipeline.states.stop_event)
    tts_handler = TTSSiliconflowHandler(stop_event=pipeline.states.stop_event)
    tts_handler.add_input_queue(pipeline.queues.lm_response_queue)
    tts_handler.add_output_queue(pipeline.queues.send_audio_chunks_queue)
    tts_handler.setup(
        api_key=args.tts_api_key,
        should_listen=pipeline.states.should_listen,
    )
    handlers.append(tts_handler)

    return handlers


class SocketServerHandler:
    """Socket处理器，用于接收音频数据和播放音频数据"""

    def __init__(self, args: argparse.Namespace):
        self.host = args.host
        self.port = args.port
        self.socket = None
        self.args = args

    def run(self):
        """启动Socket处理器，同时处理接收和发送"""
        logging.info("Starting SocketHandler...")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.host, self.port))
        self.socket.listen()
        logging.info(f"Listening on {self.host}:{self.port}")
        while True:
            try:
                conn, addr = self.socket.accept()
                logging.info(f"Connected by {addr}")

                # 使用新的函数来设置和启动管道
                setup_and_start_pipeline(args=self.args, socket_handler=SocketHandler(socket = conn, args = self.args))
            except Exception as e:
                logging.error(f"Error accepting connection: {e}")

class SocketHandler:
    def __init__(self, socket=None, args: argparse.Namespace=None):
        self.socket = socket
        self.args = args
        self.should_listen = None
        self.queue_in = None
        self.queue_out = None

    def setup(self, should_listen: Event, queue_in: Queue, queue_out: Queue):
        self.should_listen = should_listen
        self.queue_in = queue_in
        self.queue_out = queue_out

    def handle_receiving(self):
        """处理接收数据并放入queue_in"""
        logging.info("Starting handle_receiving...")
        try:
            while True:
                try:
                    data = self.socket.recv(1024)
                    if not data:
                        logging.info("No data received, closing connection.")
                        break
                    self.queue_in.put(data)
                except socket.timeout:
                    pass
                except Exception as e:
                    logging.error(f"Error receiving data: {e}")
                    break
        finally:
            self.socket.close()

    def handle_sending(self):
        """处理从queue_out获取数据并通过conn发送"""
        logging.info("Starting handle_sending...")
        try:
            while True:
                try:
                    data_to_send = self.queue_out.get(timeout=1)
                    if data_to_send:
                        self.socket.sendall(data_to_send)
                        logging.debug(f"Sent {len(data_to_send)} bytes from queue_out.")
                except Empty:
                    pass
                except Exception as e:
                    logging.error(f"Error sending data: {e}")
                    break
        finally:
            self.socket.close()

    def run(self):
        logging.info("Starting SocketHandler...")
        threading.Thread(target=self.handle_sending).start()
        threading.Thread(target=self.handle_receiving).start()
        self.should_listen.set()

def main():
    """主函数"""
    # 设置日志级别为DEBUG以查看更详细的信息
    logging.basicConfig(
        level=logging.DEBUG,
        # level=logging.INFO,
        format='%(asctime)s|%(name)s|%(levelname)s - %(message)s',
        encoding='utf-8',
        handlers=[
            logging.StreamHandler(),  # 输出到控制台
        ]
    )
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='语音对话服务器')
    # 服务器配置
    parser.add_argument('--host', default='localhost', help='服务器地址')
    parser.add_argument('--port', type=int, default=65432, help='服务器端口')
    # 音频配置
    parser.add_argument('--audio-save-dir', default='audio_saves', help='音频保存目录')
    # llm
    parser.add_argument('--llm_model_name', default='cosyvoice-v1', help='LLM模型名称')
    parser.add_argument('--llm_base_url', default='', help='LLM模型地址')
    parser.add_argument('--llm_api_key', default='', help='LLM API KEY')
    # tts
    parser.add_argument('--tts_api_key', default='', help='TTS API KEY')
    args = parser.parse_args()

    # WebSocket处理器
    SocketServerHandler(args=args).run()

if __name__ == "__main__":
    main()