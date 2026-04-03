import asyncio
import random
import uuid
from string import Template

from astrbot.api.platform import (
    AstrBotMessage,
    Group,
    MessageMember,
    MessageType,
    Platform,
    PlatformMetadata,
    register_platform_adapter,
)
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain
from astrbot.core.platform.astr_message_event import MessageSession
from astrbot import logger

from .fake_platform_event import FakePlatformEvent

# Shared reference to AstrBot's Context, set by the main plugin on startup.
_astrbot_context = None

DEFAULT_PROMPT_TEMPLATE = (
    "你正在一個有 $user_count 人的群聊中，請以群聊成員的身份發送一條自然的聊天消息。"
    "要求：1. 消息應當簡短自然，不超過 50 字；"
    "2. 不要使用自我介紹；"
    "3. 直接輸出消息內容，不要添加任何前綴或說明。"
)
MIN_FREQUENCY_PER_MINUTE = 1.0 / 60.0

FAKE_ADAPTER_CONFIG_METADATA = {
    "bot_name": {
        "description": "虛擬機器人名稱",
        "type": "string",
        "hint": "作為 fake adapter 的 bot self_id。",
    },
    "umos": {
        "description": "虛擬聊天群組",
        "type": "template_list",
        "hint": "可新增多個 UMO；每個 UMO 可配置獨立用戶與發言頻率。",
        "templates": {
            "group": {
                "name": "群聊 UMO",
                "hint": "一個可持續產生虛擬消息的群聊單位。",
                "items": {
                    "id": {
                        "description": "UMO ID",
                        "type": "string",
                        "hint": "例如 fake_group_1。",
                    },
                    "users": {
                        "description": "虛擬用戶 ID 列表",
                        "type": "list",
                        "hint": "例如 user_1、user_2。每個 ID 對應一個虛擬發言者。",
                    },
                    "frequency": {
                        "description": "發言頻率（條/分鐘）",
                        "type": "float",
                        "hint": "最小為 1/60（每小時 1 條）。",
                        "slider": {"min": MIN_FREQUENCY_PER_MINUTE, "max": 60, "step": 0.1},
                    },
                    "debug_prefix": {
                        "description": "啟用 Debug 前綴",
                        "type": "bool",
                        "hint": "啟用後消息會附加 [來自 {umo_id}] 前綴。",
                    },
                },
            }
        },
    },
    "model": {
        "description": "LLM 模型提供者",
        "type": "string",
        "_special": "select_provider",
        "hint": "留空時使用 AstrBot 當前預設提供者。",
    },
    "prompt_template": {
        "description": "消息生成 Prompt 模板",
        "type": "text",
        "hint": "支持 $user_count 變數。",
    },
}


@register_platform_adapter(
    "fake_adapter",
    "FakeAdapter — 用於插件開發測試的虛擬平台適配器",
    default_config_tmpl={
        "bot_name": "FakeBot",
        "umos": [
            {
                "__template_key": "group",
                "id": "fake_group_1",
                "users": ["user_1", "user_2"],
                "frequency": 10,
                "debug_prefix": True,
            }
        ],
        "model": "",
        "prompt_template": DEFAULT_PROMPT_TEMPLATE,
    },
    config_metadata=FAKE_ADAPTER_CONFIG_METADATA,
)
class FakePlatformAdapter(Platform):
    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: asyncio.Queue,
    ) -> None:
        super().__init__(platform_config, event_queue)
        self.settings = platform_settings
        self._umo_tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # Required Platform interface
    # ------------------------------------------------------------------

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="fake_adapter",
            description="FakeAdapter — 用於插件開發測試的虛擬平台適配器",
            id=self.config.get("id", "fake_adapter"),
            adapter_display_name="FakeAdapter",
        )

    async def send_by_session(
        self, session: MessageSession, message_chain: MessageChain
    ) -> None:
        await super().send_by_session(session, message_chain)

    async def run(self) -> None:
        umos: list[dict] = self.config.get("umos", [])
        if not umos:
            logger.warning("FakeAdapter: 未配置任何 UMO，適配器將空閒運行。")

        for umo in umos:
            task = asyncio.create_task(self._umo_loop(umo))
            self._umo_tasks.append(task)

        try:
            await asyncio.gather(*self._umo_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    async def terminate(self) -> None:
        for task in self._umo_tasks:
            task.cancel()
        self._umo_tasks.clear()
        await super().terminate()

    # ------------------------------------------------------------------
    # UMO message loop
    # ------------------------------------------------------------------

    @staticmethod
    def _placeholder_message() -> str:
        return f"（虛擬消息 #{random.randint(1000, 9999)}）"

    @staticmethod
    def _normalize_users(users: list) -> list[dict]:
        normalized: list[dict] = []
        for user in users:
            if isinstance(user, dict):
                user_id = str(user.get("id", "")).strip()
                if not user_id:
                    continue
                nickname = str(user.get("nickname", "")).strip()
                nickname = nickname if nickname else user_id
                normalized.append({"id": user_id, "nickname": nickname})
                continue

            user_id = str(user).strip()
            if not user_id:
                continue
            normalized.append({"id": user_id, "nickname": user_id})

        return normalized

    async def _umo_loop(self, umo: dict) -> None:
        umo_id: str = umo.get("id", str(uuid.uuid4()))
        users: list[dict] = self._normalize_users(umo.get("users", []))
        frequency: float = float(umo.get("frequency", 10))
        debug_prefix: bool = bool(umo.get("debug_prefix", True))

        if not users:
            logger.warning(f"FakeAdapter: UMO '{umo_id}' 沒有配置任何用戶，跳過。")
            return

        # Clamp frequency to a sensible minimum (1 message per hour).
        frequency = max(frequency, MIN_FREQUENCY_PER_MINUTE)
        interval = 60.0 / frequency
        logger.info(
            f"FakeAdapter: UMO '{umo_id}' 啟動，"
            f"{len(users)} 個虛擬用戶，"
            f"發言頻率 {frequency} 條/分鐘（間隔 {interval:.1f} 秒）"
        )

        while True:
            await asyncio.sleep(interval)
            try:
                await self._emit_fake_message(umo_id, users, debug_prefix)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"FakeAdapter: UMO '{umo_id}' 發送消息時出錯: {exc}")

    # ------------------------------------------------------------------
    # Message construction & emission
    # ------------------------------------------------------------------

    async def _emit_fake_message(
        self, umo_id: str, users: list[dict], debug_prefix: bool
    ) -> None:
        user_data = random.choice(users)
        user_id: str = user_data.get("id", str(uuid.uuid4()))
        nickname: str = user_data.get("nickname", user_id)

        content = await self._generate_content(len(users))

        if debug_prefix:
            content = f"[來自 {umo_id}] {content}"

        abm = AstrBotMessage()
        abm.type = MessageType.GROUP_MESSAGE
        abm.self_id = self.config.get("bot_name", "FakeBot")
        abm.session_id = umo_id
        abm.message_id = str(uuid.uuid4())
        abm.sender = MessageMember(user_id=user_id, nickname=nickname)
        abm.group = Group(group_id=umo_id, group_name=umo_id)
        abm.message = [Plain(text=content)]
        abm.message_str = content
        abm.raw_message = {
            "umo_id": umo_id,
            "user_id": user_id,
            "nickname": nickname,
            "content": content,
        }

        event = FakePlatformEvent(
            message_str=content,
            message_obj=abm,
            platform_meta=self.meta(),
            session_id=umo_id,
        )
        self.commit_event(event)

    # ------------------------------------------------------------------
    # LLM message generation
    # ------------------------------------------------------------------

    async def _generate_content(self, user_count: int) -> str:
        prompt_tmpl_str: str = self.config.get(
            "prompt_template", DEFAULT_PROMPT_TEMPLATE
        )
        try:
            prompt = Template(prompt_tmpl_str).safe_substitute(user_count=user_count)
        except Exception as exc:
            logger.warning(f"FakeAdapter: Prompt 模板解析失敗，使用預設模板: {exc}")
            prompt = Template(DEFAULT_PROMPT_TEMPLATE).safe_substitute(
                user_count=user_count
            )

        if _astrbot_context is None:
            logger.warning("FakeAdapter: 插件上下文未初始化，使用佔位消息。")
            return self._placeholder_message()

        try:
            model_id: str = self.config.get("model") or ""
            provider = None

            if model_id:
                provider = _astrbot_context.get_provider_by_id(model_id)
            if provider is None:
                provider = _astrbot_context.get_using_provider()

            if provider is None:
                logger.warning("FakeAdapter: 沒有可用的 LLM 提供者，使用佔位消息。")
                return self._placeholder_message()

            provider_id: str = provider.meta().id
            response = await _astrbot_context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )
            text = (response.completion_text or "").strip()
            return text if text else self._placeholder_message()

        except Exception as exc:
            logger.error(f"FakeAdapter: LLM 生成消息失敗: {exc}")
            return self._placeholder_message()
