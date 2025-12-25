"""
AI 核心模块
集成 phone_agent，提供任务执行和流式反馈
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional

from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig, StepResult
from phone_agent.model import ModelConfig

logger = logging.getLogger(__name__)


class AICore:
    """
    AI 核心模块

    功能：
    - 初始化 PhoneAgent
    - 执行自然语言任务
    - 提供流式执行反馈
    - 状态管理
    """

    def __init__(self, adb_manager):
        """
        初始化 AI 核心模块

        Args:
            adb_manager: ADB 管理器实例
        """
        self.adb_manager = adb_manager
        self.agent: Optional[PhoneAgent] = None
        self._initialized = False

    async def initialize(
        self,
        base_url: str,
        api_key: str,
        model_name: str = "autoglm-phone-9b",
        device_id: Optional[str] = None,
        lang: str = "cn",
        max_steps: int = 100,
    ):
        """
        初始化 AI 核心模块

        Args:
            base_url: 模型服务 API 地址
            api_key: API 密钥
            model_name: 模型名称
            device_id: 设备 ID（可选）
            lang: 语言（"cn" 或 "en"）
            max_steps: 最大执行步数
        """
        try:
            # 获取设备 ID
            target_device_id = device_id or self.adb_manager.get_current_device_id()
            if not target_device_id:
                raise ValueError("未连接设备，请先连接设备")

            # 创建模型配置
            model_config = ModelConfig(
                base_url=base_url,
                api_key=api_key,
                model_name=model_name,
            )

            # 创建 Agent 配置
            agent_config = AgentConfig(
                device_id=target_device_id,
                lang=lang,
                max_steps=max_steps,
                verbose=False,  # 不在控制台输出，通过流式 API 返回
            )

            # 创建 PhoneAgent 实例
            self.agent = PhoneAgent(
                model_config=model_config,
                agent_config=agent_config,
                confirmation_callback=self._confirmation_callback,
                takeover_callback=self._takeover_callback,
            )

            self._initialized = True
            logger.info("AI 核心模块初始化成功")

        except Exception as e:
            logger.error(f"初始化 AI 核心模块失败: {e}")
            self._initialized = False
            raise

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized and self.agent is not None

    async def run_task(self, task: str) -> str:
        """
        执行任务（同步）

        Args:
            task: 自然语言任务描述

        Returns:
            任务执行结果
        """
        if not self.is_initialized():
            raise ValueError("AI 核心模块未初始化")

        # 在执行新任务前，重置 Agent 状态
        logger.info("重置 Agent 状态，清空历史对话...")
        self.agent.reset()

        # 在后台线程中执行（避免阻塞）
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.agent.run, task)
        return result

    async def run_task_stream(self, task: str) -> AsyncGenerator[dict, None]:
        """
        执行任务（流式，实时推送进度）

        Args:
            task: 自然语言任务描述

        Yields:
            执行进度事件字典
        """
        if not self.is_initialized():
            logger.error("AI 核心模块未初始化")
            yield {"type": "error", "message": "AI 核心模块未初始化"}
            return

        try:
            # 在执行新任务前，重置 Agent 状态，清空历史对话
            logger.info("重置 Agent 状态，清空历史对话...")
            self.agent.reset()

            # 发送开始事件
            logger.info(f"开始执行任务: {task}")
            yield {"type": "started", "task": task}

            # 执行第一步
            logger.info("执行第一步，准备调用模型...")
            loop = asyncio.get_event_loop()
            step_result = await loop.run_in_executor(None, self.agent.step, task)
            logger.info(
                f"第一步执行完成: thinking={step_result.thinking[:50]}..., action={step_result.action}"
            )

            # 发送第一步结果
            yield {
                "type": "step",
                "step_count": self.agent.step_count,
                "thinking": step_result.thinking,
                "action": step_result.action,
                "success": step_result.success,
            }

            # 如果已完成，返回
            if step_result.finished:
                logger.info(f"任务在第一步完成: {step_result.message}")
                yield {
                    "type": "finished",
                    "message": step_result.message or "任务完成",
                    "step_count": self.agent.step_count,
                }
                return

            # 继续执行后续步骤
            while self.agent.step_count < self.agent.agent_config.max_steps:
                # 执行下一步
                logger.info(f"执行第 {self.agent.step_count + 1} 步...")
                step_result = await loop.run_in_executor(None, self.agent.step)
                logger.info(
                    f"第 {self.agent.step_count} 步执行完成: thinking={step_result.thinking[:50] if step_result.thinking else ''}..."
                )

                # 发送步骤结果
                yield {
                    "type": "step",
                    "step_count": self.agent.step_count,
                    "thinking": step_result.thinking,
                    "action": step_result.action,
                    "success": step_result.success,
                }

                # 如果已完成，返回
                if step_result.finished:
                    logger.info(
                        f"任务在第 {self.agent.step_count} 步完成: {step_result.message}"
                    )
                    yield {
                        "type": "finished",
                        "message": step_result.message or "任务完成",
                        "step_count": self.agent.step_count,
                    }
                    return

                # 短暂延迟，避免过快执行
                await asyncio.sleep(0.1)

            # 达到最大步数
            logger.warning(f"达到最大执行步数: {self.agent.step_count}")
            yield {
                "type": "finished",
                "message": "达到最大执行步数",
                "step_count": self.agent.step_count,
            }

        except Exception as e:
            logger.error(f"执行任务失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}

    def reset(self):
        """重置 AI 状态"""
        if self.agent:
            self.agent.reset()
            logger.info("AI 状态已重置")

    def get_status(self) -> dict:
        """
        获取 AI 状态

        Returns:
            状态字典
        """
        if not self.agent:
            return {
                "initialized": False,
                "step_count": 0,
                "max_steps": 0,
            }

        return {
            "initialized": True,
            "step_count": self.agent.step_count,
            "max_steps": self.agent.agent_config.max_steps,
            "device_id": self.agent.agent_config.device_id,
            "lang": self.agent.agent_config.lang,
        }

    def _confirmation_callback(self, message: str) -> bool:
        """
        敏感操作确认回调

        Args:
            message: 操作描述

        Returns:
            是否确认执行
        """
        # 默认返回 True，实际应用中可以通过 WebSocket 或 HTTP 请求用户确认
        logger.warning(f"敏感操作需要确认: {message}")
        return True

    def _takeover_callback(self, message: str):
        """
        用户接管回调

        Args:
            message: 接管原因
        """
        logger.warning(f"需要用户接管: {message}")
        # 实际应用中可以通过 WebSocket 通知前端

    async def cleanup(self):
        """清理资源"""
        self.agent = None
        self._initialized = False
        logger.info("AI 核心模块已清理")
