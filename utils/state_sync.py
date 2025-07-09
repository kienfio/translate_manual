import json
import asyncio
import redis.asyncio as redis
from typing import Dict, Any, Optional, List, Callable, Awaitable
from config.settings import settings
from utils.audit_logger import AuditLogger

class StateManager:
    """状态管理器，处理分布式状态同步"""
    
    def __init__(self):
        """初始化状态管理器"""
        self.redis = None
        self.subscribers = {}
        self.local_state = {}
        self.is_connected = False
        self.pubsub = None
    
    async def connect(self) -> bool:
        """
        连接到Redis
        
        Returns:
            连接是否成功
        """
        if not settings.REDIS_ENABLED:
            print("⚠️ Redis状态同步未启用")
            return False
        
        try:
            # 连接到Redis
            self.redis = redis.from_url(settings.REDIS_URL)
            self.is_connected = True
            
            # 初始化PubSub
            self.pubsub = self.redis.pubsub()
            
            print("✅ Redis连接成功")
            return True
        except Exception as e:
            print(f"❌ Redis连接失败: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis:
            await self.redis.close()
            self.is_connected = False
            print("🔌 Redis连接已关闭")
    
    async def set_state(self, key: str, value: Any, namespace: str = "default") -> bool:
        """
        设置状态
        
        Args:
            key: 状态键
            value: 状态值
            namespace: 命名空间
        
        Returns:
            操作是否成功
        """
        full_key = f"{namespace}:{key}"
        
        # 更新本地状态
        if namespace not in self.local_state:
            self.local_state[namespace] = {}
        
        self.local_state[namespace][key] = value
        
        # 如果Redis已连接，同步到Redis
        if self.is_connected and self.redis:
            try:
                json_value = json.dumps(value)
                await self.redis.set(full_key, json_value)
                
                # 发布更新通知
                update_message = json.dumps({
                    "type": "state_update",
                    "namespace": namespace,
                    "key": key,
                    "value": value
                })
                await self.redis.publish(f"state_updates:{namespace}", update_message)
                
                return True
            except Exception as e:
                print(f"❌ Redis设置状态失败: {str(e)}")
                return False
        
        return True
    
    async def get_state(self, key: str, namespace: str = "default") -> Any:
        """
        获取状态
        
        Args:
            key: 状态键
            namespace: 命名空间
        
        Returns:
            状态值
        """
        # 先检查本地状态
        if namespace in self.local_state and key in self.local_state[namespace]:
            return self.local_state[namespace][key]
        
        # 如果Redis已连接，从Redis获取
        if self.is_connected and self.redis:
            try:
                full_key = f"{namespace}:{key}"
                value = await self.redis.get(full_key)
                
                if value:
                    parsed_value = json.loads(value)
                    
                    # 更新本地缓存
                    if namespace not in self.local_state:
                        self.local_state[namespace] = {}
                    
                    self.local_state[namespace][key] = parsed_value
                    
                    return parsed_value
            except Exception as e:
                print(f"❌ Redis获取状态失败: {str(e)}")
        
        return None
    
    async def delete_state(self, key: str, namespace: str = "default") -> bool:
        """
        删除状态
        
        Args:
            key: 状态键
            namespace: 命名空间
        
        Returns:
            操作是否成功
        """
        # 从本地状态删除
        if namespace in self.local_state and key in self.local_state[namespace]:
            del self.local_state[namespace][key]
        
        # 如果Redis已连接，从Redis删除
        if self.is_connected and self.redis:
            try:
                full_key = f"{namespace}:{key}"
                await self.redis.delete(full_key)
                
                # 发布删除通知
                delete_message = json.dumps({
                    "type": "state_delete",
                    "namespace": namespace,
                    "key": key
                })
                await self.redis.publish(f"state_updates:{namespace}", delete_message)
                
                return True
            except Exception as e:
                print(f"❌ Redis删除状态失败: {str(e)}")
                return False
        
        return True
    
    async def subscribe(
        self, 
        namespace: str, 
        callback: Callable[[str, Any], Awaitable[None]]
    ) -> bool:
        """
        订阅状态更新
        
        Args:
            namespace: 命名空间
            callback: 回调函数，接收(key, value)参数
        
        Returns:
            订阅是否成功
        """
        if not self.is_connected or not self.redis:
            print("⚠️ Redis未连接，无法订阅状态更新")
            return False
        
        try:
            # 将回调函数添加到订阅者列表
            if namespace not in self.subscribers:
                self.subscribers[namespace] = []
            
            self.subscribers[namespace].append(callback)
            
            # 如果是第一个订阅者，启动PubSub监听
            if len(self.subscribers[namespace]) == 1:
                await self.pubsub.subscribe(f"state_updates:{namespace}")
                
                # 启动后台任务处理消息
                asyncio.create_task(self._message_handler())
            
            return True
        except Exception as e:
            print(f"❌ 订阅状态更新失败: {str(e)}")
            return False
    
    async def unsubscribe(
        self, 
        namespace: str, 
        callback: Callable[[str, Any], Awaitable[None]]
    ) -> bool:
        """
        取消订阅状态更新
        
        Args:
            namespace: 命名空间
            callback: 回调函数
        
        Returns:
            取消订阅是否成功
        """
        if namespace not in self.subscribers:
            return False
        
        try:
            # 从订阅者列表中移除回调函数
            if callback in self.subscribers[namespace]:
                self.subscribers[namespace].remove(callback)
            
            # 如果没有订阅者了，取消PubSub订阅
            if not self.subscribers[namespace]:
                await self.pubsub.unsubscribe(f"state_updates:{namespace}")
                del self.subscribers[namespace]
            
            return True
        except Exception as e:
            print(f"❌ 取消订阅状态更新失败: {str(e)}")
            return False
    
    async def _message_handler(self):
        """处理PubSub消息"""
        while self.is_connected:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                
                if message:
                    channel = message["channel"].decode("utf-8")
                    data = json.loads(message["data"].decode("utf-8"))
                    
                    # 解析频道名称
                    parts = channel.split(":")
                    if len(parts) == 2 and parts[0] == "state_updates":
                        namespace = parts[1]
                        
                        if namespace in self.subscribers:
                            # 处理状态更新
                            if data["type"] == "state_update":
                                key = data["key"]
                                value = data["value"]
                                
                                # 更新本地缓存
                                if namespace not in self.local_state:
                                    self.local_state[namespace] = {}
                                
                                self.local_state[namespace][key] = value
                                
                                # 通知所有订阅者
                                for callback in self.subscribers[namespace]:
                                    try:
                                        await callback(key, value)
                                    except Exception as e:
                                        print(f"❌ 状态更新回调执行失败: {str(e)}")
                            
                            # 处理状态删除
                            elif data["type"] == "state_delete":
                                key = data["key"]
                                
                                # 从本地缓存删除
                                if namespace in self.local_state and key in self.local_state[namespace]:
                                    del self.local_state[namespace][key]
                                
                                # 通知所有订阅者
                                for callback in self.subscribers[namespace]:
                                    try:
                                        await callback(key, None)
                                    except Exception as e:
                                        print(f"❌ 状态删除回调执行失败: {str(e)}")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ 处理PubSub消息失败: {str(e)}")
            
            # 避免CPU占用过高
            await asyncio.sleep(0.1)
    
    async def get_all_states(self, namespace: str = "default") -> Dict[str, Any]:
        """
        获取命名空间下的所有状态
        
        Args:
            namespace: 命名空间
        
        Returns:
            状态字典
        """
        result = {}
        
        # 合并本地状态
        if namespace in self.local_state:
            result.update(self.local_state[namespace])
        
        # 如果Redis已连接，获取Redis中的状态
        if self.is_connected and self.redis:
            try:
                # 获取所有键
                keys = await self.redis.keys(f"{namespace}:*")
                
                if keys:
                    # 批量获取值
                    values = await self.redis.mget(keys)
                    
                    # 解析键和值
                    for i, key in enumerate(keys):
                        if values[i]:
                            # 提取实际键名（去掉命名空间前缀）
                            actual_key = key.decode("utf-8").split(":", 1)[1]
                            result[actual_key] = json.loads(values[i].decode("utf-8"))
            except Exception as e:
                print(f"❌ 获取所有状态失败: {str(e)}")
        
        return result

# 创建全局状态管理器实例
state_manager = StateManager() 
