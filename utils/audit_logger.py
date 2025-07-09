import os
import json
import logging
import structlog
from datetime import datetime
from typing import Dict, Any, Optional
from config.settings import settings

# 确保日志目录存在
os.makedirs(os.path.dirname(settings.AUDIT_LOG_PATH), exist_ok=True)

# 配置结构化日志
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# 配置标准日志
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(getattr(logging, settings.AUDIT_LOG_LEVEL))

# 添加文件处理器
file_handler = logging.FileHandler(settings.AUDIT_LOG_PATH)
file_handler.setFormatter(logging.Formatter('%(message)s'))
audit_logger.addHandler(file_handler)

# 如果需要，添加控制台处理器
if settings.AUDIT_LOG_LEVEL == "DEBUG":
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    audit_logger.addHandler(console_handler)

# 结构化日志记录器
structured_logger = structlog.get_logger("audit")

class AuditLogger:
    """安全审计日志记录器"""
    
    @staticmethod
    def log(event: str, user_id: str, details: Dict[str, Any], level: str = "INFO") -> None:
        """
        记录审计事件
        
        Args:
            event: 事件类型
            user_id: 用户标识
            details: 事件详情
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        if not settings.AUDIT_ENABLED:
            return
        
        log_data = {
            "event": event,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        }
        
        # 使用结构化日志记录 - 修复方法调用
        log_method = getattr(structured_logger, level.lower(), structured_logger.info)
        # 正确的调用方式是将event作为第一个参数，其他信息作为关键字参数
        log_method(
            event,  # 第一个参数是事件名称
            user_id=user_id,
            **details
        )
        
        # 同时使用标准日志记录JSON格式
        log_method = getattr(audit_logger, level.lower(), audit_logger.info)
        log_method(json.dumps(log_data))
    
    @staticmethod
    def log_room_event(event: str, room_name: str, user_id: str, details: Dict[str, Any]) -> None:
        """记录房间相关事件"""
        AuditLogger.log(
            event=f"room.{event}",
            user_id=user_id,
            details={"room_name": room_name, **details}
        )
    
    @staticmethod
    def log_token_event(event: str, room_name: str, user_id: str, is_publisher: bool) -> None:
        """记录令牌相关事件"""
        AuditLogger.log(
            event=f"token.{event}",
            user_id=user_id,
            details={
                "room_name": room_name,
                "is_publisher": is_publisher
            }
        )
    
    @staticmethod
    def log_recording_event(event: str, room_name: str, recording_id: str, details: Dict[str, Any]) -> None:
        """记录录制相关事件"""
        AuditLogger.log(
            event=f"recording.{event}",
            user_id=recording_id,
            details={"room_name": room_name, **details}
        )
    
    @staticmethod
    def log_sip_event(event: str, call_id: str, details: Dict[str, Any]) -> None:
        """记录SIP电话相关事件"""
        AuditLogger.log(
            event=f"sip.{event}",
            user_id=call_id,
            details=details
        )
    
    @staticmethod
    def log_security_event(event: str, user_id: str, details: Dict[str, Any]) -> None:
        """记录安全相关事件"""
        AuditLogger.log(
            event=f"security.{event}",
            user_id=user_id,
            details=details,
            level="WARNING"
        )
    
    @staticmethod
    def log_error(event: str, user_id: str, error: Exception, details: Optional[Dict[str, Any]] = None) -> None:
        """记录错误事件"""
        if details is None:
            details = {}
        
        AuditLogger.log(
            event=f"error.{event}",
            user_id=user_id,
            details={
                "error_type": type(error).__name__,
                "error_message": str(error),
                **details
            },
            level="ERROR"
        ) 
