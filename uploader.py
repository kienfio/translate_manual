import argparse
import os
import sys
import time
import asyncio
import logging
from typing import Optional
import wave

# 导入LiveKit RTC库
try:
    from livekit import rtc
except ImportError as e:
    logging.error(f"导入LiveKit RTC库失败: {str(e)}. 请确保已安装正确版本的LiveKit库。")
    sys.exit(1)

from token_generator import generate_token
from config.settings import settings

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AudioUploader:
    def __init__(self, room_name: str, identity: str, source_type: str, file_path: Optional[str] = None):
        """
        初始化音频上传器
        
        Args:
            room_name: LiveKit房间名称
            identity: 发布者身份标识
            source_type: 音频源类型 ('mic' 或 'file')
            file_path: 如果source_type为'file'，提供音频文件路径
        """
        self.room_name = room_name
        self.identity = identity
        self.source_type = source_type
        self.file_path = file_path
        self.engine = None
        self.audio_source = None
        self.running = False
        
        # 验证参数
        if source_type == 'file' and (not file_path or not os.path.exists(file_path)):
            raise ValueError(f"文件模式需要有效的文件路径，但提供的路径无效: {file_path}")
        
        if not settings.LIVEKIT_URL:
            raise ValueError("缺少LIVEKIT_URL环境变量")
    
    async def setup(self):
        """设置RTC引擎和音频源"""
        logger.info(f"设置音频上传器: 房间={self.room_name}, 身份={self.identity}")
        
        # 获取发布者访问令牌
        token = generate_token(self.room_name, self.identity, is_publisher=True)
        if not token:
            raise ValueError("无法生成LiveKit访问令牌")
        
        try:
            # 创建RTC引擎
            self.engine = rtc.RtcEngine()
            
            # 连接到房间
            logger.info(f"连接到LiveKit房间: {self.room_name}")
            await self.engine.connect(settings.LIVEKIT_URL, token)
            
            # 设置音频源
            if self.source_type == 'mic':
                logger.info("使用麦克风作为音频源")
                self.audio_source = rtc.MicrophoneAudioSource()
            else:  # file
                logger.info(f"使用文件作为音频源: {self.file_path}")
                
                # 获取文件格式和采样率信息
                with wave.open(self.file_path, 'rb') as wav_file:
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    frame_rate = wav_file.getframerate()
                    logger.info(f"音频文件: 通道数={channels}, 采样率={frame_rate}Hz")
                    
                self.audio_source = rtc.FileAudioSource(
                    file_path=self.file_path,
                    loop=True  # 循环播放文件
                )
        except Exception as e:
            logger.error(f"设置RTC引擎失败: {str(e)}")
            raise
    
    async def start_publishing(self):
        """开始发布音频流"""
        if not self.engine or not self.audio_source:
            raise ValueError("RTC引擎或音频源尚未设置")
        
        self.running = True
        
        try:
            # 启动音频源
            await self.audio_source.start()
            
            # 发布音频轨道
            audio_options = rtc.TrackOption()
            publish_options = rtc.AudioTrackPublishOptions(
                source=self.audio_source,
                track_option=audio_options
            )
            
            logger.info(f"开始发布音频到房间: {self.room_name}")
            await self.engine.local_participant.publish_audio_track("audio_track", publish_options)
            
            # 保持连接
            try:
                while self.running:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("上传被取消")
                self.running = False
            finally:
                await self.cleanup()
        except Exception as e:
            logger.error(f"发布音频失败: {str(e)}")
            await self.cleanup()
            raise
    
    async def cleanup(self):
        """清理资源"""
        logger.info("清理资源...")
        if self.audio_source:
            try:
                await self.audio_source.stop()
            except Exception as e:
                logger.error(f"停止音频源失败: {str(e)}")
        
        if self.engine:
            try:
                await self.engine.disconnect()
            except Exception as e:
                logger.error(f"断开RTC引擎连接失败: {str(e)}")

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='LiveKit音频上传工具')
    parser.add_argument('--room', type=str, required=True, help='LiveKit房间名称 (例如: room-en, room-vi, room-id, room-kr)')
    parser.add_argument('--identity', type=str, required=True, help='发布者身份标识')
    parser.add_argument('--source', type=str, choices=['mic', 'file'], default='mic', help='音频源类型: mic (麦克风) 或 file (文件)')
    parser.add_argument('--file', type=str, help='音频文件路径 (当source=file时必须提供)')
    
    args = parser.parse_args()
    
    if args.source == 'file' and not args.file:
        parser.error("--source=file 时，必须提供 --file 参数")
    
    try:
        uploader = AudioUploader(
            room_name=args.room,
            identity=args.identity,
            source_type=args.source,
            file_path=args.file
        )
        
        await uploader.setup()
        await uploader.start_publishing()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
