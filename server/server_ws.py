import argparse
import logging
import threading
from queue import Queue, Empty
from threading import Event
from typing import List

import websockets.sync.server

from server.modules.asr_handler import AsrHandler
from server.modules.llm_handler import LLMHandler
from server.modules.tts_siliconflow_handler import TTSSiliconflowHandler
from server.modules.vad_handler import VADHandler
from utils.pipeline_manager import PipelineManager


def setup_and_start_pipeline(args: argparse.Namespace, ws_handler):
    pipeline = PipelineManager()
    handlers = create_handlers(pipeline, args)
    # 在handlers头部追加一个对socket conn的处理handler
    ws_handler.setup(
        should_listen=pipeline.states.should_listen,
        queue_in=pipeline.queues.recv_audio_chunks_queue,
        queue_out=pipeline.queues.send_audio_chunks_queue,
    )
    handlers.insert(0, ws_handler)

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

class WebSocketHandler:
    def __init__(self, websocket, args):
        self.websocket = websocket
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
                    data = self.websocket.recv()
                    if not data:
                        logging.info("No data received, closing connection.")
                        break
                    # logging.debug(f"receiving data {data}")
                    self.queue_in.put(data)
                except Exception as e:
                    logging.error(f"Error receiving data: {e}")
                    print(e)
                    break
        finally:
            self.websocket.close()

    def handle_sending(self):
        """处理从queue_out获取数据并通过conn发送"""
        logging.info("Starting handle_sending...")
        try:
            while True:
                try:
                    data_to_send = self.queue_out.get(timeout=1)
                    if data_to_send:
                        self.websocket.send(data_to_send)
                        # logging.debug(f"Sent {len(data_to_send)} bytes from queue_out.")
                except Empty:
                    pass
                except Exception as e:
                    logging.error(f"Error sending data: {e}")
                    break
        finally:
            self.websocket.close()

    def run(self):
        threading.Thread(target=self.handle_sending).start()
        threading.Thread(target=self.handle_receiving).start()
        self.should_listen.set()


def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s|%(name)s|%(levelname)s - %(message)s',
        encoding='utf-8'
    )
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='WebSocket服务器')
    parser.add_argument('--host', default='localhost', help='服务器地址')
    parser.add_argument('--port', type=int, default=8765, help='服务器端口')
    parser.add_argument('--llm_model_name', default='cosyvoice-v1', help='LLM模型名称')
    parser.add_argument('--llm_base_url', default='', help='LLM模型地址')
    parser.add_argument('--llm_api_key', default='', help='LLM API KEY')
    parser.add_argument('--tts_api_key', default='', help='TTS API KEY')
    args = parser.parse_args()

    """启动WebSocket服务器"""
    logging.info(f"启动WebSocket服务器: {args.host}:{args.port}")
    def echo(websocket):
        for message in websocket:
            websocket.send(message)
    def handle_client(websocket):
        """处理单个客户端连接"""
        logging.info(f"新的客户端连接: {websocket.remote_address}")
        setup_and_start_pipeline(args, WebSocketHandler(websocket, args))
        input(f"新的客户端, 服务中: {websocket.remote_address}")

    with websockets.sync.server.serve(handle_client, args.host, args.port) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
