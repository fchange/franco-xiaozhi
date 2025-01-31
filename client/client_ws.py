import logging
import threading

import pyaudio
import sounddevice as sd
from websockets.sync.client import connect


class AudioClient:
    def __init__(self, url: str = "ws://localhost:8765"):
        self.url = url
        self.EXPECTED_SAMPLE_RATE = 16000

        self.websocket = None
        self._player = None
        self._stream = None

    def start(self):
        """启动客户端"""
        try:
            logging.info(f"连接服务器: {self.url}")
            with connect(self.url) as websocket:
                self.websocket = websocket
                logging.info("已连接到服务器")

                # 麦克风
                threading.Thread(target=self.microphone_start, daemon=True).start()
                # 播放
                threading.Thread(target=self.play, daemon=True).start()

                input("按回车键停止客户端...\n")

        except Exception as e:
            logging.error(f"连接错误: {e}")

    def microphone_start(self):
        def callback(indata, frames: int, time, status):
            if status:
                print("status", status)
                if status.input_overflow:
                    print("Input buffer overflow detected. Consider increasing blocksize.")
            # Convert the audio data to a format suitable for worker.on_audio_frame
            frame = bytes(indata)
            self.websocket.send(frame)

        # 使用 RawInputStream 替换 InputStream
        send_stream = sd.RawInputStream(
            samplerate=self.EXPECTED_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            callback=callback,
        )
        send_stream.start()

    def play(self):
        self._player = pyaudio.PyAudio()
        self._stream = self._player.open(format=pyaudio.paInt16, channels=1, rate=16000, output=True)
        while True:
            try:
                response = self.websocket.recv()
                self._stream.write(response)
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s|%(name)s|%(levelname)s - %(message)s',
        encoding='utf-8'
    )
    
    client = AudioClient()
    try:
        client.start()
    except KeyboardInterrupt:
        logging.info("用户中断，正在退出...")


if __name__ == "__main__":
    main()
