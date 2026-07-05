# tools/plan_tot.py
"""ToT 规划工具 - 调 Planner 生成任务列表。"""
import json
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from core.planner import Planner
from core.llm import create_llm
from config.config import load_config


class PlanToTInput(BaseModel):
    task: str = Field(description="Complex task to plan")


@tool(args_schema=PlanToTInput)
def plan_tot(task: str) -> str:
    """Use Tree of Thoughts to plan a complex task into subtasks."""
    try:
        config = load_config()
        llm = create_llm(config)
        planner = Planner(llm, tot_candidates=config.get("cognitive", {}).get("tot_candidates", 3))
        tasks = planner.invoke(task)
        return json.dumps(tasks, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"
