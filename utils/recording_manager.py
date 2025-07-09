import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import requests
from config.settings import settings
from utils.audit_logger import AuditLogger

class RecordingManager:
    """录制管理器，处理LiveKit的录制请求和管理"""
    
    def __init__(self):
        """初始化录制管理器"""
        # 确保录制存储目录存在
        if settings.RECORDING_ENABLED and settings.RECORDING_STORAGE_PATH:
            os.makedirs(settings.RECORDING_STORAGE_PATH, exist_ok=True)
        
        # 当前活跃的录制会话
        self.active_recordings: Dict[str, Dict[str, Any]] = {}
    
    async def start_recording(
        self, 
        room_name: str, 
        layout: str = "audio-only", 
        preset: str = "audio-only",
        output_type: str = "mp4",
        custom_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        开始房间录制
        
        Args:
            room_name: 房间名称
            layout: 录制布局 (audio-only, grid, speaker)
            preset: 录制预设 (audio-only, high, medium, low)
            output_type: 输出格式 (mp4, mp3, etc.)
            custom_id: 自定义录制ID
        
        Returns:
            (成功状态, 消息, 录制ID)
        """
        if not settings.RECORDING_ENABLED:
            return False, "录制功能未启用", None
        
        if not settings.RECORDING_EGRESS_URL:
            return False, "录制服务URL未配置", None
        
        # 生成录制ID
        recording_id = custom_id or f"rec_{room_name}_{uuid.uuid4().hex[:8]}"
        
        # 检查房间是否已经在录制
        for rec_id, rec_info in self.active_recordings.items():
            if rec_info.get("room_name") == room_name:
                return False, f"房间 {room_name} 已经在录制中 (ID: {rec_id})", rec_id
        
        try:
            # 准备录制请求
            egress_url = settings.RECORDING_EGRESS_URL.rstrip("/")
            api_key = settings.LIVEKIT_API_KEY
            api_secret = settings.LIVEKIT_SECRET
            
            # 构建录制请求
            request_data = {
                "room_name": room_name,
                "output": {
                    "file_type": output_type,
                    "filepath": f"{recording_id}.{output_type}"
                },
                "preset": preset,
                "layout": layout,
                "custom_id": recording_id
            }
            
            # 如果配置了S3存储
            if settings.RECORDING_STORAGE_S3_BUCKET:
                request_data["output"]["s3"] = {
                    "bucket": settings.RECORDING_STORAGE_S3_BUCKET,
                    "region": settings.RECORDING_STORAGE_S3_REGION,
                    "key_prefix": f"recordings/{room_name}/"
                }
            
            # 发送录制请求到LiveKit Egress API
            response = requests.post(
                f"{egress_url}/api/v1/room_composite",
                json=request_data,
                auth=(api_key, api_secret),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                error_msg = f"录制请求失败: {response.status_code} - {response.text}"
                AuditLogger.log_recording_event(
                    "start_failed", room_name, recording_id,
                    {"error": error_msg, "request": request_data}
                )
                return False, error_msg, None
            
            # 解析响应
            response_data = response.json()
            egress_id = response_data.get("egress_id")
            
            if not egress_id:
                error_msg = "录制服务未返回有效的egress_id"
                AuditLogger.log_recording_event(
                    "start_failed", room_name, recording_id,
                    {"error": error_msg, "response": response_data}
                )
                return False, error_msg, None
            
            # 记录活跃的录制会话
            self.active_recordings[recording_id] = {
                "room_name": room_name,
                "egress_id": egress_id,
                "start_time": datetime.utcnow().isoformat(),
                "status": "active",
                "layout": layout,
                "preset": preset,
                "output_type": output_type
            }
            
            # 记录审计日志
            AuditLogger.log_recording_event(
                "started", room_name, recording_id,
                {"egress_id": egress_id, "layout": layout, "preset": preset}
            )
            
            return True, f"房间 {room_name} 录制已开始 (ID: {recording_id})", recording_id
        
        except Exception as e:
            error_msg = f"启动录制时发生错误: {str(e)}"
            AuditLogger.log_recording_event(
                "start_error", room_name, recording_id,
                {"error": str(e)}
            )
            return False, error_msg, None
    
    async def stop_recording(self, recording_id: str) -> Tuple[bool, str]:
        """
        停止录制
        
        Args:
            recording_id: 录制ID
        
        Returns:
            (成功状态, 消息)
        """
        if not settings.RECORDING_ENABLED:
            return False, "录制功能未启用"
        
        if recording_id not in self.active_recordings:
            return False, f"未找到录制ID: {recording_id}"
        
        recording_info = self.active_recordings[recording_id]
        room_name = recording_info.get("room_name")
        egress_id = recording_info.get("egress_id")
        
        if not egress_id:
            return False, f"录制 {recording_id} 没有有效的egress_id"
        
        try:
            # 准备停止录制请求
            egress_url = settings.RECORDING_EGRESS_URL.rstrip("/")
            api_key = settings.LIVEKIT_API_KEY
            api_secret = settings.LIVEKIT_SECRET
            
            # 发送停止录制请求
            response = requests.post(
                f"{egress_url}/api/v1/egress/{egress_id}/stop",
                auth=(api_key, api_secret)
            )
            
            if response.status_code not in [200, 204]:
                error_msg = f"停止录制请求失败: {response.status_code} - {response.text}"
                AuditLogger.log_recording_event(
                    "stop_failed", room_name, recording_id,
                    {"error": error_msg, "egress_id": egress_id}
                )
                return False, error_msg
            
            # 更新录制状态
            self.active_recordings[recording_id]["status"] = "stopped"
            self.active_recordings[recording_id]["stop_time"] = datetime.utcnow().isoformat()
            
            # 记录审计日志
            AuditLogger.log_recording_event(
                "stopped", room_name, recording_id,
                {"egress_id": egress_id}
            )
            
            return True, f"录制 {recording_id} 已停止"
        
        except Exception as e:
            error_msg = f"停止录制时发生错误: {str(e)}"
            AuditLogger.log_recording_event(
                "stop_error", room_name, recording_id,
                {"error": str(e), "egress_id": egress_id}
            )
            return False, error_msg
    
    async def get_recording_status(self, recording_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        获取录制状态
        
        Args:
            recording_id: 录制ID
        
        Returns:
            (成功状态, 状态信息)
        """
        if not settings.RECORDING_ENABLED:
            return False, {"error": "录制功能未启用"}
        
        if recording_id not in self.active_recordings:
            return False, {"error": f"未找到录制ID: {recording_id}"}
        
        recording_info = self.active_recordings[recording_id]
        room_name = recording_info.get("room_name")
        egress_id = recording_info.get("egress_id")
        
        if not egress_id:
            return False, {"error": f"录制 {recording_id} 没有有效的egress_id"}
        
        try:
            # 准备查询录制状态请求
            egress_url = settings.RECORDING_EGRESS_URL.rstrip("/")
            api_key = settings.LIVEKIT_API_KEY
            api_secret = settings.LIVEKIT_SECRET
            
            # 发送查询录制状态请求
            response = requests.get(
                f"{egress_url}/api/v1/egress/{egress_id}",
                auth=(api_key, api_secret)
            )
            
            if response.status_code != 200:
                error_msg = f"查询录制状态失败: {response.status_code} - {response.text}"
                return False, {"error": error_msg}
            
            # 解析响应
            status_data = response.json()
            
            # 更新本地录制状态
            self.active_recordings[recording_id]["livekit_status"] = status_data
            
            # 构建返回信息
            result = {
                "recording_id": recording_id,
                "room_name": room_name,
                "status": self.active_recordings[recording_id]["status"],
                "start_time": self.active_recordings[recording_id]["start_time"],
                "livekit_status": status_data
            }
            
            if "stop_time" in self.active_recordings[recording_id]:
                result["stop_time"] = self.active_recordings[recording_id]["stop_time"]
            
            return True, result
        
        except Exception as e:
            error_msg = f"查询录制状态时发生错误: {str(e)}"
            return False, {"error": error_msg}
    
    async def list_recordings(self, room_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出录制
        
        Args:
            room_name: 可选的房间名称过滤
        
        Returns:
            录制列表
        """
        if not settings.RECORDING_ENABLED:
            return []
        
        recordings = []
        
        for rec_id, rec_info in self.active_recordings.items():
            if room_name is None or rec_info.get("room_name") == room_name:
                recordings.append({
                    "recording_id": rec_id,
                    "room_name": rec_info.get("room_name"),
                    "status": rec_info.get("status"),
                    "start_time": rec_info.get("start_time"),
                    "stop_time": rec_info.get("stop_time", None),
                    "layout": rec_info.get("layout"),
                    "preset": rec_info.get("preset"),
                    "output_type": rec_info.get("output_type")
                })
        
        return recordings
    
    def get_recording_info(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """
        获取录制信息
        
        Args:
            recording_id: 录制ID
        
        Returns:
            录制信息或None
        """
        return self.active_recordings.get(recording_id)

# 创建全局录制管理器实例
recording_manager = RecordingManager() 