import os
from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from token_generator import generate_token
import uvicorn
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from config.settings import settings
from utils.audit_logger import AuditLogger
from utils.recording_manager import recording_manager
from utils.sip_manager import sip_manager
from utils.state_sync import state_manager
from utils.text_chat import text_chat_manager
from utils.audio_processor import audio_processor

# 打印环境变量状态
print("🚀 FastAPI 启动中，打印环境变量状态：")
settings.log()

# 创建FastAPI应用
app = FastAPI(
    title="实时翻译服务",
    description="使用LiveKit进行实时音频翻译",
    version="1.0.0"
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 设置模板
templates = Jinja2Templates(directory="templates")

# 活跃的WebSocket连接
active_websockets: Dict[str, List[WebSocket]] = {}

# 验证LiveKit配置
async def verify_livekit_config():
    if not settings.LIVEKIT_URL:
        raise HTTPException(
            status_code=500,
            detail="LiveKit配置缺失。请确保设置了LIVEKIT_URL环境变量。"
        )
    return True

# 应用启动事件
@app.on_event("startup")
async def startup_event():
    print("🔄 应用启动事件触发...")
    
    # 初始化状态同步
    if settings.REDIS_ENABLED:
        await state_manager.connect()
    
    # 初始化文本聊天管理器
    await text_chat_manager.initialize()
    
    # 如果启用了Twilio，设置入站电话Webhook
    if settings.TWILIO_ENABLED:
        success, message = await sip_manager.setup_inbound_call_webhook()
        print(f"📞 Twilio入站电话Webhook设置: {message}")
    
    print(f"📡 LiveKit URL: {settings.LIVEKIT_URL}")
    print(f"🔊 音频质量适配: {'启用' if settings.AUDIO_QUALITY_ADAPTIVE else '禁用'}")
    print(f"🔊 噪声抑制: {'启用' if settings.AUDIO_NOISE_SUPPRESSION else '禁用'}")
    print(f"🔊 回声消除: {'启用' if settings.AUDIO_ECHO_CANCELLATION else '禁用'}")

# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    print("🔄 应用关闭事件触发...")
    
    # 断开Redis连接
    if settings.REDIS_ENABLED:
        await state_manager.disconnect()

# 根路径 - 返回语言选择页面
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request, _=Depends(verify_livekit_config)):
    # 获取可用区域
    regions = settings.get_available_regions()
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "regions": regions,
            "multi_region": settings.MULTI_REGION,
            "audio_settings": {
                "noise_suppression": settings.AUDIO_NOISE_SUPPRESSION,
                "echo_cancellation": settings.AUDIO_ECHO_CANCELLATION,
                "auto_gain": settings.AUDIO_AUTO_GAIN_CONTROL,
                "adaptive_quality": settings.AUDIO_QUALITY_ADAPTIVE
            }
        }
    )

# 翻译员页面 - 返回翻译员推流界面
@app.get("/interpreter", response_class=HTMLResponse)
async def get_interpreter(request: Request, _=Depends(verify_livekit_config)):
    print("🎤 访问翻译员页面")
    
    # 获取可用区域
    regions = settings.get_available_regions()
    
    # 获取音频处理JavaScript代码
    audio_settings_js = audio_processor.get_javascript_audio_settings()
    audio_stats_js = audio_processor.get_audio_stats_collector_js()
    
    return templates.TemplateResponse(
        "interpreter.html",
        {
            "request": request,
            "regions": regions,
            "multi_region": settings.MULTI_REGION,
            "audio_settings_js": audio_settings_js,
            "audio_stats_js": audio_stats_js,
            "recording_enabled": settings.RECORDING_ENABLED,
            "text_chat_enabled": True
        }
    )

# 添加别名路由 - interpreter.html 指向 interpreter
@app.get("/interpreter.html", response_class=HTMLResponse)
async def get_interpreter_html(request: Request, _=Depends(verify_livekit_config)):
    print("🎤 访问翻译员页面 (通过 /interpreter.html)")
    return await get_interpreter(request, _)

# 添加别名路由 - translator 指向 interpreter
@app.get("/translator", response_class=HTMLResponse)
async def get_translator(request: Request, _=Depends(verify_livekit_config)):
    print("🎤 访问翻译员页面 (通过 /translator)")
    return await get_interpreter(request, _)

# 生成房间访问令牌
@app.get("/token")
async def get_token(
    room: str, 
    identity: str,
    is_publisher: bool = False,
    region: Optional[str] = None,
    _=Depends(verify_livekit_config)
):
    print(f"🟢 收到 token 请求 → room: {room}, identity: {identity}, is_publisher: {is_publisher}, region: {region}")
    
    # 验证参数
    if not room or not identity:
        print("❌ 参数验证失败: room 或 identity 缺失")
        raise HTTPException(
            status_code=400,
            detail="缺少必需的参数: room 和 identity"
        )
    
    # 生成访问令牌
    print("🧠 正在生成 AccessToken...")
    try:
        # 获取区域特定的LiveKit配置
        livekit_url = settings.get_livekit_url_for_region(region)
        livekit_api_key = settings.get_livekit_api_key_for_region(region)
        livekit_secret = settings.get_livekit_secret_for_region(region)
        
        token = generate_token(
            room, 
            identity, 
            is_publisher=is_publisher,
            api_key=livekit_api_key,
            api_secret=livekit_secret
        )
        
        if not token:
            print("❌ Token 生成失败: 返回值为空")
            raise HTTPException(
                status_code=500,
                detail="生成令牌失败"
            )
        
        print("✅ Token 生成成功")
        
        # 记录审计日志
        AuditLogger.log_token_event(
            event="generated",
            room_name=room,
            user_id=identity,
            is_publisher=is_publisher
        )
        
        # 返回令牌和URL信息
        return JSONResponse(content={
            "token": token,
            "url": livekit_url,
            "room": room,
            "identity": identity,
            "region": region or "default"
        })
    except Exception as e:
        print(f"❌ Token 生成失败: {str(e)}")
        
        # 记录错误日志
        AuditLogger.log_error(
            event="token_generation_failed",
            user_id=identity,
            error=e,
            details={"room": room, "is_publisher": is_publisher}
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Token 生成失败: {str(e)}"
        )

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 调试环境变量端点
@app.get("/debug_env")
async def debug_env():
    return {
        "LIVEKIT_API_KEY": "FOUND" if settings.LIVEKIT_API_KEY else "MISSING",
        "LIVEKIT_SECRET": "FOUND" if settings.LIVEKIT_SECRET else "MISSING",
        "LIVEKIT_URL": settings.LIVEKIT_URL or "MISSING",
        "PORT": settings.PORT,
        "MULTI_REGION": settings.MULTI_REGION,
        "REGION": settings.REGION,
        "RECORDING_ENABLED": settings.RECORDING_ENABLED,
        "SIP_ENABLED": settings.SIP_ENABLED,
        "TWILIO_ENABLED": settings.TWILIO_ENABLED,
        "REDIS_ENABLED": settings.REDIS_ENABLED,
        "AUDIO_QUALITY_ADAPTIVE": settings.AUDIO_QUALITY_ADAPTIVE
    }

# WebSocket连接处理
@app.websocket("/ws/{room_name}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_name: str, user_id: str):
    await websocket.accept()
    
    # 添加到活跃连接列表
    if room_name not in active_websockets:
        active_websockets[room_name] = []
    
    active_websockets[room_name].append(websocket)
    
    # 记录审计日志
    AuditLogger.log(
        event="websocket.connected",
        user_id=user_id,
        details={"room_name": room_name}
    )
    
    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "system",
            "message": f"欢迎 {user_id} 加入 {room_name}"
        })
        
        # 获取历史消息
        messages = await text_chat_manager.get_room_messages(room_name, limit=50)
        
        # 发送历史消息
        if messages:
            await websocket.send_json({
                "type": "history",
                "messages": messages
            })
        
        # 获取当前字幕
        captions = await text_chat_manager.get_room_captions(room_name)
        
        # 发送当前字幕
        if captions:
            await websocket.send_json({
                "type": "captions",
                "captions": captions
            })
        
        # 处理WebSocket消息
        while True:
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "text")
                
                if message_type == "text":
                    # 处理文本消息
                    content = message_data.get("content", "").strip()
                    
                    if content:
                        # 发送消息到房间
                        message = await text_chat_manager.send_message(
                            room_name=room_name,
                            user_id=user_id,
                            content=content,
                            message_type="text"
                        )
                        
                        # 广播消息给房间内所有连接
                        for ws in active_websockets.get(room_name, []):
                            if ws != websocket:  # 不发送给自己
                                await ws.send_json({
                                    "type": "message",
                                    "message": message
                                })
                
                elif message_type == "caption":
                    # 处理字幕更新
                    text = message_data.get("text", "")
                    is_final = message_data.get("is_final", False)
                    language = message_data.get("language", "zh-CN")
                    
                    # 更新字幕
                    caption = await text_chat_manager.update_caption(
                        room_name=room_name,
                        user_id=user_id,
                        text=text,
                        is_final=is_final,
                        language=language
                    )
                    
                    # 广播字幕给房间内所有连接
                    for ws in active_websockets.get(room_name, []):
                        if ws != websocket:  # 不发送给自己
                            await ws.send_json({
                                "type": "caption",
                                "user_id": user_id,
                                "caption": caption
                            })
                
                elif message_type == "command":
                    # 处理命令
                    command = message_data.get("command", "")
                    
                    if command == "clear_captions":
                        # 清除字幕
                        await text_chat_manager.update_caption(
                            room_name=room_name,
                            user_id=user_id,
                            text="",
                            is_final=True
                        )
                    
                    elif command == "start_recording" and settings.RECORDING_ENABLED:
                        # 开始录制
                        success, message, recording_id = await recording_manager.start_recording(
                            room_name=room_name,
                            layout="audio-only",
                            preset="audio-only"
                        )
                        
                        # 发送录制状态
                        await websocket.send_json({
                            "type": "recording_status",
                            "success": success,
                            "message": message,
                            "recording_id": recording_id
                        })
                    
                    elif command == "stop_recording" and settings.RECORDING_ENABLED:
                        # 停止录制
                        recording_id = message_data.get("recording_id")
                        
                        if recording_id:
                            success, message = await recording_manager.stop_recording(recording_id)
                            
                            # 发送录制状态
                            await websocket.send_json({
                                "type": "recording_status",
                                "success": success,
                                "message": message,
                                "recording_id": recording_id
                            })
            
            except json.JSONDecodeError:
                # 记录错误日志
                AuditLogger.log_error(
                    event="websocket.invalid_json",
                    user_id=user_id,
                    error=Exception("Invalid JSON"),
                    details={"room_name": room_name, "data": data[:100]}
                )
            
            except Exception as e:
                # 记录错误日志
                AuditLogger.log_error(
                    event="websocket.message_processing_error",
                    user_id=user_id,
                    error=e,
                    details={"room_name": room_name}
                )
    
    except WebSocketDisconnect:
        # 从活跃连接列表中移除
        if room_name in active_websockets and websocket in active_websockets[room_name]:
            active_websockets[room_name].remove(websocket)
            
            if not active_websockets[room_name]:
                del active_websockets[room_name]
        
        # 记录审计日志
        AuditLogger.log(
            event="websocket.disconnected",
            user_id=user_id,
            details={"room_name": room_name}
        )

# 录制管理API
@app.post("/api/recordings/start")
async def start_recording_api(
    room_name: str,
    layout: str = "audio-only",
    preset: str = "audio-only",
    output_type: str = "mp4"
):
    if not settings.RECORDING_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="录制功能未启用"
        )
    
    success, message, recording_id = await recording_manager.start_recording(
        room_name=room_name,
        layout=layout,
        preset=preset,
        output_type=output_type
    )
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=message
        )
    
    return {
        "success": success,
        "message": message,
        "recording_id": recording_id
    }

@app.post("/api/recordings/{recording_id}/stop")
async def stop_recording_api(recording_id: str):
    if not settings.RECORDING_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="录制功能未启用"
        )
    
    success, message = await recording_manager.stop_recording(recording_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=message
        )
    
    return {
        "success": success,
        "message": message
    }

@app.get("/api/recordings/{recording_id}/status")
async def get_recording_status_api(recording_id: str):
    if not settings.RECORDING_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="录制功能未启用"
        )
    
    success, status = await recording_manager.get_recording_status(recording_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=status.get("error", "未找到录制")
        )
    
    return status

@app.get("/api/recordings")
async def list_recordings_api(room_name: Optional[str] = None):
    if not settings.RECORDING_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="录制功能未启用"
        )
    
    recordings = await recording_manager.list_recordings(room_name)
    
    return {
        "recordings": recordings
    }

# SIP电话API
@app.post("/api/calls/outbound")
async def make_outbound_call_api(
    phone_number: str,
    room_name: str,
    language: str = "zh-CN",
    caller_id: Optional[str] = None
):
    if not settings.TWILIO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Twilio电话功能未启用"
        )
    
    success, message, call_id = await sip_manager.make_outbound_call(
        phone_number=phone_number,
        room_name=room_name,
        language=language,
        caller_id=caller_id
    )
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=message
        )
    
    return {
        "success": success,
        "message": message,
        "call_id": call_id
    }

@app.post("/api/calls/{call_id}/end")
async def end_call_api(call_id: str):
    if not settings.TWILIO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Twilio电话功能未启用"
        )
    
    success, message = await sip_manager.end_call(call_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=message
        )
    
    return {
        "success": success,
        "message": message
    }

@app.get("/api/calls/{call_id}/status")
async def get_call_status_api(call_id: str):
    if not settings.TWILIO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Twilio电话功能未启用"
        )
    
    success, status = await sip_manager.get_call_status(call_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=status.get("error", "未找到通话")
        )
    
    return status

@app.get("/api/calls")
async def list_calls_api(room_name: Optional[str] = None):
    if not settings.TWILIO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Twilio电话功能未启用"
        )
    
    calls = await sip_manager.list_calls(room_name)
    
    return {
        "calls": calls
    }

# Twilio入站电话Webhook
@app.post("/api/twilio/incoming")
async def twilio_incoming_webhook(request: Request):
    if not settings.TWILIO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Twilio电话功能未启用"
        )
    
    # 解析Twilio请求
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    from_number = form_data.get("From")
    to_number = form_data.get("To")
    
    if not all([call_sid, from_number, to_number]):
        raise HTTPException(
            status_code=400,
            detail="缺少必需的Twilio参数"
        )
    
    # 处理入站电话
    success, twiml, call_id = await sip_manager.handle_incoming_call(
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number
    )
    
    return HTMLResponse(content=twiml)

# 聊天消息API
@app.post("/api/chat/{room_name}/messages")
async def send_message_api(
    room_name: str,
    user_id: str,
    content: str,
    message_type: str = "text"
):
    if not content.strip():
        raise HTTPException(
            status_code=400,
            detail="消息内容不能为空"
        )
    
    message = await text_chat_manager.send_message(
        room_name=room_name,
        user_id=user_id,
        content=content,
        message_type=message_type
    )
    
    # 广播消息给房间内所有WebSocket连接
    for ws in active_websockets.get(room_name, []):
        await ws.send_json({
            "type": "message",
            "message": message
        })
    
    return message

@app.get("/api/chat/{room_name}/messages")
async def get_messages_api(
    room_name: str,
    limit: int = 100,
    before_id: Optional[str] = None
):
    messages = await text_chat_manager.get_room_messages(
        room_name=room_name,
        limit=limit,
        before_id=before_id
    )
    
    return {
        "messages": messages
    }

@app.post("/api/chat/{room_name}/captions")
async def update_caption_api(
    room_name: str,
    user_id: str,
    text: str,
    is_final: bool = False,
    language: str = "zh-CN"
):
    caption = await text_chat_manager.update_caption(
        room_name=room_name,
        user_id=user_id,
        text=text,
        is_final=is_final,
        language=language
    )
    
    # 广播字幕给房间内所有WebSocket连接
    for ws in active_websockets.get(room_name, []):
        await ws.send_json({
            "type": "caption",
            "user_id": user_id,
            "caption": caption
        })
    
    return caption

@app.get("/api/chat/{room_name}/captions")
async def get_captions_api(room_name: str):
    captions = await text_chat_manager.get_room_captions(room_name)
    
    return {
        "captions": captions
    }

# 主函数
if __name__ == "__main__":
    # 在开发环境中运行应用
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=settings.PORT,
        reload=True
    ) 
