import os
import uuid
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from twilio.rest import Client
from config.settings import settings
from utils.audit_logger import AuditLogger

class SipManager:
    """SIP管理器，处理与传统电话系统的连接"""
    
    def __init__(self):
        """初始化SIP管理器"""
        self.active_calls: Dict[str, Dict[str, Any]] = {}
        self.twilio_client = None
        
        # 如果启用了Twilio，初始化客户端
        if settings.TWILIO_ENABLED and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                print("✅ Twilio客户端初始化成功")
            except Exception as e:
                print(f"❌ Twilio客户端初始化失败: {str(e)}")
    
    async def make_outbound_call(
        self, 
        phone_number: str, 
        room_name: str, 
        language: str,
        caller_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        拨打电话并连接到LiveKit房间
        
        Args:
            phone_number: 要拨打的电话号码
            room_name: LiveKit房间名称
            language: 语言代码
            caller_id: 主叫号码（如果未提供，使用配置的Twilio号码）
        
        Returns:
            (成功状态, 消息, 通话ID)
        """
        if not settings.TWILIO_ENABLED:
            return False, "Twilio电话功能未启用", None
        
        if not self.twilio_client:
            return False, "Twilio客户端未初始化", None
        
        # 验证电话号码格式
        if not phone_number.startswith('+'):
            phone_number = f"+{phone_number}"
        
        # 设置主叫号码
        from_number = caller_id or settings.TWILIO_PHONE_NUMBER
        if not from_number:
            return False, "未配置主叫号码", None
        
        # 生成通话ID
        call_id = f"call_{uuid.uuid4().hex[:8]}"
        
        try:
            # 创建TwiML响应
            twiml = f"""
            <?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say language="{language}">您已连接到实时翻译服务。请稍等，正在连接翻译员。</Say>
                <Connect>
                    <Stream url="wss://{settings.LIVEKIT_URL.replace('wss://', '')}/twilio/stream?room={room_name}&identity=phone_{call_id}"></Stream>
                </Connect>
                <Say language="{language}">通话已结束。感谢您使用实时翻译服务。</Say>
            </Response>
            """
            
            # 发起呼叫
            call = self.twilio_client.calls.create(
                to=phone_number,
                from_=from_number,
                twiml=twiml
            )
            
            # 记录活跃通话
            self.active_calls[call_id] = {
                "twilio_call_sid": call.sid,
                "phone_number": phone_number,
                "room_name": room_name,
                "language": language,
                "status": "initiated",
                "direction": "outbound"
            }
            
            # 记录审计日志
            AuditLogger.log_sip_event(
                "outbound_call_initiated", call_id,
                {
                    "phone_number": phone_number,
                    "room_name": room_name,
                    "twilio_call_sid": call.sid
                }
            )
            
            return True, f"正在拨打电话 {phone_number}", call_id
        
        except Exception as e:
            error_msg = f"拨打电话失败: {str(e)}"
            AuditLogger.log_sip_event(
                "outbound_call_failed", call_id,
                {
                    "phone_number": phone_number,
                    "room_name": room_name,
                    "error": str(e)
                }
            )
            return False, error_msg, None
    
    async def setup_inbound_call_webhook(self) -> Tuple[bool, str]:
        """
        设置接收入站电话的Webhook
        
        Returns:
            (成功状态, 消息)
        """
        if not settings.TWILIO_ENABLED:
            return False, "Twilio电话功能未启用"
        
        if not self.twilio_client:
            return False, "Twilio客户端未初始化"
        
        try:
            # 更新Twilio电话号码的Webhook
            incoming_phone_number = self.twilio_client.incoming_phone_numbers.list(
                phone_number=settings.TWILIO_PHONE_NUMBER,
                limit=1
            )
            
            if not incoming_phone_number:
                return False, f"未找到Twilio电话号码: {settings.TWILIO_PHONE_NUMBER}"
            
            # 更新Webhook URL
            incoming_phone_number[0].update(
                voice_url=f"https://{settings.LIVEKIT_URL.replace('wss://', '')}/api/twilio/incoming"
            )
            
            return True, "入站电话Webhook设置成功"
        
        except Exception as e:
            error_msg = f"设置入站电话Webhook失败: {str(e)}"
            return False, error_msg
    
    async def handle_incoming_call(
        self, 
        call_sid: str, 
        from_number: str, 
        to_number: str,
        room_name: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        处理入站电话
        
        Args:
            call_sid: Twilio通话SID
            from_number: 主叫号码
            to_number: 被叫号码
            room_name: 可选的房间名称，如果未提供则自动生成
        
        Returns:
            (成功状态, TwiML响应, 通话ID)
        """
        # 生成通话ID
        call_id = f"call_{uuid.uuid4().hex[:8]}"
        
        # 如果未提供房间名称，则根据被叫号码生成
        if not room_name:
            # 提取号码的最后4位作为房间标识
            last_four_digits = to_number[-4:] if len(to_number) >= 4 else to_number
            room_name = f"room-phone-{last_four_digits}"
        
        # 记录活跃通话
        self.active_calls[call_id] = {
            "twilio_call_sid": call_sid,
            "phone_number": from_number,
            "room_name": room_name,
            "status": "connected",
            "direction": "inbound"
        }
        
        # 记录审计日志
        AuditLogger.log_sip_event(
            "inbound_call_received", call_id,
            {
                "from_number": from_number,
                "to_number": to_number,
                "room_name": room_name,
                "twilio_call_sid": call_sid
            }
        )
        
        # 创建TwiML响应
        twiml = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say>欢迎使用实时翻译服务。您已连接到翻译频道。</Say>
            <Connect>
                <Stream url="wss://{settings.LIVEKIT_URL.replace('wss://', '')}/twilio/stream?room={room_name}&identity=phone_{call_id}"></Stream>
            </Connect>
            <Say>通话已结束。感谢您使用实时翻译服务。</Say>
        </Response>
        """
        
        return True, twiml, call_id
    
    async def end_call(self, call_id: str) -> Tuple[bool, str]:
        """
        结束通话
        
        Args:
            call_id: 通话ID
        
        Returns:
            (成功状态, 消息)
        """
        if call_id not in self.active_calls:
            return False, f"未找到通话ID: {call_id}"
        
        call_info = self.active_calls[call_id]
        twilio_call_sid = call_info.get("twilio_call_sid")
        
        if not twilio_call_sid:
            return False, f"通话 {call_id} 没有有效的Twilio通话SID"
        
        try:
            # 结束通话
            self.twilio_client.calls(twilio_call_sid).update(status="completed")
            
            # 更新通话状态
            self.active_calls[call_id]["status"] = "ended"
            
            # 记录审计日志
            AuditLogger.log_sip_event(
                "call_ended", call_id,
                {"twilio_call_sid": twilio_call_sid}
            )
            
            return True, f"通话 {call_id} 已结束"
        
        except Exception as e:
            error_msg = f"结束通话时发生错误: {str(e)}"
            AuditLogger.log_sip_event(
                "call_end_error", call_id,
                {"error": str(e), "twilio_call_sid": twilio_call_sid}
            )
            return False, error_msg
    
    async def get_call_status(self, call_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        获取通话状态
        
        Args:
            call_id: 通话ID
        
        Returns:
            (成功状态, 状态信息)
        """
        if call_id not in self.active_calls:
            return False, {"error": f"未找到通话ID: {call_id}"}
        
        call_info = self.active_calls[call_id]
        twilio_call_sid = call_info.get("twilio_call_sid")
        
        if not twilio_call_sid:
            return False, {"error": f"通话 {call_id} 没有有效的Twilio通话SID"}
        
        try:
            # 查询Twilio通话状态
            call = self.twilio_client.calls(twilio_call_sid).fetch()
            
            # 更新本地通话状态
            self.active_calls[call_id]["twilio_status"] = call.status
            
            # 构建返回信息
            result = {
                "call_id": call_id,
                "phone_number": call_info.get("phone_number"),
                "room_name": call_info.get("room_name"),
                "status": call_info.get("status"),
                "direction": call_info.get("direction"),
                "twilio_status": call.status,
                "twilio_duration": call.duration
            }
            
            return True, result
        
        except Exception as e:
            error_msg = f"查询通话状态时发生错误: {str(e)}"
            return False, {"error": error_msg}
    
    async def list_calls(self, room_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出通话
        
        Args:
            room_name: 可选的房间名称过滤
        
        Returns:
            通话列表
        """
        calls = []
        
        for c_id, c_info in self.active_calls.items():
            if room_name is None or c_info.get("room_name") == room_name:
                calls.append({
                    "call_id": c_id,
                    "phone_number": c_info.get("phone_number"),
                    "room_name": c_info.get("room_name"),
                    "status": c_info.get("status"),
                    "direction": c_info.get("direction")
                })
        
        return calls

# 创建全局SIP管理器实例
sip_manager = SipManager() 