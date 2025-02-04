import argparse
import logging
import socket
import threading
from queue import Queue, Empty
from threading import Event

import pyaudio


class AudioClient:
    """音频客户端，用于发送音频数据到服务器"""

    def __init__(self, host: str = "localhost", port: int = 65432):
        self.host = host
        self.port = port
        self.stop_event = Event()
        self.audio_queue = Queue()
        self.EXPECTED_SAMPLE_RATE = 16000  # 添加 EXPECTED_SAMPLE_RATE 常量

        self.socket = None

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

    def microphone_start(self):
        import sounddevice as sd
        def callback(indata, frames: int, time, status):
            if status:
                print("status", status)
                if status.input_overflow:
                    print("Input buffer overflow detected. Consider increasing blocksize.")
            # Convert the audio data to a format suitable for worker.on_audio_frame
            frame = bytes(indata)
            self.socket.sendall(frame)

        # 使用 RawInputStream 替换 InputStream
        send_stream = sd.RawInputStream(
            samplerate=self.EXPECTED_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            callback=callback,
        )
        # 启动一个线程来处理音频流
        threading.Thread(target=send_stream.start).start()

    def play(self):
        self._player = pyaudio.PyAudio()
        self._stream = self._player.open(format=pyaudio.paInt16, channels=1, rate=16000, output=True)

        def play_audio():
            while True:
                try:
                    response = self.socket.recv(1024)
                    self._stream.write(response)
                except Empty:
                    continue
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    break

        threading.Thread(target=play_audio).start()


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
    args = parser.parse_args()

    # 创建客户端实例
    client = AudioClient(host=args.host, port=args.port)

    try:
        # 连接服务器
        client.connect()

        # 麦克风
        client.microphone_start()
        # 播放
        client.play()

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