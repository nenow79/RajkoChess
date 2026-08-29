from sqlalchemy.ext.asyncio import AsyncSession

from chess_logic.bot_game import configured_bot_elo_offset
from db.models import RuntimeSetting

BOT_GLOBAL_ELO_OFFSET_KEY = "bot_global_elo_offset"


async def get_bot_global_elo_offset(db: AsyncSession) -> tuple[int, str]:
    setting = await db.get(RuntimeSetting, BOT_GLOBAL_ELO_OFFSET_KEY)
    if setting is not None:
        value = setting.value.get("offset")
        if isinstance(value, int) and not isinstance(value, bool):
            return min(300, max(-600, value)), "database"
    return configured_bot_elo_offset(), "environment"
