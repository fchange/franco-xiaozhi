import argparse
import logging
import socket
from queue import Queue, Empty
from threading import Event, Thread
from typing import Optional, List

from server.modules.asr_handler import AsrHandler
from server.modules.llm_handler import LLMHandler
from server.modules.tts_handler import TTSHandler
from server.modules.tts_siliconflow_handler import TTSSiliconflowHandler
from server.modules.vad_handler import VADHandler
from utils.pipeline_manager import PipelineManager


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
    handlers.append(SocketHandler(
        host=args.host,
        port=args.port,
        should_listen=pipeline.states.should_listen,
        queue_in=pipeline.queues.recv_audio_chunks_queue,
        queue_out=pipeline.queues.send_audio_chunks_queue
    ))
    
    # 2. 创建VAD处理器
    vad_handler = VADHandler(stop_event=pipeline.states.stop_event)
    vad_handler.add_input_queue(pipeline.queues.recv_audio_chunks_queue)
    vad_handler.add_output_queue(pipeline.queues.spoken_prompt_queue)
    vad_handler.setup(should_listen=pipeline.states.should_listen)
    pipeline.states.should_listen.set()
    handlers.append(vad_handler)

    # 3. 创建原始音频保存处理器
    # raw_audio_saver = AudioSaverHandler(stop_event=pipeline.states.stop_event)
    # raw_audio_saver.add_input_queue(pipeline.queues.spoken_prompt_queue)
    # raw_audio_saver.setup(
    #     save_dir=args.audio_save_dir,
    #     sample_rate=args.sample_rate,
    #     channels=args.channels
    # )
    # handlers.append(raw_audio_saver)
    
    # 4. asr
    asr_handler = AsrHandler(stop_event=pipeline.states.stop_event)
    asr_handler.add_input_queue(pipeline.queues.spoken_prompt_queue)
    asr_handler.add_output_queue(pipeline.queues.text_prompt_queue)
    asr_handler.setup()
    handlers.append(asr_handler)

    # 5. llm
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

    # 6. tts
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


class SocketHandler:
    """Socket处理器，用于接收音频数据和播放音频数据"""

    def __init__(self, host: str, port: int, should_listen:Event, queue_in: Queue, queue_out: Queue):
        self.host = host
        self.port = port
        self.socket = None
        self.should_listen = should_listen
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.stop_event = Event()

    def run(self):
        """启动Socket处理器，同时处理接收和发送"""
        logging.info("Starting SocketHandler...")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.host, self.port))
        self.socket.listen()
        logging.info(f"Listening on {self.host}:{self.port}")

        while not self.stop_event.is_set():
            try:
                conn, addr = self.socket.accept()
                logging.info(f"Connected by {addr}")
                # 启动一个线程来处理发送数据
                Thread(target=self.handle_sending, args=(conn,)).start()
                # 处理接收数据
                self.handle_receiving(conn)
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"Error accepting connection: {e}")
                if self.stop_event.is_set():
                    break

        self.socket.close()
        logging.info("SocketHandler stopped.")

    def handle_receiving(self, conn: socket.socket):
        self.should_listen.set()
        """处理接收数据并放入queue_in"""
        with conn:
            conn.settimeout(1)
            while not self.stop_event.is_set():
                try:
                    data = conn.recv(1024)
                    if not data:
                        logging.info("No data received, closing connection.")
                        break
                    self.queue_in.put(data)
                except socket.timeout:
                    pass
                except Exception as e:
                    logging.error(f"Error receiving data: {e}")
                    break

    def handle_sending(self, conn: socket.socket):
        """处理从queue_out获取数据并通过conn发送"""
        with conn:
            while not self.stop_event.is_set():
                try:
                    # 从queue_out获取数据并发送
                    data_to_send = self.queue_out.get(timeout=1)
                    if data_to_send:
                        conn.sendall(data_to_send)
                        # logging.debug(f"Sent {len(data_to_send)} bytes from queue_out.")
                except Empty:
                    pass
                except Exception as e:
                    logging.error(f"Error sending data: {e}")
                    break

    def stop(self):
        """停止Socket处理器"""
        self.stop_event.set()
        logging.info("Stopping SocketHandler...")
        if self.socket:
            self.socket.close()

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