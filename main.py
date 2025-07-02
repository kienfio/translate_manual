import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from token_generator import generate_token
import uvicorn
from dotenv import load_dotenv

# 尝试加载.env文件，但在Render部署时会使用环境变量
load_dotenv()

# 从环境变量获取LiveKit配置
LIVEKIT_URL = os.getenv('LIVEKIT_URL')  # 例如: wss://your-project.livekit.cloud

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
    if not LIVEKIT_URL:
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
    # 验证参数
    if not room or not identity:
        raise HTTPException(
            status_code=400,
            detail="缺少必需的参数: room 和 identity"
        )
    
    # 生成观众访问令牌（非发布者）
    token = generate_token(room, identity, is_publisher=False)
    
    if not token:
        raise HTTPException(
            status_code=500,
            detail="生成令牌失败"
        )
    
    # 返回令牌和URL信息
    return JSONResponse(content={
        "token": token,
        "url": LIVEKIT_URL,
        "room": room,
        "identity": identity
    })

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 应用启动事件
@app.on_event("startup")
async def startup_event():
    print("应用启动中...")
    # 这里可以添加应用启动时需要执行的逻辑
    print(f"LiveKit URL: {LIVEKIT_URL}")

# 主函数
if __name__ == "__main__":
    # 在开发环境中运行应用
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", "8000")),
        reload=True
    ) 