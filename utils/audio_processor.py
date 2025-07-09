import json
from typing import Dict, Any, Optional, List
from config.settings import settings

class AudioProcessor:
    """音频处理器，提供音频处理增强功能"""
    
    @staticmethod
    def get_audio_constraints(quality: str = "auto") -> Dict[str, Any]:
        """
        获取音频约束配置
        
        Args:
            quality: 音频质量 (low, medium, high, auto)
        
        Returns:
            音频约束配置
        """
        # 基础约束
        constraints = {
            "echoCancellation": settings.AUDIO_ECHO_CANCELLATION,
            "noiseSuppression": settings.AUDIO_NOISE_SUPPRESSION,
            "autoGainControl": settings.AUDIO_AUTO_GAIN_CONTROL
        }
        
        # 根据质量级别设置音频参数
        if quality == "low":
            constraints.update({
                "sampleRate": 8000,
                "channelCount": 1
            })
        elif quality == "medium":
            constraints.update({
                "sampleRate": 16000,
                "channelCount": 1
            })
        elif quality == "high":
            constraints.update({
                "sampleRate": 44100,
                "channelCount": 2
            })
        # auto模式下不指定采样率和通道数，由浏览器自动选择
        
        return constraints
    
    @staticmethod
    def get_audio_publish_options(quality: str = "auto") -> Dict[str, Any]:
        """
        获取音频发布选项
        
        Args:
            quality: 音频质量 (low, medium, high, auto)
        
        Returns:
            音频发布选项
        """
        # 获取基础音频约束
        audio_constraints = AudioProcessor.get_audio_constraints(quality)
        
        # 构建发布选项
        publish_options = {
            "audioBitrate": AudioProcessor._get_bitrate_for_quality(quality),
            "dtx": True,  # 启用不连续传输，在静音期间减少带宽使用
            "red": True,  # 启用冗余编码，提高弱网环境下的音频质量
            "forceStereo": quality == "high"  # 高质量模式强制立体声
        }
        
        return {
            "audioConstraints": audio_constraints,
            "publishOptions": publish_options
        }
    
    @staticmethod
    def _get_bitrate_for_quality(quality: str) -> int:
        """
        根据质量级别获取比特率
        
        Args:
            quality: 音频质量 (low, medium, high, auto)
        
        Returns:
            音频比特率 (bps)
        """
        if quality == "low":
            return 16000  # 16 kbps
        elif quality == "medium":
            return 32000  # 32 kbps
        elif quality == "high":
            return 64000  # 64 kbps
        else:  # auto
            return 32000  # 默认32 kbps
    
    @staticmethod
    def get_adaptive_quality_settings() -> Dict[str, Any]:
        """
        获取自适应音频质量设置
        
        Returns:
            自适应音频质量设置
        """
        if not settings.AUDIO_QUALITY_ADAPTIVE:
            # 如果未启用自适应质量，返回固定高质量设置
            return AudioProcessor.get_audio_publish_options("high")
        
        # 自适应质量设置
        return {
            "audioConstraints": AudioProcessor.get_audio_constraints("auto"),
            "publishOptions": {
                "dtx": True,
                "red": True,
                "adaptiveStream": True,  # 启用自适应流
                "dynacast": True  # 启用动态广播
            }
        }
    
    @staticmethod
    def get_enhanced_noise_suppression_settings() -> Dict[str, Any]:
        """
        获取增强噪声抑制设置
        
        Returns:
            增强噪声抑制设置
        """
        if not settings.AUDIO_NOISE_SUPPRESSION:
            return {}
        
        # 增强噪声抑制设置
        return {
            "audioConstraints": {
                "noiseSuppression": {
                    "level": "high"  # 高级噪声抑制
                },
                "echoCancellation": settings.AUDIO_ECHO_CANCELLATION,
                "autoGainControl": settings.AUDIO_AUTO_GAIN_CONTROL
            }
        }
    
    @staticmethod
    def get_javascript_audio_settings() -> str:
        """
        获取JavaScript格式的音频设置代码
        
        Returns:
            JavaScript代码字符串
        """
        # 获取自适应质量设置
        adaptive_settings = AudioProcessor.get_adaptive_quality_settings()
        
        # 获取增强噪声抑制设置
        noise_suppression_settings = AudioProcessor.get_enhanced_noise_suppression_settings()
        
        # 合并设置
        merged_settings = {
            "audioConstraints": {
                **adaptive_settings.get("audioConstraints", {}),
                **noise_suppression_settings.get("audioConstraints", {})
            },
            "publishOptions": adaptive_settings.get("publishOptions", {})
        }
        
        # 转换为JavaScript代码
        js_code = f"""
// 音频处理增强设置
const audioSettings = {json.dumps(merged_settings, indent=2)};

// 创建音频轨道函数
async function createEnhancedAudioTrack() {{
  try {{
    // 请求麦克风权限并创建音频轨道
    const audioTrack = await LivekitClient.createLocalAudioTrack(audioSettings.audioConstraints);
    console.log('✅ 增强音频轨道创建成功');
    return audioTrack;
  }} catch (error) {{
    console.error('❌ 创建增强音频轨道失败:', error);
    // 如果增强设置失败，尝试使用基本设置
    try {{
      console.log('⚠️ 尝试使用基本设置创建音频轨道');
      const basicTrack = await LivekitClient.createLocalAudioTrack({{
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }});
      return basicTrack;
    }} catch (fallbackError) {{
      console.error('❌ 使用基本设置创建音频轨道也失败:', fallbackError);
      throw fallbackError;
    }}
  }}
}}

// 发布音频轨道函数
async function publishEnhancedAudioTrack(room, audioTrack) {{
  if (!room || !audioTrack) return null;
  
  try {{
    // 使用增强发布选项发布音频轨道
    const trackPublication = await room.localParticipant.publishTrack(
      audioTrack, 
      audioSettings.publishOptions
    );
    console.log('✅ 增强音频轨道发布成功');
    return trackPublication;
  }} catch (error) {{
    console.error('❌ 发布增强音频轨道失败:', error);
    // 如果增强发布失败，尝试使用基本设置
    try {{
      console.log('⚠️ 尝试使用基本设置发布音频轨道');
      const basicPublication = await room.localParticipant.publishTrack(audioTrack);
      return basicPublication;
    }} catch (fallbackError) {{
      console.error('❌ 使用基本设置发布音频轨道也失败:', fallbackError);
      throw fallbackError;
    }}
  }}
}}
"""
        return js_code
    
    @staticmethod
    def get_audio_stats_collector_js() -> str:
        """
        获取音频统计收集器的JavaScript代码
        
        Returns:
            JavaScript代码字符串
        """
        js_code = """
// 音频统计收集器
class AudioStatsCollector {
  constructor(room) {
    this.room = room;
    this.statsInterval = null;
    this.localStats = {};
    this.remoteStats = {};
    this.onStatsUpdate = null;
  }
  
  // 开始收集统计信息
  startCollecting(intervalMs = 2000) {
    if (this.statsInterval) {
      this.stopCollecting();
    }
    
    this.statsInterval = setInterval(() => {
      this.collectStats();
    }, intervalMs);
  }
  
  // 停止收集统计信息
  stopCollecting() {
    if (this.statsInterval) {
      clearInterval(this.statsInterval);
      this.statsInterval = null;
    }
  }
  
  // 设置统计更新回调
  setStatsUpdateCallback(callback) {
    this.onStatsUpdate = callback;
  }
  
  // 收集统计信息
  async collectStats() {
    if (!this.room) return;
    
    try {
      // 收集本地参与者统计
      if (this.room.localParticipant) {
        const localAudioPublications = Array.from(this.room.localParticipant.audioTracks.values());
        
        for (const pub of localAudioPublications) {
          if (pub.track) {
            const trackStats = await pub.track.getStats();
            this.localStats[pub.trackSid] = this.processAudioStats(trackStats);
          }
        }
      }
      
      // 收集远程参与者统计
      this.room.participants.forEach(async (participant) => {
        const audioSubscriptions = Array.from(participant.audioTracks.values());
        
        for (const sub of audioSubscriptions) {
          if (sub.track) {
            const trackStats = await sub.track.getStats();
            this.remoteStats[sub.trackSid] = {
              ...this.processAudioStats(trackStats),
              participantId: participant.identity
            };
          }
        }
      });
      
      // 调用回调函数
      if (this.onStatsUpdate) {
        this.onStatsUpdate({
          local: this.localStats,
          remote: this.remoteStats
        });
      }
    } catch (error) {
      console.error('收集音频统计信息失败:', error);
    }
  }
  
  // 处理音频统计数据
  processAudioStats(rawStats) {
    const stats = {
      timestamp: Date.now(),
      packetsLost: 0,
      packetsReceived: 0,
      bytesReceived: 0,
      jitter: 0,
      audioLevel: 0,
      bitrate: 0,
      lastResult: null
    };
    
    if (!rawStats || !rawStats.length) {
      return stats;
    }
    
    for (const stat of rawStats) {
      if (stat.type === 'inbound-rtp' && stat.kind === 'audio') {
        stats.packetsLost = stat.packetsLost || 0;
        stats.packetsReceived = stat.packetsReceived || 0;
        stats.bytesReceived = stat.bytesReceived || 0;
        stats.jitter = stat.jitter || 0;
        
        // 计算丢包率
        if (stats.packetsReceived > 0) {
          stats.packetLossRate = (stats.packetsLost / (stats.packetsReceived + stats.packetsLost)) * 100;
        }
        
        // 计算比特率
        if (stats.lastResult && stats.lastResult.bytesReceived) {
          const byteDiff = stats.bytesReceived - stats.lastResult.bytesReceived;
          const timeDiff = (stats.timestamp - stats.lastResult.timestamp) / 1000;
          if (timeDiff > 0) {
            stats.bitrate = (byteDiff * 8) / timeDiff; // bps
          }
        }
      } else if (stat.type === 'outbound-rtp' && stat.kind === 'audio') {
        stats.packetsSent = stat.packetsSent || 0;
        stats.bytesSent = stat.bytesSent || 0;
        
        // 计算比特率
        if (stats.lastResult && stats.lastResult.bytesSent) {
          const byteDiff = stats.bytesSent - stats.lastResult.bytesSent;
          const timeDiff = (stats.timestamp - stats.lastResult.timestamp) / 1000;
          if (timeDiff > 0) {
            stats.bitrate = (byteDiff * 8) / timeDiff; // bps
          }
        }
      } else if (stat.type === 'media-source' && stat.kind === 'audio') {
        stats.audioLevel = stat.audioLevel || 0;
      }
    }
    
    stats.lastResult = {
      bytesReceived: stats.bytesReceived,
      bytesSent: stats.bytesSent,
      timestamp: stats.timestamp
    };
    
    return stats;
  }
  
  // 获取当前统计信息
  getStats() {
    return {
      local: this.localStats,
      remote: this.remoteStats
    };
  }
}
"""
        return js_code

# 创建全局音频处理器实例
audio_processor = AudioProcessor() 