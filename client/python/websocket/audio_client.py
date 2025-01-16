import os
import sys
import socket
import logging
import argparse
from pathlib import Path
from threading import Thread, Event
from queue import Queue
from typing import Optional


class AudioClient:
    """音频客户端，用于发送音频数据到服务器"""
    
    def __init__(self, host: str = "localhost", port: int = 65432):
        self.host = host
        self.port = port
        self.stop_event = Event()
        self.audio_queue = Queue()
        
    def connect(self) -> None:
        """连接到服务器"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
            logging.info(f"Connected to server at {self.host}:{self.port}")
        except Exception as e:
            logging.error(f"Failed to connect to server: {e}")
            raise
            
    def disconnect(self) -> None:
        """断开与服务器的连接"""
        if hasattr(self, 'socket'):
            self.socket.close()
            logging.info("Disconnected from server")
            
    def send_audio_file(self, audio_file: str, chunk_size: int = 1024) -> None:
        """
        发送音频文件到服务器
        
        Args:
            audio_file: 音频文件路径
            chunk_size: 每次发送的数据大小
        """
        try:
            with open(audio_file, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.socket.sendall(chunk)
            logging.info(f"Finished sending audio file: {audio_file}")
        except Exception as e:
            logging.error(f"Error sending audio file: {e}")
            raise
            
    def send_audio_data(self, audio_data: bytes) -> None:
        """
        发送音频数据到服务器
        
        Args:
            audio_data: 音频数据字节
        """
        try:
            self.socket.sendall(audio_data)
        except Exception as e:
            logging.error(f"Error sending audio data: {e}")
            raise


def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='音频客户端')
    parser.add_argument('--host', default='localhost', help='服务器地址')
    parser.add_argument('--port', type=int, default=65432, help='服务器端口')
    parser.add_argument('--audio-file', type=str, help='要发送的音频文件路径')
    args = parser.parse_args()
    
    # 创建客户端实例
    client = AudioClient(host=args.host, port=args.port)
    
    try:
        # 连接服务器
        client.connect()
        
        # 如果指定了音频文件，就发送它
        if args.audio_file:
            if not os.path.exists(args.audio_file):
                raise FileNotFoundError(f"Audio file not found: {args.audio_file}")
            client.send_audio_file(args.audio_file)
        else:
            # 等待用户输入，用于测试连接
            input("按回车键停止客户端...\n")
            
    except KeyboardInterrupt:
        logging.info("接收到停止信号")
    except Exception as e:
        logging.error(f"发生错误: {e}")
    finally:
        # 断开连接
        client.disconnect()


if __name__ == "__main__":
    main() 