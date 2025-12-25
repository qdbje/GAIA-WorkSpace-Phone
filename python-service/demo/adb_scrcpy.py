import subprocess
import socket
import time
import sys
import os

# --- 配置部分 ---
ADB_PATH = "adb"
SERVER_FILE_PATH = (
    "../../resources/scrcpy-server.jar"  # 必须是 scrcpy 3.x 版本的 server 文件
)
DEVICE_SERVER_PATH = "/data/local/tmp/scrcpy-server.jar"
SOCKET_NAME = "scrcpy"  # 手机端尝试连接的抽象 socket 名称
LOCAL_PORT = 27183  # PC 端监听的端口


def run_adb_command(cmd):
    full_cmd = [ADB_PATH] + cmd
    print(f"[ADB] 执行: {' '.join(full_cmd)}")
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ADB] 错误: {result.stderr}")
        return None
    return result.stdout.strip()


def prepare_server():
    """推送 Server 文件"""
    if not os.path.exists(SERVER_FILE_PATH):
        print(f"错误: 本地找不到 {SERVER_FILE_PATH}，请确保下载了 Scrcpy 3.x server")
        sys.exit(1)
    print("正在推送 server 文件到手机...")
    run_adb_command(["push", SERVER_FILE_PATH, DEVICE_SERVER_PATH])


def setup_reverse_tunnel():
    """
    关键步骤：建立反向隧道
    告诉手机：连接 localabstract:scrcpy -> 转发到 PC tcp:27183
    """
    print(f"设置反向隧道: 手机({SOCKET_NAME}) -> PC({LOCAL_PORT})")
    # 注意这里是 reverse，不是 forward
    run_adb_command(["reverse", f"localabstract:{SOCKET_NAME}", f"tcp:{LOCAL_PORT}"])


def start_socket_server():
    """PC 端启动监听，等待手机连过来"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 允许端口复用，防止程序关闭后端口被占用
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        s.bind(("0.0.0.0", LOCAL_PORT))
        s.listen(1)  # 监听一个连接
        print(f"PC Socket 服务已启动，正在监听端口 {LOCAL_PORT}，等待手机连接...")
        return s
    except Exception as e:
        print(f"监听端口失败: {e}")
        sys.exit(1)


def start_scrcpy_server_process():
    """在手机上启动 scrcpy server (3.x 参数)"""

    # Scrcpy 3.x 启动参数
    # 注意: tunnel_forward=false 是默认值，这里显式写出来为了演示
    # scid: Server Connection ID，用于区分不同的连接，这里简略处理
    cmd = [
        ADB_PATH,
        "shell",
        f"CLASSPATH={DEVICE_SERVER_PATH}",
        "app_process",
        "/",
        "com.genymobile.scrcpy.Server",
        "3.3",  # 版本号必须匹配
        "log_level=info",
        "video_bit_rate=2000000",
        "max_fps=30",
        "tunnel_forward=false",  # 关键：关闭正向隧道，开启反向连接模式
        "audio=false",  # 3.x 默认开启音频，如果只要视频建议先关掉，因为音频走另一个 Socket
        "control=false",  # 关闭控制，纯接收视频
        # "send_device_meta=true",
        # "send_frame_meta=true",
        # "send_dummy_byte=true" # 3.x 协议握手细节可能需要这个
    ]

    print("正在启动手机端 Scrcpy Server...")
    # 非阻塞启动
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process


def handle_connection(conn):
    """处理连接后的数据"""
    print(">>> 手机已连接到 PC！")

    try:
        # Scrcpy 3.x 协议握手
        # 注意：3.x 的握手协议比 2.x 更复杂，可能包含 dummy byte

        # 1. 接收设备名 (64 bytes)
        device_name = conn.recv(64).decode("utf-8", errors="ignore").strip("\x00")
        print(f"设备名称: {device_name}")

        # 2. 接收 Codec ID (4 bytes) - 例如 h264
        codec_id = conn.recv(4)
        print(f"Codec ID: {codec_id}")

        # 3. 接收宽高 (4 bytes + 4 bytes)
        width_bytes = conn.recv(4)
        height_bytes = conn.recv(4)
        width = int.from_bytes(width_bytes, "big")
        height = int.from_bytes(height_bytes, "big")
        print(f"视频尺寸: {width}x{height}")

        print("开始接收视频流数据 (按 Ctrl+C 退出)...")

        # 循环接收数据流
        while True:
            data = conn.recv(4096)  # 接收 4KB 数据块
            if not data:
                break
            # 这里通常需要将 data 喂给解码器
            print(f"收到 {len(data)} bytes", end="\r")
            ## 调用opencv 显示
            ##cv2.imshow("Scrcpy", data)

    except Exception as e:
        print(f"数据处理出错: {e}")
    finally:
        conn.close()


def main():
    # 1. 清理环境
    run_adb_command(["reverse", "--remove-all"])

    # 2. 准备文件
    prepare_server()

    # 3. 建立反向隧道 (Phone -> PC)
    setup_reverse_tunnel()

    # 4. PC 先启动监听
    server_socket = start_socket_server()

    # 5. 启动手机 Server (它会尝试连接 localabstract:scrcpy)
    scrcpy_proc = start_scrcpy_server_process()

    try:
        # 设置 accept 超时，防止 Server 启动失败导致死等
        server_socket.settimeout(5.0)

        # 6. 等待连接
        conn, addr = server_socket.accept()
        print(f"接受来自 {addr} 的连接")

        # 恢复阻塞模式（可选，看具体需求）
        conn.settimeout(None)

        # 7. 处理数据
        handle_connection(conn)

    except socket.timeout:
        print("等待手机连接超时！请检查 adb reverse 是否成功，或 server 是否报错。")
        # 打印 server 报错信息
        if scrcpy_proc.poll() is not None:
            print("Server 错误输出:")
            print(scrcpy_proc.stderr.read().decode())

    except KeyboardInterrupt:
        print("\n用户中断")

    finally:
        print("正在清理...")
        if "conn" in locals():
            conn.close()
        server_socket.close()
        scrcpy_proc.terminate()
        run_adb_command(["reverse", "--remove", f"localabstract:{SOCKET_NAME}"])


if __name__ == "__main__":
    main()
