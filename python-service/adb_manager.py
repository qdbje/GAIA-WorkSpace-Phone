"""
ADB 连接管理模块
支持 USB 和 Wi-Fi 连接，设备状态监控，自动重连
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from typing import Optional
import os
import sys
from pathlib import Path

from adbutils import adb

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """设备信息"""

    serial: str
    model: str
    connection_type: str  # "usb" or "wifi"
    status: str  # "device", "offline", "unauthorized"
    ip_address: Optional[str] = None


class ADBManager:
    """
    ADB 连接管理器

    功能：
    - USB 和 Wi-Fi 连接管理
    - 设备状态监控
    - 自动重连机制
    - 多设备支持
    """

    def __init__(self, adb_path: Optional[str] = None):
        """
        初始化 ADB 管理器

        Args:
            adb_path: 自定义 ADB 路径（用于打包后的内置 ADB）
        """
        self.adb_path = self._detect_adb_path(adb_path)
        self.current_device_id: Optional[str] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_monitoring = False

        # 如果找到内置 ADB，优先使用，并更新 PATH，保证 adbutils 也能找到
        if self.adb_path:
            adb_dir = os.path.dirname(self.adb_path)
            os.environ["PATH"] = adb_dir + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"使用 ADB 路径: {self.adb_path}")

    def _detect_adb_path(self, override_path: Optional[str] = None) -> Optional[str]:
        """
        检测 ADB 可执行文件路径

        优先使用显式传入的路径，其次使用打包内置路径，最后回退到系统 adb。
        """
        if override_path:
            return override_path

        candidates = []

        try:
            if getattr(sys, "frozen", False):
                # PyInstaller 打包后的运行目录
                base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
                candidates.extend(
                    [
                        base_path / "resources" / "adb" / "mac" / "adb",
                        base_path / "resources" / "adb" / "adb",
                        base_path / "adb" / "adb",
                    ]
                )
            else:
                # 开发环境：项目根目录下的 resources
                project_root = Path(__file__).parent.parent
                candidates.extend(
                    [
                        project_root / "resources" / "adb" / "mac" / "adb",
                        project_root / "resources" / "adb" / "adb",
                    ]
                )

            for path in candidates:
                if path.exists():
                    return str(path)
        except Exception:
            pass

        # 找不到内置 ADB 时，回退到系统 adb（通过 PATH）
        return None

    async def start(self):
        """启动 ADB 管理器"""
        logger.info("启动 ADB 管理器...")

        # 启动 ADB server
        try:
            adb_cmd = [self.adb_path or "adb", "start-server"]
            subprocess.run(adb_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"启动 ADB server 失败: {e}")

        # 开始监控设备状态
        self._stop_monitoring = False
        self._monitoring_task = asyncio.create_task(self._monitor_devices())

    async def cleanup(self):
        """清理资源"""
        logger.info("清理 ADB 管理器...")
        self._stop_monitoring = True
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

    async def list_devices(self) -> list[dict]:
        """
        获取设备列表

        Returns:
            设备信息列表
        """
        try:
            devices = adb.device_list()
            result = []

            for device in devices:
                try:
                    model = device.shell("getprop ro.product.model").strip()
                    # 使用 get_state() 方法获取设备状态
                    status = device.get_state()

                    # 判断连接类型
                    connection_type = "wifi" if ":" in device.serial else "usb"

                    device_info = {
                        "serial": device.serial,
                        "model": model,
                        "connection_type": connection_type,
                        "status": status,
                    }

                    # 如果是 Wi-Fi 连接，尝试获取 IP
                    if connection_type == "wifi":
                        try:
                            ip = device.serial.split(":")[0]
                            device_info["ip_address"] = ip
                        except Exception:
                            pass

                    result.append(device_info)
                except Exception as e:
                    logger.warning(f"获取设备 {device.serial} 信息失败: {e}")
                    # 在异常处理中也使用 get_state() 方法
                    try:
                        status = device.get_state()
                    except Exception:
                        status = "unknown"
                    result.append(
                        {
                            "serial": device.serial,
                            "model": "Unknown",
                            "connection_type": "unknown",
                            "status": status,
                        }
                    )

            return result
        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            return []

    async def connect(
        self, device_id: Optional[str] = None, connection_type: str = "usb"
    ) -> bool:
        """
        连接设备

        Args:
            device_id: 设备序列号（可选，默认使用第一个可用设备）
            connection_type: 连接类型 ("usb" 或 "wifi")

        Returns:
            是否连接成功
        """
        try:
            devices = await self.list_devices()

            if not devices:
                logger.warning("未检测到设备")
                return False

            # 选择设备
            if device_id:
                # 查找指定设备
                target_device = None
                for device in devices:
                    if device["serial"] == device_id and device["status"] == "device":
                        target_device = device
                        break

                if not target_device:
                    logger.warning(f"未找到设备: {device_id} 或设备状态异常")
                    return False
            else:
                # 使用第一个可用设备
                available_devices = [d for d in devices if d["status"] == "device"]
                if not available_devices:
                    logger.warning("未找到可用设备")
                    return False
                target_device = available_devices[0]

            self.current_device_id = target_device["serial"]
            logger.info(
                f"已连接设备: {self.current_device_id} ({target_device['model']})"
            )
            return True

        except Exception as e:
            logger.error(f"连接设备失败: {e}")
            return False

    async def disconnect(self):
        """断开设备连接"""
        self.current_device_id = None
        logger.info("已断开设备连接")

    def is_connected(self) -> bool:
        """检查是否已连接设备"""
        if not self.current_device_id:
            return False

        try:
            devices = adb.device_list()
            for device in devices:
                if device.serial == self.current_device_id:
                    # 使用 get_state() 方法检查设备状态
                    return device.get_state() == "device"
            return False
        except Exception:
            return False

    def get_current_device_id(self) -> Optional[str]:
        """获取当前设备 ID"""
        return self.current_device_id

    async def get_device_info(self, device_id: Optional[str] = None) -> Optional[dict]:
        """
        获取设备详细信息

        Args:
            device_id: 设备序列号（可选，默认使用当前设备）

        Returns:
            设备信息字典
        """
        target_id = device_id or self.current_device_id
        if not target_id:
            return None

        try:
            device = adb.device(target_id)
            # 使用 get_state() 方法获取设备状态
            status = device.get_state()
            if status != "device":
                return None

            model = device.shell("getprop ro.product.model").strip()
            brand = device.shell("getprop ro.product.brand").strip()
            android_version = device.shell("getprop ro.build.version.release").strip()
            sdk_version = device.shell("getprop ro.build.version.sdk").strip()

            # 获取屏幕尺寸
            try:
                size_output = device.shell("wm size").strip()
                if "Physical size:" in size_output:
                    size_str = size_output.split("Physical size:")[1].strip()
                    width, height = map(int, size_str.split("x"))
                else:
                    width, height = 1080, 1920  # 默认值
            except Exception:
                width, height = 1080, 1920

            connection_type = "wifi" if ":" in target_id else "usb"

            return {
                "serial": target_id,
                "model": model,
                "brand": brand,
                "android_version": android_version,
                "sdk_version": sdk_version,
                "connection_type": connection_type,
                "screen_width": width,
                "screen_height": height,
                "status": status,
            }
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
            return None

    async def _monitor_devices(self):
        """监控设备状态（后台任务）"""
        while not self._stop_monitoring:
            try:
                # 每 5 秒检查一次设备状态
                await asyncio.sleep(5)

                if self.current_device_id:
                    if not self.is_connected():
                        logger.warning(f"设备 {self.current_device_id} 已断开")
                        # 可以在这里触发重连逻辑
                        self.current_device_id = None

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"设备监控错误: {e}")

    async def connect_wifi(self, ip: str, port: int = 5555) -> bool:
        """
        通过 Wi-Fi 连接设备

        Args:
            ip: 设备 IP 地址
            port: ADB 端口（默认 5555）

        Returns:
            是否连接成功
        """
        try:
            # 执行 adb connect
            result = subprocess.run(
                ["adb", "connect", f"{ip}:{port}"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and "connected" in result.stdout:
                # 等待设备状态变为 device
                await asyncio.sleep(2)
                return await self.connect(
                    device_id=f"{ip}:{port}", connection_type="wifi"
                )
            else:
                logger.error(f"Wi-Fi 连接失败: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Wi-Fi 连接异常: {e}")
            return False

    async def disconnect_wifi(self, ip: str, port: int = 5555) -> bool:
        """
        断开 Wi-Fi 设备连接

        Args:
            ip: 设备 IP 地址
            port: ADB 端口（默认 5555）

        Returns:
            是否断开成功
        """
        try:
            address = f"{ip}:{port}"

            # 执行 adb disconnect
            result = subprocess.run(
                ["adb", "disconnect", address],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # 检查断开结果
            output = result.stdout + result.stderr
            if result.returncode == 0:
                # 如果当前连接的设备就是要断开的设备，清除 current_device_id
                if self.current_device_id == address:
                    self.current_device_id = None
                    logger.info(f"已断开当前 Wi-Fi 设备: {address}")
                else:
                    logger.info(f"已断开 Wi-Fi 设备: {address}")
                return True
            else:
                # 即使返回码不为0，也可能是因为设备已经断开
                if (
                    "not connected" in output.lower()
                    or "no such device" in output.lower()
                ):
                    logger.info(f"Wi-Fi 设备 {address} 未连接或已断开")
                    # 如果当前连接的设备就是要断开的设备，清除 current_device_id
                    if self.current_device_id == address:
                        self.current_device_id = None
                    return True
                else:
                    logger.error(f"Wi-Fi 断开失败: {output.strip()}")
                    return False

        except subprocess.TimeoutExpired:
            logger.error(f"断开 Wi-Fi 设备超时: {ip}:{port}")
            return False
        except Exception as e:
            logger.error(f"断开 Wi-Fi 设备异常: {e}")
            return False

    async def enable_wifi_debugging(self, device_id: Optional[str] = None) -> bool:
        """
        启用 Wi-Fi 调试（需要先通过 USB 连接）

        Args:
            device_id: 设备序列号（可选）

        Returns:
            是否成功启用
        """
        target_id = device_id or self.current_device_id
        if not target_id:
            logger.error("未指定设备")
            return False

        try:
            device = adb.device(target_id)
            # 执行 adb tcpip 5555
            device.shell("setprop service.adb.tcp.port 5555")
            device.shell("stop adbd")
            device.shell("start adbd")

            # 或者使用 adb tcpip 命令
            subprocess.run(
                ["adb", "-s", target_id, "tcpip", "5555"], check=True, timeout=10
            )

            logger.info(f"已为设备 {target_id} 启用 Wi-Fi 调试")
            return True
        except Exception as e:
            logger.error(f"启用 Wi-Fi 调试失败: {e}")
            return False
