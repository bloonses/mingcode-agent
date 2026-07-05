"""向用户提问工具。"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class AskUserInput(BaseModel):
    question: str = Field(description="Question to ask the user")


@tool(args_schema=AskUserInput)
def ask_user(question: str) -> str:
    """Ask the user a question and wait for their answer."""
    print(f"\n[AI 问题] {question}")
    try:
        answer = input("> ")
        return answer
    except (EOFError, KeyboardInterrupt):
        return "(用户取消了回答)"
