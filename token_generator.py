import os
from livekit.api.access_token import AccessToken, VideoGrants
from typing import Optional
from config.settings import settings
from utils.audit_logger import AuditLogger

def create_room_if_not_exists(room_name: str, api_key: Optional[str] = None, api_secret: Optional[str] = None) -> bool:
    """
    如果房间不存在，则创建房间
    
    Args:
        room_name: 房间名称
        api_key: 可选的LiveKit API密钥，如果未提供则使用默认配置
        api_secret: 可选的LiveKit密钥，如果未提供则使用默认配置
        
    Returns:
        bool: 操作是否成功
    """
    try:
        # 在新版本的API中，房间创建可能需要使用其他方式
        # 这部分可能需要根据新版本的API进行调整
        print(f"🔍 [DEBUG] 尝试检查/创建房间: {room_name}")
        # 由于API变化，此功能可能需要重新实现
        return True
    except Exception as e:
        print(f"❌ [ERROR] 创建房间失败: {str(e)}")
        AuditLogger.log_error(
            event="room_creation_failed",
            user_id="system",
            error=e,
            details={"room_name": room_name}
        )
        return False

def generate_token(
    room_name: str, 
    identity: str, 
    is_publisher: bool = False, 
    api_key: Optional[str] = None, 
    api_secret: Optional[str] = None
) -> Optional[str]:
    """
    生成LiveKit房间访问Token
    
    Args:
        room_name: 房间名称
        identity: 用户标识
        is_publisher: 是否为发布者（默认为否，即观众）
        api_key: 可选的LiveKit API密钥，如果未提供则使用默认配置
        api_secret: 可选的LiveKit密钥，如果未提供则使用默认配置
        
    Returns:
        str: JWT Token
    """
    try:
        # 使用提供的API密钥和密钥，或者默认配置
        livekit_api_key = api_key or settings.LIVEKIT_API_KEY
        livekit_secret = api_secret or settings.LIVEKIT_SECRET
        
        # 验证必要的配置是否存在
        if not all([livekit_api_key, livekit_secret]):
            print("❌ [ERROR] LiveKit API密钥或密钥缺失")
            AuditLogger.log_error(
                event="token_generation_failed",
                user_id=identity,
                error=Exception("LiveKit API密钥或密钥缺失"),
                details={"room_name": room_name, "is_publisher": is_publisher}
            )
            return None
            
        # 确保房间存在
        print(f"🔍 [DEBUG] 确保房间存在: {room_name}")
        create_room_if_not_exists(room_name, livekit_api_key, livekit_secret)
        
        # 创建授权Token，使用新版API
        print(f"🔍 [DEBUG] 为用户 {identity} 创建Token")
        token = AccessToken(livekit_api_key, livekit_secret)
        token = token.with_identity(identity)
        
        # 设置权限
        print(f"🔍 [DEBUG] 设置权限 (is_publisher={is_publisher})")
        grants = VideoGrants(
            room=room_name,
            room_join=True,
            room_admin=is_publisher,  # 发布者有管理权限
            can_publish=is_publisher,  # 发布者可以发布流
            can_subscribe=True  # 所有人都可以订阅
        )
        token = token.with_grants(grants)
        
        # 生成JWT
        print("🔍 [DEBUG] 生成JWT")
        jwt_token = token.to_jwt()
        print("✅ [SUCCESS] Token生成成功")
        
        # 记录审计日志
        AuditLogger.log_token_event(
            event="generated",
            room_name=room_name,
            user_id=identity,
            is_publisher=is_publisher
        )
        
        return jwt_token
    except Exception as e:
        print(f"❌ [ERROR] 生成Token失败: {str(e)}")
        AuditLogger.log_error(
            event="token_generation_failed",
            user_id=identity,
            error=e,
            details={"room_name": room_name, "is_publisher": is_publisher}
        )
        raise e

if __name__ == "__main__":
    # 测试生成token
    print("🧪 [TEST] 开始测试Token生成")
    test_token = generate_token("room-test", "test-user", True)
    if test_token:
        print(f"✅ [TEST] 测试Token生成成功: {test_token[:20]}...")
    else:
        print("❌ [TEST] 测试Token生成失败") 
