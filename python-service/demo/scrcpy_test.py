# 利用这个文件，来对scrcpy进行测试
import subprocess
import time
import os
import signal
import sys
import socket
import struct

##  这个方式对scrcpy 2.X有效果，新的不行

# 按照一下流程
# 1. adb push scrcpy-server.jar /data/local/tmp/
# 2. adb shell "cd /data/local/tmp && chmod 777 scrcpy-server.jar"
# 3. adb forward tcp:8886 localabstract:scrcpy
# 4. 启动scrcpy-server.jar
# 5. 对8886建立连接
# 6. 对建立的连接进行发送空包和接收数据

# 全局变量
SCRCPY_SERVER_JAR = os.path.join(
    os.path.dirname(__file__), "../../resources/scrcpy-server.jar"
)
DEVICE_TMP_PATH = "/data/local/tmp/scrcpy-server.jar"
SCRCPY_PORT = 8886
server_process = None


def step1_push_server():
    """步骤1: 推送scrcpy-server.jar到设备"""
    print("[步骤1] 推送scrcpy-server.jar到设备...")

    if not os.path.exists(SCRCPY_SERVER_JAR):
        print(f"错误: 找不到scrcpy-server.jar文件: {SCRCPY_SERVER_JAR}")
        return False

    try:
        result = subprocess.run(
            ["adb", "push", SCRCPY_SERVER_JAR, DEVICE_TMP_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print("✓ scrcpy-server.jar推送成功")
            return True
        else:
            print(f"✗ 推送失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 推送异常: {e}")
        return False


def step2_set_permission():
    """步骤2: 设置scrcpy-server.jar的执行权限"""
    print("[步骤2] 设置文件权限...")

    try:
        result = subprocess.run(
            ["adb", "shell", f"chmod 777 {DEVICE_TMP_PATH}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print("✓ 权限设置成功")
            return True
        else:
            print(f"✗ 权限设置失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 权限设置异常: {e}")
        return False


def step3_setup_port_forward():
    """步骤3: 设置ADB端口转发"""
    print(f"[步骤3] 设置端口转发 tcp:{SCRCPY_PORT} -> localabstract:scrcpy...")

    try:
        result = subprocess.run(
            ["adb", "forward", f"tcp:{SCRCPY_PORT}", "localabstract:scrcpy"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print("✓ 端口转发设置成功")
            return True
        else:
            print(f"✗ 端口转发失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 端口转发异常: {e}")
        return False


def step4_start_scrcpy_server():
    """步骤4: 启动scrcpy-server.jar"""
    global server_process
    print("[步骤4] 启动scrcpy-server...")

    try:
        # scrcpy server 启动命令
        cmd = [
            "adb",
            "shell",
            f"CLASSPATH={DEVICE_TMP_PATH}",
            "app_process",
            "/",
            "com.genymobile.scrcpy.Server",
            "3.3",  # scrcpy版本
            "log_level=info",
            "max_size=1920",
            "bit_rate=8000000",
            "max_fps=60",
            "tunnel_forward=true",
            "control=true",
        ]

        server_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        print("✓ scrcpy-server启动命令已执行")
        print("  等待服务器初始化...")
        time.sleep(2)  # 等待服务器启动

        if server_process.poll() is not None:
            # 进程已退出，读取错误信息
            stdout, stderr = server_process.communicate(timeout=1)
            print(f"✗ 服务器进程异常退出，返回码: {server_process.returncode}")
            print("\n===== 标准输出 (stdout) =====")
            if stdout:
                print(stdout)
            else:
                print("(无输出)")
            print("\n===== 错误输出 (stderr) =====")
            if stderr:
                print(stderr)
            else:
                print("(无错误)")
            print("==============================\n")
            return False

        print("✓ scrcpy-server正在运行")
        return True
    except Exception as e:
        print(f"✗ 启动服务器异常: {e}")
        import traceback

        traceback.print_exc()
        return False


def step5_connect_to_server():
    """步骤5: 连接到scrcpy服务器"""
    print(f"[步骤5] 连接到localhost:{SCRCPY_PORT}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(("localhost", SCRCPY_PORT))
        print("✓ 连接成功")
        return sock
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return None


def step6_communicate_with_server(sock):
    """步骤6: 发送空包并接收数据（原始流调试版）"""
    print("[步骤6] 与服务器通信...")

    try:

        # 2. 设置一个相对长一点的超时时间，避免过早判定为失败
        sock.settimeout(100)

        # 3. 先尝试读取第一包数据
        print("  尝试读取首个数据包...")
        try:
            first = sock.recv(1)
        except socket.timeout:
            print("  首次读取超时，没有收到任何数据")
            return False

        if not first:
            print("  首次读取返回空数据（连接已关闭）")
            return False

        total = len(first)
        print(f"  首包长度: {len(first)} 字节")
        print(f"  首包原始字节: {first!r}")

        # 1. 先发送一个空包（满足“发送空包”的步骤要求）
        print("  发送空包...")
        dummy_byte = b"\x00"
        try:
            # sock.sendall(dummy_byte)
            print("  空包发送完成")
        except Exception as e:
            print(f"  发送空包失败: {e}")

        # 4. 再读取一段时间的数据，作为连通性验证
        print("  继续读取更多数据（最多读取 10 次）...")
        for i in range(10):
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                print(f"  第 {i+1} 次追加读取超时，当前总字节数: {total}")
                break

            if not chunk:
                print("  连接关闭")
                break

            total += len(chunk)
            print(f"  追加数据块 {i+1}: {len(chunk)} 字节，总计 {total} 字节")
            # 为了避免把太多二进制日志刷屏，只打印前 64 字节预览
            print(f"  数据块 {i+1} 前 64 字节预览: {chunk[:64]!r}")

        print("✓ 通信测试完成（原始数据已打印）")
        return True
    except Exception as e:
        print(f"✗ 通信异常: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if sock:
            sock.close()
            print("  连接已关闭")


def cleanup():
    """清理资源"""
    global server_process
    print("\n[清理] 停止服务并清理资源...")

    # 终止服务器进程
    if server_process and server_process.poll() is None:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
            print("✓ 服务器进程已终止")
        except subprocess.TimeoutExpired:
            server_process.kill()
            print("✓ 服务器进程已强制终止")

    # 移除端口转发
    try:
        subprocess.run(
            ["adb", "forward", "--remove", f"tcp:{SCRCPY_PORT}"],
            capture_output=True,
            timeout=5,
        )
        print("✓ 端口转发已移除")
    except:
        pass


def signal_handler(sig, frame):
    """信号处理器"""
    print("\n收到中断信号，正在退出...")
    cleanup()
    sys.exit(0)


def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 50)
    print("scrcpy 测试程序")
    print("=" * 50)

    try:
        # 执行各个步骤
        if not step1_push_server():
            return

        if not step2_set_permission():
            return

        if not step3_setup_port_forward():
            return

        if not step4_start_scrcpy_server():
            return

        sock = step5_connect_to_server()
        if not sock:
            return

        step6_communicate_with_server(sock)

        print("\n" + "=" * 50)
        print("测试完成！")
        print("=" * 50)

    except Exception as e:
        print(f"\n发生错误: {e}")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
