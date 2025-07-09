import json
import asyncio
from typing import Dict, List, Any, Optional, Set, Callable, Awaitable
from datetime import datetime
from config.settings import settings
from utils.audit_logger import AuditLogger
from utils.state_sync import state_manager

class TextChatManager:
    """文本聊天管理器，处理实时文本传输和字幕"""
    
    def __init__(self):
        """初始化文本聊天管理器"""
        # 房间消息历史
        self.room_messages: Dict[str, List[Dict[str, Any]]] = {}
        
        # 房间消息监听器
        self.message_listeners: Dict[str, Set[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        
        # 字幕历史
        self.captions: Dict[str, Dict[str, Any]] = {}
        
        # 字幕监听器
        self.caption_listeners: Dict[str, Set[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        
        # 消息ID计数器
        self.message_counter = 0
    
    async def initialize(self):
        """初始化管理器，连接到状态同步系统"""
        if settings.REDIS_ENABLED:
            # 连接到Redis并订阅消息更新
            await state_manager.connect()
            
            # 订阅消息更新
            await state_manager.subscribe("chat_messages", self._handle_message_update)
            
            # 订阅字幕更新
            await state_manager.subscribe("captions", self._handle_caption_update)
    
    async def _handle_message_update(self, key: str, value: Any):
        """
        处理消息更新
        
        Args:
            key: 消息键 (room_name)
            value: 消息值
        """
        if not value:
            return
        
        room_name = key
        message = value
        
        # 更新本地消息历史
        if room_name not in self.room_messages:
            self.room_messages[room_name] = []
        
        self.room_messages[room_name].append(message)
        
        # 通知监听器
        if room_name in self.message_listeners:
            for listener in self.message_listeners[room_name]:
                try:
                    await listener(message)
                except Exception as e:
                    print(f"❌ 消息监听器执行失败: {str(e)}")
    
    async def _handle_caption_update(self, key: str, value: Any):
        """
        处理字幕更新
        
        Args:
            key: 字幕键 (room_name:user_id)
            value: 字幕值
        """
        if not value:
            return
        
        parts = key.split(":")
        if len(parts) != 2:
            return
        
        room_name, user_id = parts
        caption = value
        
        # 更新本地字幕历史
        if room_name not in self.captions:
            self.captions[room_name] = {}
        
        self.captions[room_name][user_id] = caption
        
        # 通知监听器
        if room_name in self.caption_listeners:
            for listener in self.caption_listeners[room_name]:
                try:
                    await listener({
                        "room": room_name,
                        "user_id": user_id,
                        "caption": caption
                    })
                except Exception as e:
                    print(f"❌ 字幕监听器执行失败: {str(e)}")
    
    async def send_message(
        self, 
        room_name: str, 
        user_id: str, 
        content: str, 
        message_type: str = "text"
    ) -> Dict[str, Any]:
        """
        发送消息到房间
        
        Args:
            room_name: 房间名称
            user_id: 用户ID
            content: 消息内容
            message_type: 消息类型 (text, system, etc.)
        
        Returns:
            发送的消息
        """
        # 生成消息ID
        self.message_counter += 1
        message_id = f"msg_{int(datetime.now().timestamp())}_{self.message_counter}"
        
        # 创建消息对象
        message = {
            "id": message_id,
            "room": room_name,
            "user_id": user_id,
            "content": content,
            "type": message_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 添加到本地历史
        if room_name not in self.room_messages:
            self.room_messages[room_name] = []
        
        self.room_messages[room_name].append(message)
        
        # 如果启用了状态同步，同步到Redis
        if settings.REDIS_ENABLED:
            await state_manager.set_state(room_name, message, namespace="chat_messages")
        else:
            # 直接通知本地监听器
            if room_name in self.message_listeners:
                for listener in self.message_listeners[room_name]:
                    try:
                        await listener(message)
                    except Exception as e:
                        print(f"❌ 消息监听器执行失败: {str(e)}")
        
        # 记录审计日志
        AuditLogger.log(
            event="chat.message_sent",
            user_id=user_id,
            details={
                "room_name": room_name,
                "message_id": message_id,
                "message_type": message_type
            }
        )
        
        return message
    
    async def update_caption(
        self, 
        room_name: str, 
        user_id: str, 
        text: str, 
        is_final: bool = False,
        language: str = "zh-CN"
    ) -> Dict[str, Any]:
        """
        更新用户字幕
        
        Args:
            room_name: 房间名称
            user_id: 用户ID
            text: 字幕文本
            is_final: 是否为最终字幕
            language: 字幕语言
        
        Returns:
            更新的字幕
        """
        # 创建字幕对象
        caption = {
            "text": text,
            "is_final": is_final,
            "language": language,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 更新本地字幕
        if room_name not in self.captions:
            self.captions[room_name] = {}
        
        self.captions[room_name][user_id] = caption
        
        # 如果是最终字幕，可以作为消息保存
        if is_final and text.strip():
            await self.send_message(
                room_name=room_name,
                user_id=user_id,
                content=text,
                message_type="caption"
            )
        
        # 如果启用了状态同步，同步到Redis
        if settings.REDIS_ENABLED:
            key = f"{room_name}:{user_id}"
            await state_manager.set_state(key, caption, namespace="captions")
        else:
            # 直接通知本地监听器
            if room_name in self.caption_listeners:
                for listener in self.caption_listeners[room_name]:
                    try:
                        await listener({
                            "room": room_name,
                            "user_id": user_id,
                            "caption": caption
                        })
                    except Exception as e:
                        print(f"❌ 字幕监听器执行失败: {str(e)}")
        
        return caption
    
    async def get_room_messages(
        self, 
        room_name: str, 
        limit: int = 100, 
        before_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取房间消息历史
        
        Args:
            room_name: 房间名称
            limit: 返回的消息数量限制
            before_id: 可选的消息ID，获取此ID之前的消息
        
        Returns:
            消息列表
        """
        if room_name not in self.room_messages:
            return []
        
        messages = self.room_messages[room_name]
        
        if before_id:
            # 找到指定消息的索引
            index = -1
            for i, msg in enumerate(messages):
                if msg["id"] == before_id:
                    index = i
                    break
            
            if index != -1:
                messages = messages[:index]
        
        # 返回最近的消息，最多limit条
        return messages[-limit:] if len(messages) > limit else messages
    
    async def get_room_captions(self, room_name: str) -> Dict[str, Dict[str, Any]]:
        """
        获取房间当前字幕
        
        Args:
            room_name: 房间名称
        
        Returns:
            用户ID到字幕的映射
        """
        if room_name not in self.captions:
            return {}
        
        return self.captions[room_name]
    
    async def add_message_listener(
        self, 
        room_name: str, 
        listener: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """
        添加消息监听器
        
        Args:
            room_name: 房间名称
            listener: 监听器回调函数
        """
        if room_name not in self.message_listeners:
            self.message_listeners[room_name] = set()
        
        self.message_listeners[room_name].add(listener)
    
    async def remove_message_listener(
        self, 
        room_name: str, 
        listener: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """
        移除消息监听器
        
        Args:
            room_name: 房间名称
            listener: 监听器回调函数
        """
        if room_name in self.message_listeners and listener in self.message_listeners[room_name]:
            self.message_listeners[room_name].remove(listener)
            
            if not self.message_listeners[room_name]:
                del self.message_listeners[room_name]
    
    async def add_caption_listener(
        self, 
        room_name: str, 
        listener: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """
        添加字幕监听器
        
        Args:
            room_name: 房间名称
            listener: 监听器回调函数
        """
        if room_name not in self.caption_listeners:
            self.caption_listeners[room_name] = set()
        
        self.caption_listeners[room_name].add(listener)
    
    async def remove_caption_listener(
        self, 
        room_name: str, 
        listener: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """
        移除字幕监听器
        
        Args:
            room_name: 房间名称
            listener: 监听器回调函数
        """
        if room_name in self.caption_listeners and listener in self.caption_listeners[room_name]:
            self.caption_listeners[room_name].remove(listener)
            
            if not self.caption_listeners[room_name]:
                del self.caption_listeners[room_name]
    
    async def clear_room_messages(self, room_name: str):
        """
        清除房间消息历史
        
        Args:
            room_name: 房间名称
        """
        if room_name in self.room_messages:
            self.room_messages[room_name] = []
        
        # 如果启用了状态同步，从Redis删除
        if settings.REDIS_ENABLED:
            await state_manager.delete_state(room_name, namespace="chat_messages")

# 创建全局文本聊天管理器实例
text_chat_manager = TextChatManager() 