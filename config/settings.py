import os
from dotenv import load_dotenv

# 尝试加载.env文件，但在Render部署时会使用环境变量
load_dotenv()

class Settings:
    # LiveKit配置
    LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
    LIVEKIT_SECRET = os.getenv('LIVEKIT_SECRET')
    LIVEKIT_URL = os.getenv('LIVEKIT_URL')  # 例如: wss://your-project.livekit.cloud
    
    # 服务器配置
    PORT = int(os.getenv('PORT', '8000'))
    
    def log(self):
        print("🔍 [DEBUG] LIVEKIT_API_KEY:", "FOUND" if self.LIVEKIT_API_KEY else "MISSING")
        print("🔍 [DEBUG] LIVEKIT_SECRET:", "FOUND" if self.LIVEKIT_SECRET else "MISSING")
        print("🔍 [DEBUG] LIVEKIT_URL:", self.LIVEKIT_URL or "MISSING")
        print("🔍 [DEBUG] PORT:", self.PORT)

# 创建全局设置实例
settings = Settings() 
