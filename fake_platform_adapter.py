import asyncio
import json
import random
import uuid
from string import Template

from .fake_platform_constants import (
    DEFAULT_ADAPTER_CONFIG,
    DEFAULT_PROMPT_TEMPLATE,
    FAKE_ADAPTER_CONFIG_METADATA,
    MIN_FREQUENCY_PER_MINUTE,
    POOL_DEFAULT_BATCH_SIZE,
    POOL_REFILL_RATIO,
)

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


@register_platform_adapter(
    "fake_adapter",
    "FakeAdapter — 用於插件開發測試的虛擬平台適配器",
    default_config_tmpl=DEFAULT_ADAPTER_CONFIG,
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

        batch_size = int(
            umo.get(
                "batch_size", self.config.get("batch_size", POOL_DEFAULT_BATCH_SIZE)
            )
        )
        batch_size = max(1, min(100, batch_size))

        refill_ratio = float(
            umo.get("refill_ratio", self.config.get("refill_ratio", POOL_REFILL_RATIO))
        )
        refill_ratio = max(0.1, min(1.0, refill_ratio))

        message_pool: list[str] = []
        refill_threshold = max(1, int(batch_size * refill_ratio))

        while True:
            try:
                if not message_pool:
                    message_pool = await self._generate_content_batch(
                        len(users), batch_size
                    )

                content = (
                    message_pool.pop(0) if message_pool else self._placeholder_message()
                )

                await self._emit_fake_message(
                    umo_id, users, debug_prefix, content=content
                )

                if len(message_pool) <= refill_threshold:
                    more = await self._generate_content_batch(len(users), batch_size)
                    if more:
                        message_pool.extend(more)

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"FakeAdapter: UMO '{umo_id}' 發送消息時出錯: {exc}")

    # ------------------------------------------------------------------
    # Message construction & emission
    # ------------------------------------------------------------------

    async def _emit_fake_message(
        self,
        umo_id: str,
        users: list[dict],
        debug_prefix: bool,
        content: str | None = None,
    ) -> None:
        user_data = random.choice(users)
        user_id: str = user_data.get("id", str(uuid.uuid4()))
        nickname: str = user_data.get("nickname", user_id)

        if content is None:
            content = await self._generate_content(len(users))

        if debug_prefix:
            content = f"[來自 {umo_id}] {content}"

        abm = AstrBotMessage()
        abm.type = MessageType.GROUP_MESSAGE
        # fake adapter 不支援真正“發言帳號”，將 self_id 設為固定適配器標識
        abm.self_id = self.meta().id
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
        results = await self._generate_content_batch(user_count, 1)
        return results[0] if results else self._placeholder_message()

    async def _generate_content_batch(
        self, user_count: int, batch_size: int
    ) -> list[str]:
        prompt_tmpl_str: str = self.config.get(
            "prompt_template", DEFAULT_PROMPT_TEMPLATE
        )
        try:
            prompt = Template(prompt_tmpl_str).safe_substitute(
                user_count=user_count,
                batch_size=batch_size,
            )
        except Exception as exc:
            logger.warning(f"FakeAdapter: Prompt 模板解析失敗，使用預設模板: {exc}")
            prompt = Template(DEFAULT_PROMPT_TEMPLATE).safe_substitute(
                user_count=user_count,
                batch_size=batch_size,
            )

        if _astrbot_context is None:
            logger.warning("FakeAdapter: 插件上下文未初始化，使用佔位消息。")
            return [self._placeholder_message() for _ in range(batch_size)]

        model_id = str(self.config.get("model", "") or "").strip()
        provider = None

        if model_id:
            provider = _astrbot_context.get_provider_by_id(model_id)
        if provider is None:
            provider = _astrbot_context.get_using_provider()

        if provider is None:
            logger.warning("FakeAdapter: 沒有可用的 LLM 提供者，使用佔位消息。")
            return [self._placeholder_message() for _ in range(batch_size)]

        try:
            response = await _astrbot_context.llm_generate(
                chat_provider_id=provider.meta().id,
                prompt=prompt,
            )

            raw_text = (response.completion_text or "").strip()
            if not raw_text:
                return [self._placeholder_message() for _ in range(batch_size)]

            candidates = []
            try:
                parsed = json.loads(raw_text)
                if isinstance(parsed, list):
                    candidates = [
                        str(item).strip()
                        for item in parsed
                        if isinstance(item, str) and item.strip()
                    ]
            except json.JSONDecodeError:
                candidates = []

            if not candidates:
                candidates = [
                    line.strip() for line in raw_text.splitlines() if line.strip()
                ]

            if not candidates:
                return [self._placeholder_message() for _ in range(batch_size)]

            if len(candidates) < batch_size:
                logger.info(
                    f"FakeAdapter: LLM 返回 {len(candidates)} 條，少於要求 {batch_size} 條，將補充佔位消息。"
                )
                candidates.extend(
                    [self._placeholder_message() for _ in range(batch_size - len(candidates))]
                )

            return candidates[:batch_size]

        except Exception as exc:
            logger.error(f"FakeAdapter: LLM 生成消息失敗: {exc}")
            return [self._placeholder_message() for _ in range(batch_size)]
