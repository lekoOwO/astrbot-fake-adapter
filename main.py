from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from . import fake_platform_adapter as _fpa


@register(
    "astrbot_plugin_fake_adapter",
    "lekoOwO",
    "用於插件開發測試的虛擬平台適配器，可產生虛擬聊天消息",
    "1.0.0",
)
class FakeAdapterPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # Share the AstrBot context with the platform adapter module so it
        # can call the LLM for generating virtual messages.
        _fpa._astrbot_context = context
        # Importing the class here (via the module import above) already
        # triggered the @register_platform_adapter decorator, so the adapter
        # is now registered with AstrBot.
        from .fake_platform_adapter import FakePlatformAdapter  # noqa: F401

        logger.info("FakeAdapter: 虛擬平台適配器已載入。")

    async def terminate(self):
        """清理：移除對 AstrBot 上下文的引用。"""
        _fpa._astrbot_context = None
