"""时间日期工具。"""
from datetime import datetime, timezone
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class TimeNowInput(BaseModel):
    timezone_offset: int = Field(default=8, description="Timezone offset from UTC (default: 8 for Asia/Shanghai)")


@tool(args_schema=TimeNowInput)
def time_now(timezone_offset: int = 8) -> str:
    """Get current time in ISO format with timezone offset."""
    from datetime import timedelta
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)
    return now.isoformat()
