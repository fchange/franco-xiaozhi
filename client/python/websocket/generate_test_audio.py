import numpy as np
import wave
import argparse
from pathlib import Path


def generate_test_audio(
    output_file: str,
    duration: float = 3.0,
    sample_rate: int = 16000,
    frequency: float = 440.0
) -> None:
    """
    生成测试用的音频文件（正弦波）
    
    Args:
        output_file: 输出文件路径
        duration: 音频时长（秒）
        sample_rate: 采样率
        frequency: 音频频率（Hz）
    """
    # 生成时间序列
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 生成正弦波
    audio_data = np.sin(2 * np.pi * frequency * t)
    
    # 归一化到 16-bit 范围
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # 保存为 WAV 文件
    with wave.open(output_file, 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())


def main():
    parser = argparse.ArgumentParser(description='生成测试音频文件')
    parser.add_argument('--output', default='test_audio.wav', help='输出文件路径')
    parser.add_argument('--duration', type=float, default=3.0, help='音频时长（秒）')
    parser.add_argument('--sample-rate', type=int, default=16000, help='采样率')
    parser.add_argument('--frequency', type=float, default=440.0, help='音频频率（Hz）')
    args = parser.parse_args()
    
    # 确保输出目录存在
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 生成测试音频
    generate_test_audio(
        str(output_path),
        duration=args.duration,
        sample_rate=args.sample_rate,
        frequency=args.frequency
    )
    print(f"已生成测试音频文件：{output_path}")


if __name__ == "__main__":
    main() 