from astrbot.api.event import MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot import logger


class FakePlatformEvent(AstrMessageEvent):
    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
    ):
        super().__init__(message_str, message_obj, platform_meta, session_id)

    async def send(self, message: MessageChain):
        text = message.get_plain_text(with_other_comps_mark=True)
        logger.info(f"[FakeAdapter] 回覆 -> {self.get_session_id()}: {text}")
        await super().send(message)
