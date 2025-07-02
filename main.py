import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from token_generator import generate_token
import uvicorn
from config.settings import settings

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

# 验证LiveKit配置
async def verify_livekit_config():
    if not settings.LIVEKIT_URL:
        raise HTTPException(
            status_code=500,
            detail="LiveKit配置缺失。请确保设置了LIVEKIT_URL环境变量。"
        )
    return True

# 根路径 - 返回语言选择页面
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request, _=Depends(verify_livekit_config)):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

# 生成房间访问令牌
@app.get("/token")
async def get_token(
    room: str, 
    identity: str, 
    _=Depends(verify_livekit_config)
):
    print(f"🟢 收到 token 请求 → room: {room}, identity: {identity}")
    
    # 验证参数
    if not room or not identity:
        print("❌ 参数验证失败: room 或 identity 缺失")
        raise HTTPException(
            status_code=400,
            detail="缺少必需的参数: room 和 identity"
        )
    
    # 生成观众访问令牌（非发布者）
    print("🧠 正在生成 AccessToken...")
    try:
        token = generate_token(room, identity, is_publisher=False)
        
        if not token:
            print("❌ Token 生成失败: 返回值为空")
            raise HTTPException(
                status_code=500,
                detail="生成令牌失败"
            )
        
        print("✅ Token 生成成功")
        
        # 返回令牌和URL信息
        return JSONResponse(content={
            "token": token,
            "url": settings.LIVEKIT_URL,
            "room": room,
            "identity": identity
        })
    except Exception as e:
        print(f"❌ Token 生成失败: {str(e)}")
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
        "PORT": settings.PORT
    }

# 应用启动事件
@app.on_event("startup")
async def startup_event():
    print("🔄 应用启动事件触发...")
    # 这里可以添加应用启动时需要执行的逻辑
    print(f"📡 LiveKit URL: {settings.LIVEKIT_URL}")

# 主函数
if __name__ == "__main__":
    # 在开发环境中运行应用
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=settings.PORT,
        reload=True
    ) 
