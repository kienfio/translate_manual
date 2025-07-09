import os
from dotenv import load_dotenv
import json
from typing import List, Dict, Optional, Any

# 尝试加载.env文件，但在Render部署时会使用环境变量
load_dotenv()

class Settings:
    # LiveKit配置
    LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
    LIVEKIT_SECRET = os.getenv('LIVEKIT_SECRET')
    LIVEKIT_URL = os.getenv('LIVEKIT_URL')  # 例如: wss://your-project.livekit.cloud
    
    # 服务器配置
    PORT = int(os.getenv('PORT', '8000'))
    
    # 多区域部署配置
    MULTI_REGION = os.getenv('MULTI_REGION', 'false').lower() == 'true'
    REGION = os.getenv('REGION', 'default')
    REGIONS_CONFIG = json.loads(os.getenv('REGIONS_CONFIG', '{}'))
    
    # 安全审计配置
    AUDIT_ENABLED = os.getenv('AUDIT_ENABLED', 'true').lower() == 'true'
    AUDIT_LOG_PATH = os.getenv('AUDIT_LOG_PATH', './logs/audit.log')
    AUDIT_LOG_LEVEL = os.getenv('AUDIT_LOG_LEVEL', 'INFO')
    
    # 录制配置
    RECORDING_ENABLED = os.getenv('RECORDING_ENABLED', 'false').lower() == 'true'
    RECORDING_STORAGE_PATH = os.getenv('RECORDING_STORAGE_PATH', './recordings')
    RECORDING_STORAGE_S3_BUCKET = os.getenv('RECORDING_STORAGE_S3_BUCKET', '')
    RECORDING_STORAGE_S3_REGION = os.getenv('RECORDING_STORAGE_S3_REGION', 'us-east-1')
    RECORDING_EGRESS_URL = os.getenv('RECORDING_EGRESS_URL', '')
    
    # SIP配置
    SIP_ENABLED = os.getenv('SIP_ENABLED', 'false').lower() == 'true'
    SIP_SERVER = os.getenv('SIP_SERVER', '')
    SIP_USERNAME = os.getenv('SIP_USERNAME', '')
    SIP_PASSWORD = os.getenv('SIP_PASSWORD', '')
    
    # Twilio配置（用于电话集成）
    TWILIO_ENABLED = os.getenv('TWILIO_ENABLED', 'false').lower() == 'true'
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')
    
    # Redis配置（用于状态同步）
    REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'false').lower() == 'true'
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # 音频处理配置
    AUDIO_QUALITY_ADAPTIVE = os.getenv('AUDIO_QUALITY_ADAPTIVE', 'true').lower() == 'true'
    AUDIO_NOISE_SUPPRESSION = os.getenv('AUDIO_NOISE_SUPPRESSION', 'true').lower() == 'true'
    AUDIO_ECHO_CANCELLATION = os.getenv('AUDIO_ECHO_CANCELLATION', 'true').lower() == 'true'
    AUDIO_AUTO_GAIN_CONTROL = os.getenv('AUDIO_AUTO_GAIN_CONTROL', 'true').lower() == 'true'
    
    # 获取多区域LiveKit URL
    def get_livekit_url_for_region(self, region: Optional[str] = None) -> str:
        """根据区域获取LiveKit URL"""
        if not region or not self.MULTI_REGION:
            return self.LIVEKIT_URL
        
        regions_config = self.REGIONS_CONFIG
        if not regions_config or region not in regions_config:
            return self.LIVEKIT_URL
        
        return regions_config.get(region, {}).get('url', self.LIVEKIT_URL)
    
    # 获取多区域LiveKit API密钥
    def get_livekit_api_key_for_region(self, region: Optional[str] = None) -> str:
        """根据区域获取LiveKit API密钥"""
        if not region or not self.MULTI_REGION:
            return self.LIVEKIT_API_KEY
        
        regions_config = self.REGIONS_CONFIG
        if not regions_config or region not in regions_config:
            return self.LIVEKIT_API_KEY
        
        return regions_config.get(region, {}).get('api_key', self.LIVEKIT_API_KEY)
    
    # 获取多区域LiveKit密钥
    def get_livekit_secret_for_region(self, region: Optional[str] = None) -> str:
        """根据区域获取LiveKit密钥"""
        if not region or not self.MULTI_REGION:
            return self.LIVEKIT_SECRET
        
        regions_config = self.REGIONS_CONFIG
        if not regions_config or region not in regions_config:
            return self.LIVEKIT_SECRET
        
        return regions_config.get(region, {}).get('secret', self.LIVEKIT_SECRET)
    
    # 获取所有可用区域
    def get_available_regions(self) -> List[Dict[str, str]]:
        """获取所有可用区域"""
        if not self.MULTI_REGION:
            return [{"id": "default", "name": "默认区域", "url": self.LIVEKIT_URL}]
        
        regions = []
        for region_id, region_config in self.REGIONS_CONFIG.items():
            regions.append({
                "id": region_id,
                "name": region_config.get('name', region_id),
                "url": region_config.get('url', '')
            })
        
        if not regions:
            regions = [{"id": "default", "name": "默认区域", "url": self.LIVEKIT_URL}]
        
        return regions
    
    def log(self):
        """打印配置信息"""
        print("🔍 [DEBUG] LIVEKIT_API_KEY:", "FOUND" if self.LIVEKIT_API_KEY else "MISSING")
        print("🔍 [DEBUG] LIVEKIT_SECRET:", "FOUND" if self.LIVEKIT_SECRET else "MISSING")
        print("🔍 [DEBUG] LIVEKIT_URL:", self.LIVEKIT_URL or "MISSING")
        print("🔍 [DEBUG] PORT:", self.PORT)
        print("🔍 [DEBUG] MULTI_REGION:", self.MULTI_REGION)
        print("🔍 [DEBUG] REGION:", self.REGION)
        print("🔍 [DEBUG] AUDIT_ENABLED:", self.AUDIT_ENABLED)
        print("🔍 [DEBUG] RECORDING_ENABLED:", self.RECORDING_ENABLED)
        print("🔍 [DEBUG] SIP_ENABLED:", self.SIP_ENABLED)
        print("🔍 [DEBUG] TWILIO_ENABLED:", self.TWILIO_ENABLED)
        print("🔍 [DEBUG] REDIS_ENABLED:", self.REDIS_ENABLED)
        print("🔍 [DEBUG] AUDIO_QUALITY_ADAPTIVE:", self.AUDIO_QUALITY_ADAPTIVE)

# 创建全局设置实例
settings = Settings() 
