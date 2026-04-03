DEFAULT_PROMPT_TEMPLATE = (
    "你正在一個有 $user_count 人的群聊中，請以群聊成員身份生成 $batch_size 條自然聊天消息。\n"
    '請直接輸出合法 JSON 列表，例如 ["消息1", "消息2", ...]，不要額外說明。\n'
    "每條消息不超過 50 字，保持簡短自然。"
)
MIN_FREQUENCY_PER_MINUTE = 1.0 / 60.0
POOL_DEFAULT_BATCH_SIZE = 20
POOL_REFILL_RATIO = 0.3

FAKE_ADAPTER_CONFIG_METADATA = {
    "umos": {
        "description": "虛擬聊天群組",
        "type": "template_list",
        "hint": "可新增多個群組；每個群組可配置獨立成員與發言頻率。",
        "templates": {
            "group": {
                "name": "群聊 UMO",
                "hint": "一個可持續產生虛擬消息的群組單位。",
                "items": {
                    "id": {
                        "description": "群組 ID",
                        "type": "string",
                        "hint": "例如 fake_group_1。",
                    },
                    "users": {
                        "description": "虛擬用戶 ID 列表",
                        "type": "list",
                        "hint": "例如 user_1、user_2。每個 ID 對應一個群聊成員。",
                    },
                    "frequency": {
                        "description": "發言頻率（條/分鐘）",
                        "type": "float",
                        "hint": "最小為 1/60（每小時 1 條）。",
                        "slider": {
                            "min": MIN_FREQUENCY_PER_MINUTE,
                            "max": 60,
                            "step": 0.1,
                        },
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
    "batch_size": {
        "description": "每次從 LLM 批量生成的消息數量",
        "type": "integer",
        "hint": "建議 5-50 之間，值越大請求壓力越大。",
        "minimum": 1,
        "maximum": 100,
    },
    "refill_ratio": {
        "description": "消息池補充比例",
        "type": "float",
        "hint": "當剩餘消息 <= batch_size * refill_ratio 時補充。",
        "minimum": 0.1,
        "maximum": 1.0,
        "step": 0.05,
    },
    "prompt_template": {
        "description": "消息生成 Prompt 模板",
        "type": "text",
        "editor_mode": True,
        "editor_language": "markdown",
        "hint": '支持 $user_count 和 $batch_size 變數，建議是要求 JSON 列表形式，如 ["msg1", "msg2"].',
    },
}

DEFAULT_ADAPTER_CONFIG = {
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
    "batch_size": POOL_DEFAULT_BATCH_SIZE,
    "refill_ratio": POOL_REFILL_RATIO,
    "prompt_template": DEFAULT_PROMPT_TEMPLATE,
}


def merge_adapter_config(
    base_config: dict | None, override_config: dict | None
) -> dict:
    """將 override 應用到 base，返回新的字典。"""
    config = dict(DEFAULT_ADAPTER_CONFIG if base_config is None else base_config)
    if override_config:
        config.update(override_config)
    return config
