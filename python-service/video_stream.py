"""
Scrcpy 视频流处理模块
管理 Scrcpy Server 生命周期和 H.264 视频流转发
"""

import asyncio
import logging
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Scrcpy 3.x 反向通道配置（与 demo/adb_scrcpy.py 保持一致）
SCRCPY_SOCKET_NAME = "scrcpy"
SCRCPY_LOCAL_PORT = 27183


class VideoStreamManager:
    """
    Scrcpy 视频流管理器

    功能：
    - 启动和管理 Scrcpy Server
    - 接收 H.264 视频流
    - 通过 WebSocket 转发给前端
    - 支持多客户端连接
    """

    def __init__(self, adb_manager):
        """
        初始化视频流管理器

        Args:
            adb_manager: ADB 管理器实例
        """
        self.adb_manager = adb_manager
        self.scrcpy_process: Optional[subprocess.Popen] = None
        self.socket: Optional[socket.socket] = None
        self.clients: Set[WebSocket] = set()
        self._streaming_task: Optional[asyncio.Task] = None
        self._stop_streaming = False

        # 新增：本地监听 socket（反向通道用）
        self._server_socket: Optional[socket.socket] = None
        self._local_port = SCRCPY_LOCAL_PORT

        # 资源路径（支持打包后的路径）
        self.scrcpy_jar_path = self._get_resource_path("scrcpy-server.jar")

    def _get_resource_path(self, filename: str) -> str:
        """
        获取资源文件路径（支持 PyInstaller 打包）

        Args:
            filename: 资源文件名

        Returns:
            资源文件完整路径
        """
        if getattr(sys, "frozen", False):
            # PyInstaller 打包后的路径
            base_path = sys._MEIPASS
        else:
            # 开发环境路径
            base_path = Path(__file__).parent.parent

        # 尝试多个可能的资源目录
        possible_paths = [
            Path(base_path) / "resources" / filename,
            Path(base_path) / filename,
            Path(base_path).parent / "resources" / filename,
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

        # 如果找不到，返回相对路径（运行时可能会失败，但至少不会报错）
        logger.warning(f"未找到资源文件: {filename}，使用相对路径")
        return str(Path(base_path) / "resources" / filename)

    async def start_stream(self, device_id: Optional[str] = None) -> bool:
        """
        启动视频流

        Args:
            device_id: 设备序列号（可选）

        Returns:
            是否启动成功
        """
        if self.scrcpy_process:
            logger.warning("视频流已在运行")
            return True

        target_id = device_id or self.adb_manager.get_current_device_id()
        if not target_id:
            logger.error("未指定设备")
            return False

        try:
            # 推送 scrcpy-server.jar 到设备
            if not os.path.exists(self.scrcpy_jar_path):
                logger.error(f"未找到 scrcpy-server.jar: {self.scrcpy_jar_path}")
                return False
            logger.info(f"scrcpy-server.jar 路径: {self.scrcpy_jar_path}")

            logger.info(f"推送 scrcpy-server.jar 到设备 {target_id}...")
            push_result = subprocess.run(
                [
                    "adb",
                    "-s",
                    target_id,
                    "push",
                    self.scrcpy_jar_path,
                    "/data/local/tmp",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if push_result.returncode != 0:
                logger.error(f"推送 scrcpy-server.jar 失败: {push_result.stderr}")
                return False
            else:
                logger.info(f"推送 scrcpy-server.jar 成功: {push_result.stdout}")

            # adb shell 显示一下/data/local/tmp文件
            ls_result = subprocess.run(
                [
                    "adb",
                    "-s",
                    target_id,
                    "shell",
                    "ls",
                    "-l",
                    "/data/local/tmp/scrcpy-server.jar",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if ls_result.returncode == 0:
                logger.info(f"/data/local/tmp 目录下的文件:\n{ls_result.stdout}")
            else:
                logger.warning(f"查看 /data/local/tmp 目录失败: {ls_result.stderr}")

            # ========== 建立 Scrcpy 3.x 反向通道 ==========
            logger.info(
                f"建立视频流反向隧道: device(localabstract:{SCRCPY_SOCKET_NAME}) -> "
                f"host(tcp:{self._local_port})"
            )
            reverse_result = subprocess.run(
                [
                    "adb",
                    "-s",
                    target_id,
                    "reverse",
                    f"localabstract:{SCRCPY_SOCKET_NAME}",
                    f"tcp:{self._local_port}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if reverse_result.returncode != 0:
                logger.error(f"adb reverse 失败: {reverse_result.stderr}")
                return False

            # 本地启动监听 socket，等待 scrcpy server 主动连接
            try:
                self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                )
                self._server_socket.bind(("0.0.0.0", self._local_port))
                self._server_socket.listen(1)
                self._server_socket.settimeout(10.0)
                logger.info(f"本地视频流 Socket 已启动，监听端口 {self._local_port}")
            except Exception as e:
                logger.error(f"启动本地视频流 Socket 失败: {e}")
                await self.stop_stream()
                return False

            # ========== 启动 scrcpy 3.x server（反向通道模式） ==========
            logger.info("启动 scrcpy server (3.x, tunnel_forward=false)...")
            scrcpy_version = "3.3"

            shell_cmd = (
                "CLASSPATH=/data/local/tmp/scrcpy-server.jar "
                "app_process / com.genymobile.scrcpy.Server "
                f"{scrcpy_version} "
                "log_level=info "
                "video_bit_rate=2000000 "
                "max_fps=30 "
                "tunnel_forward=false "
                "audio=false "
                "control=false "
                "stay_awake=true "
            )

            logger.info(f"执行命令: adb -s {target_id} shell {shell_cmd}")

            self.scrcpy_process = subprocess.Popen(
                [
                    "adb",
                    "-s",
                    target_id,
                    "shell",
                    shell_cmd,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # 等待一小段时间让进程启动
            await asyncio.sleep(0.5)

            # 如果进程立刻退出，直接打印错误
            if self.scrcpy_process.poll() is not None:
                stderr_output = self.scrcpy_process.stderr.read().decode(
                    "utf-8", errors="ignore"
                )
                stdout_output = self.scrcpy_process.stdout.read().decode(
                    "utf-8", errors="ignore"
                )
                logger.error(
                    f"scrcpy server 进程启动后立即退出，返回码: {self.scrcpy_process.returncode}"
                )
                logger.error("=" * 60)
                logger.error("scrcpy server 启动失败，错误信息如下：")
                if stderr_output:
                    logger.error(f"STDERR:\n{stderr_output}")
                else:
                    logger.error("STDERR: (空)")
                if stdout_output:
                    logger.error(f"STDOUT:\n{stdout_output}")
                else:
                    logger.error("STDOUT: (空)")
                logger.error("=" * 60)

                await self._check_scrcpy_process_on_device(target_id)
                await self.stop_stream()
                return False

            # ========== 等待设备连接到本地 Socket ==========
            logger.info("等待设备连接到本地视频流 Socket...")
            try:
                conn, addr = await asyncio.to_thread(self._server_socket.accept)
                logger.info(f"接受来自 {addr} 的 Scrcpy 视频流连接")
                self.socket = conn
                # 单连接场景，监听 socket 不再需要
                try:
                    self._server_socket.close()
                except Exception:
                    pass
                self._server_socket = None
            except socket.timeout:
                logger.error(
                    "等待设备连接超时，请检查 adb reverse 和 scrcpy server 是否正常"
                )
                # 如进程已退出，尝试打印错误
                if self.scrcpy_process and self.scrcpy_process.poll() is not None:
                    stderr_output = self.scrcpy_process.stderr.read().decode(
                        "utf-8", errors="ignore"
                    )
                    stdout_output = self.scrcpy_process.stdout.read().decode(
                        "utf-8", errors="ignore"
                    )
                    logger.error(
                        f"scrcpy server 进程已退出，返回码: {self.scrcpy_process.returncode}"
                    )
                    if stderr_output:
                        logger.error(f"stderr: {stderr_output}")
                    if stdout_output:
                        logger.error(f"stdout: {stdout_output}")
                await self.stop_stream()
                return False
            except Exception as e:
                logger.error(f"接受 scrcpy 连接失败: {e}")
                await self.stop_stream()
                return False

            # ========== scrcpy 3.x 媒体通道握手 ==========
            try:
                # 设置超时，避免 recv 永久阻塞
                self.socket.settimeout(10.0)
                logger.info("开始 scrcpy 3.x 媒体通道握手...")

                # 1. 设备名称（固定 64 字节，填充 0）
                device_name_bytes = await asyncio.to_thread(
                    self._recv_exact, self.socket, 64
                )
                device_name = device_name_bytes.decode("utf-8", errors="ignore").strip(
                    "\x00"
                )

                # 2. Codec ID（4 字节）
                codec_id = await asyncio.to_thread(self._recv_exact, self.socket, 4)

                # 3. 宽高（4 + 4 字节，big-endian）
                width_bytes = await asyncio.to_thread(self._recv_exact, self.socket, 4)
                height_bytes = await asyncio.to_thread(self._recv_exact, self.socket, 4)
                width = int.from_bytes(width_bytes, "big")
                height = int.from_bytes(height_bytes, "big")

                logger.info(
                    f"scrcpy 设备信息: 名称={device_name}, "
                    f"codec_id={codec_id}, 分辨率={width}x{height}"
                )

                # 设置为非阻塞模式，开始接收视频流
                self.socket.setblocking(False)
            except socket.timeout:
                logger.error("scrcpy 媒体通道握手超时")
                await self.stop_stream()
                return False
            except Exception as e:
                logger.error(f"scrcpy 媒体通道握手失败: {e}")
                await self.stop_stream()
                return False

            # 开始转发视频流
            self._stop_streaming = False
            self._streaming_task = asyncio.create_task(self._stream_loop())

            logger.info("视频流已启动")
            return True

        except Exception as e:
            logger.error(f"启动视频流失败: {e}")
            await self.stop_stream()
            return False

    async def stop_stream(self):
        """停止视频流"""
        self._stop_streaming = True

        if self._streaming_task:
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                pass

        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

        # 关闭本地监听 socket
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        if self.scrcpy_process:
            try:
                self.scrcpy_process.terminate()
                self.scrcpy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.scrcpy_process.kill()
            except Exception:
                pass
            self.scrcpy_process = None

        # 清理反向隧道
        target_id = self.adb_manager.get_current_device_id()
        if target_id:
            try:
                subprocess.run(
                    [
                        "adb",
                        "-s",
                        target_id,
                        "reverse",
                        "--remove",
                        f"localabstract:{SCRCPY_SOCKET_NAME}",
                    ],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass

        logger.info("视频流已停止")

    async def add_client(self, websocket: WebSocket):
        """
        添加 WebSocket 客户端

        Args:
            websocket: WebSocket 连接
        """
        self.clients.add(websocket)
        logger.info(f"添加视频流客户端，当前客户端数: {len(self.clients)}")

        # 如果还没有启动流，则启动
        if not self.scrcpy_process:
            await self.start_stream()

        try:
            # 保持连接，直到客户端断开
            while True:
                # 接收 ping/pong 消息（如果有）
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                except asyncio.TimeoutError:
                    # 超时是正常的，继续循环
                    pass
                except Exception:
                    # 客户端断开
                    break

        except Exception as e:
            logger.debug(f"客户端连接异常: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"移除视频流客户端，当前客户端数: {len(self.clients)}")

            # 如果没有客户端了，停止流
            if len(self.clients) == 0:
                await self.stop_stream()

    async def _stream_loop(self):
        """视频流转发循环"""
        buffer_size = 65536  # 64KB 缓冲区
        # buffer_size = 16384  # 调整为16K
        buffer = bytearray()

        # 缓存 SPS/PPS/IDR 帧，用于新客户端连接
        sps_pps_idr_cache = None

        try:
            while not self._stop_streaming:
                try:
                    # 从 socket 读取数据
                    data = await asyncio.to_thread(self.socket.recv, buffer_size)
                    if not data:
                        logger.warning("视频流 socket 关闭")
                        break

                    buffer.extend(data)

                    # 查找 H.264 NAL 单元边界（0x00 0x00 0x00 0x01 或 0x00 0x00 0x01）
                    while True:
                        # 查找起始码
                        start_code_4 = buffer.find(b"\x00\x00\x00\x01")
                        start_code_3 = buffer.find(b"\x00\x00\x01")

                        if start_code_4 == -1 and start_code_3 == -1:
                            # 没有找到起始码，继续接收数据
                            break

                        # 选择更早的起始码
                        if start_code_4 == -1:
                            start_pos = start_code_3
                            start_code_len = 3
                        elif start_code_3 == -1:
                            start_pos = start_code_4
                            start_code_len = 4
                        else:
                            if start_code_3 < start_code_4:
                                start_pos = start_code_3
                                start_code_len = 3
                            else:
                                start_pos = start_code_4
                                start_code_len = 4

                        # 查找下一个起始码
                        next_start_code_4 = buffer.find(
                            b"\x00\x00\x00\x01", start_pos + start_code_len
                        )
                        next_start_code_3 = buffer.find(
                            b"\x00\x00\x01", start_pos + start_code_len
                        )

                        if next_start_code_4 == -1 and next_start_code_3 == -1:
                            # 没有找到下一个起始码，继续接收数据
                            break

                        # 选择更早的下一个起始码
                        if next_start_code_4 == -1:
                            end_pos = next_start_code_3
                        elif next_start_code_3 == -1:
                            end_pos = next_start_code_4
                        else:
                            end_pos = min(next_start_code_3, next_start_code_4)

                        # 提取 NAL 单元
                        nal_unit = bytes(buffer[start_pos:end_pos])

                        # 检查 NAL 单元类型
                        if len(nal_unit) > start_code_len:
                            nal_type = (nal_unit[start_code_len] >> 1) & 0x3F

                            # SPS (7), PPS (8), IDR (5)
                            if nal_type in [5, 7, 8]:
                                # 缓存关键帧
                                if sps_pps_idr_cache is None:
                                    sps_pps_idr_cache = bytearray()
                                sps_pps_idr_cache.extend(nal_unit)

                        # 发送给所有客户端
                        if self.clients:
                            disconnected = set()
                            for client in self.clients:
                                try:
                                    await client.send_bytes(nal_unit)
                                except Exception:
                                    disconnected.add(client)

                            # 移除断开的客户端
                            for client in disconnected:
                                self.clients.discard(client)

                        # 移除已处理的数据
                        buffer = buffer[end_pos:]

                except socket.error as e:
                    if e.errno == socket.EAGAIN or e.errno == socket.EWOULDBLOCK:
                        # 没有数据可读，继续
                        await asyncio.sleep(0.01)
                    else:
                        logger.error(f"Socket 错误: {e}")
                        break
                except Exception as e:
                    logger.error(f"视频流转发错误: {e}")
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"视频流循环错误: {e}")
        finally:
            logger.info("视频流转发循环已结束")

    async def cleanup(self):
        """清理资源"""
        await self.stop_stream()
        self.clients.clear()

    async def _check_scrcpy_process_on_device(self, device_id: str):
        """
        通过 adb 检查设备上的 scrcpy 进程

        Args:
            device_id: 设备序列号
        """
        try:
            logger.info("=" * 60)
            logger.info("检查设备上的进程状态:")

            # 方法1: 直接执行 ps 然后过滤（更可靠）
            check_process = subprocess.run(
                ["adb", "-s", device_id, "shell", "ps", "-A"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if check_process.returncode == 0:
                process_list = check_process.stdout
                # 查找 app_process 进程
                app_process_lines = [
                    line for line in process_list.split("\n") if "app_process" in line
                ]
                if app_process_lines:
                    logger.info(f"找到 app_process 进程:")
                    for line in app_process_lines:
                        logger.info(f"  {line.strip()}")
                else:
                    logger.warning("未找到 app_process 进程")

                # 查找 scrcpy 相关进程
                scrcpy_lines = [
                    line
                    for line in process_list.split("\n")
                    if "scrcpy" in line.lower()
                ]
                if scrcpy_lines:
                    logger.info(f"找到 scrcpy 相关进程:")
                    for line in scrcpy_lines:
                        logger.info(f"  {line.strip()}")
                else:
                    logger.warning("未找到 scrcpy 相关进程")
            else:
                logger.warning(f"执行 ps 命令失败: {check_process.stderr}")

            # 方法2: 使用 pgrep（如果设备支持）
            try:
                check_pgrep = subprocess.run(
                    ["adb", "-s", device_id, "shell", "pgrep", "-f", "app_process"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if check_pgrep.returncode == 0 and check_pgrep.stdout.strip():
                    logger.info(
                        f"通过 pgrep 找到进程 PID: {check_pgrep.stdout.strip()}"
                    )
            except Exception:
                pass  # pgrep 可能不可用，忽略

            logger.info("=" * 60)
        except Exception as e:
            logger.warning(f"检查设备进程时出错: {e}")

    def _recv_exact(self, sock: socket.socket, size: int) -> bytes:
        """
        阻塞读取指定长度的数据，直到读满或连接关闭。

        Args:
            sock: socket 对象
            size: 需要读取的字节数

        Returns:
            bytes: 读取到的完整数据

        Raises:
            ConnectionError: 如果连接在读满之前关闭
        """
        data = bytearray()
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("socket 在读取过程中关闭")
            data.extend(chunk)
        return bytes(data)
