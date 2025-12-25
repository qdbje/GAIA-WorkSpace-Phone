"""
GAIA-WorkSpace-Phone Python 后端服务
FastAPI 主服务器，提供 HTTP/WebSocket API
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径
# 这样可以从任何位置运行脚本
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 添加当前目录到 Python 路径（用于相对导入）
_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 使用相对导入（从当前目录）
from adb_manager import ADBManager
from ai_core import AICore
from video_stream import VideoStreamManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局管理器实例
adb_manager: Optional[ADBManager] = None
video_stream_manager: Optional[VideoStreamManager] = None
ai_core: Optional[AICore] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global adb_manager, video_stream_manager, ai_core

    # 启动时初始化
    logger.info("初始化服务组件...")
    adb_manager = ADBManager()
    video_stream_manager = VideoStreamManager(adb_manager)
    ai_core = AICore(adb_manager)

    # 启动 ADB 管理器
    await adb_manager.start()

    yield

    # 关闭时清理
    logger.info("清理服务组件...")
    if video_stream_manager:
        await video_stream_manager.cleanup()
    if adb_manager:
        await adb_manager.cleanup()
    if ai_core:
        await ai_core.cleanup()


# 创建 FastAPI 应用
app = FastAPI(
    title="GAIA-WorkSpace-Phone API",
    description="Android 设备自动化控制 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源，生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """根路径"""
    return {"message": "GAIA-WorkSpace-Phone API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "adb_connected": adb_manager.is_connected() if adb_manager else False,
    }


# ==================== ADB 连接管理 API ====================


@app.get("/api/devices")
async def list_devices():
    """获取设备列表"""
    logger.info("获取设备列表")
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    devices = await adb_manager.list_devices()
    return {"devices": devices}


@app.post("/api/connect")
async def connect_device(device_id: Optional[str] = None, connection_type: str = "usb"):
    """连接设备"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    try:
        success = await adb_manager.connect(device_id, connection_type)
        if success:
            device_info = await adb_manager.get_device_info(device_id)
            return {"success": True, "device": device_info}
        else:
            return JSONResponse(
                {"success": False, "error": "Failed to connect"}, status_code=400
            )
    except Exception as e:
        logger.error(f"连接设备失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/disconnect")
async def disconnect_device():
    """断开设备连接"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    await adb_manager.disconnect()
    return {"success": True}


@app.get("/api/device/info")
async def get_device_info():
    """获取当前设备信息"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    device_info = await adb_manager.get_device_info()
    if device_info:
        return {"device": device_info}
    else:
        return JSONResponse({"error": "No device connected"}, status_code=404)


# ==================== 视频流 API ====================


@app.websocket("/api/video/stream")
async def video_stream(websocket: WebSocket):
    """视频流 WebSocket 端点"""
    if not video_stream_manager:
        await websocket.close(code=1003, reason="Video stream manager not initialized")
        return

    await websocket.accept()
    logger.info("视频流客户端已连接")

    try:
        await video_stream_manager.add_client(websocket)
    except WebSocketDisconnect:
        logger.info("视频流客户端已断开")
    except Exception as e:
        logger.error(f"视频流错误: {e}")
        await websocket.close(code=1011, reason=str(e))


# ==================== AI 任务执行 API ====================


@app.post("/api/ai/init")
async def init_ai(
    base_url: str,
    api_key: str,
    model_name: str = "autoglm-phone-9b",
    device_id: Optional[str] = None,
    lang: str = "cn",
):
    """初始化 AI 核心模块"""
    if not ai_core:
        return JSONResponse({"error": "AI core not initialized"}, status_code=500)

    try:
        await ai_core.initialize(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            device_id=device_id,
            lang=lang,
        )
        return {"success": True}
    except Exception as e:
        logger.error(f"初始化 AI 失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/ai/chat")
async def chat_task(task: str):
    """执行 AI 任务（同步）"""
    if not ai_core:
        return JSONResponse({"error": "AI core not initialized"}, status_code=500)

    if not ai_core.is_initialized():
        return JSONResponse(
            {"error": "AI core not initialized. Call /api/ai/init first"},
            status_code=400,
        )

    try:
        result = await ai_core.run_task(task)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"执行任务失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.websocket("/api/ai/chat/stream")
async def chat_task_stream(websocket: WebSocket):
    """执行 AI 任务（流式，实时推送进度）"""
    # 必须先接受连接，然后才能关闭
    await websocket.accept()
    logger.info("AI 任务流 WebSocket 客户端已连接")

    # 检查 AI core 是否存在
    if not ai_core:
        logger.error("AI core 未初始化")
        await websocket.send_json(
            {"type": "error", "message": "AI core not initialized"}
        )
        await websocket.close(code=1003, reason="AI core not initialized")
        return

    # 检查 AI core 是否已初始化
    if not ai_core.is_initialized():
        logger.error("AI core 未初始化，需要先调用 /api/ai/init")
        await websocket.send_json(
            {
                "type": "error",
                "message": "AI core not initialized. Call /api/ai/init first",
            }
        )
        await websocket.close(
            code=1003, reason="AI core not initialized. Call /api/ai/init first"
        )
        return

    try:
        # 接收任务
        data = await websocket.receive_json()
        task = data.get("task", "")
        logger.info(f"收到 AI 任务: {task}")

        if not task:
            logger.error("任务为空")
            await websocket.send_json({"type": "error", "message": "Task is required"})
            await websocket.close()
            return

        # 流式执行任务
        logger.info(f"开始流式执行任务: {task}")
        async for event in ai_core.run_task_stream(task):
            logger.debug(f"发送事件: {event}")
            await websocket.send_json(event)

        # run_task_stream 已经发送了 finished 消息，这里不需要再发送
        logger.info("任务执行完成")
    except WebSocketDisconnect:
        logger.info("AI 任务流客户端已断开")
    except Exception as e:
        logger.error(f"AI 任务流错误: {e}", exc_info=True)
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close(code=1011, reason=str(e))


@app.post("/api/ai/reset")
async def reset_ai():
    """重置 AI 状态"""
    if not ai_core:
        return JSONResponse({"error": "AI core not initialized"}, status_code=500)

    ai_core.reset()
    return {"success": True}


@app.get("/api/ai/status")
async def get_ai_status():
    """获取 AI 状态"""
    if not ai_core:
        return JSONResponse({"error": "AI core not initialized"}, status_code=500)

    status = ai_core.get_status()
    return status


# ==================== 手动控制 API ====================


@app.post("/api/control/tap")
async def manual_tap(x: int, y: int):
    """手动点击操作"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    if not adb_manager.is_connected():
        return JSONResponse({"error": "No device connected"}, status_code=400)

    try:
        from phone_agent.adb import tap

        device_id = adb_manager.get_current_device_id()
        tap(x, y, device_id)
        return {"success": True}
    except Exception as e:
        logger.error(f"点击操作失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/control/swipe")
async def manual_swipe(
    start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 300
):
    """手动滑动操作"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    if not adb_manager.is_connected():
        return JSONResponse({"error": "No device connected"}, status_code=400)

    try:
        from phone_agent.adb import swipe

        device_id = adb_manager.get_current_device_id()
        swipe(
            start_x, start_y, end_x, end_y, duration_ms=duration_ms, device_id=device_id
        )
        return {"success": True}
    except Exception as e:
        logger.error(f"滑动操作失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/control/back")
async def manual_back():
    """手动返回操作"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    if not adb_manager.is_connected():
        return JSONResponse({"error": "No device connected"}, status_code=400)

    try:
        from phone_agent.adb import back

        device_id = adb_manager.get_current_device_id()
        back(device_id)
        return {"success": True}
    except Exception as e:
        logger.error(f"返回操作失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/control/home")
async def manual_home():
    """手动主页操作"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    if not adb_manager.is_connected():
        return JSONResponse({"error": "No device connected"}, status_code=400)

    try:
        from phone_agent.adb import home

        device_id = adb_manager.get_current_device_id()
        home(device_id)
        return {"success": True}
    except Exception as e:
        logger.error(f"主页操作失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/control/recent")
async def manual_recent():
    """手动多任务操作"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    if not adb_manager.is_connected():
        return JSONResponse({"error": "No device connected"}, status_code=400)

    try:
        from phone_agent.adb import recent_apps

        device_id = adb_manager.get_current_device_id()
        recent_apps(device_id)
        return {"success": True}
    except Exception as e:
        logger.error(f"多任务操作失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/screenshot")
async def get_screenshot():
    """获取设备截图"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    if not adb_manager.is_connected():
        return JSONResponse({"error": "No device connected"}, status_code=400)

    try:
        from phone_agent.adb import get_screenshot

        device_id = adb_manager.get_current_device_id()
        screenshot = get_screenshot(device_id)
        return {
            "base64": screenshot.base64_data,
            "width": screenshot.width,
            "height": screenshot.height,
        }
    except Exception as e:
        logger.error(f"获取截图失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/wifi/connect")
async def connect_wifi_device(ip: str = Query(...), port: int = Query(5555)):
    """通过 Wi-Fi 连接设备"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    try:
        success = await adb_manager.connect_wifi(ip, port)
        if success:
            # 刷新设备列表后返回成功
            return {"success": True, "message": f"已连接到 {ip}:{port}"}
        else:
            return JSONResponse(
                {"success": False, "error": f"无法连接到 {ip}:{port}"}, status_code=400
            )
    except Exception as e:
        logger.error(f"Wi-Fi 连接失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/wifi/disconnect")
async def disconnect_wifi_device(ip: str = Query(...), port: int = Query(5555)):
    """断开 Wi-Fi 设备连接"""
    if not adb_manager:
        return JSONResponse({"error": "ADB manager not initialized"}, status_code=500)

    try:
        success = await adb_manager.disconnect_wifi(ip, port)
        if success:
            return {"success": True, "message": f"已断开 {ip}:{port}"}
        else:
            return JSONResponse(
                {"success": False, "error": f"无法断开 {ip}:{port}"}, status_code=400
            )
    except Exception as e:
        logger.error(f"Wi-Fi 断开失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


def main():
    """主函数"""
    # 从环境变量或命令行参数获取端口
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    # 如果端口为 0，让系统自动分配
    if port == 0:
        # 绑定到随机端口，并打印到 stdout 供 Electron 主进程读取
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        print(f"PORT={port}", flush=True)

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
