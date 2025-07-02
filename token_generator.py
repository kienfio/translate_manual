import os
from livekit import AccessToken, RoomServiceClient, VideoGrant, Room
from typing import Optional
from dotenv import load_dotenv

# 尝试加载.env文件，但在Render部署时会使用环境变量
load_dotenv()

# 从环境变量获取LiveKit配置
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
LIVEKIT_SECRET = os.getenv('LIVEKIT_SECRET')
LIVEKIT_URL = os.getenv('LIVEKIT_URL')  # 例如: wss://your-project.livekit.cloud

def create_room_if_not_exists(room_name: str) -> bool:
    """
    如果房间不存在，则创建房间
    
    Args:
        room_name: 房间名称
        
    Returns:
        bool: 操作是否成功
    """
    try:
        # 创建RoomServiceClient
        room_client = RoomServiceClient(
            LIVEKIT_URL.replace('wss://', 'https://').replace('ws://', 'http://'),
            LIVEKIT_API_KEY,
            LIVEKIT_SECRET
        )
        
        # 检查房间是否存在
        try:
            room_client.get_room(room_name)
            print(f"房间 {room_name} 已存在")
        except Exception:
            # 房间不存在，创建新房间
            room: Room = room_client.create_room(
                name=room_name,
                empty_timeout=300,  # 设置空房间超时时间为5分钟
                max_participants=100  # 最大参与人数
            )
            print(f"已创建房间: {room.name}")
        
        return True
    except Exception as e:
        print(f"创建房间失败: {str(e)}")
        return False

def generate_token(room_name: str, identity: str, is_publisher: bool = False) -> Optional[str]:
    """
    生成LiveKit房间访问Token
    
    Args:
        room_name: 房间名称
        identity: 用户标识
        is_publisher: 是否为发布者（默认为否，即观众）
        
    Returns:
        str: JWT Token
    """
    try:
        # 验证必要的配置是否存在
        if not all([LIVEKIT_API_KEY, LIVEKIT_SECRET]):
            print("错误: LiveKit API密钥或密钥缺失")
            return None
            
        # 确保房间存在
        create_room_if_not_exists(room_name)
        
        # 创建授权Token
        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_SECRET)
        token.identity = identity
        token.name = identity
        
        # 设置权限
        grant = VideoGrant(
            room=room_name,
            room_join=True,
            room_admin=is_publisher,  # 发布者有管理权限
            can_publish=is_publisher,  # 发布者可以发布流
            can_subscribe=True  # 所有人都可以订阅
        )
        token.add_grant(grant)
        
        jwt_token = token.to_jwt()
        return jwt_token
    except Exception as e:
        print(f"生成Token失败: {str(e)}")
        return None

if __name__ == "__main__":
    # 测试生成token
    test_token = generate_token("room-test", "test-user", True)
    if test_token:
        print(f"测试Token: {test_token}")
    else:
        print("Token生成失败") 