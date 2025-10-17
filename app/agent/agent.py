from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool
from .prompts import FACILITATOR_INSTRUCTIONS

# Agent as a tool で利用されるエージェント
idea_agent = LlmAgent(
    name="IdeaAgent", 
    description="創造的にアイデア出しをする",
    model='gemini-2.5-flash',
    instruction="与えられたトピックに関して誰もがあっと驚くアイデアを1つ出してください。",
)

critic_agent = LlmAgent(
    name="CriticAgent", 
    description="アイデアを評価し批評します。",
    model='gemini-2.5-flash',
    instruction="アイデアに対して建設的な批評を行い改善点を簡潔に提示します。",
)

# 利用可能なツール
available_tools = {
    "IdeaAgent": idea_agent,
    "CriticAgent": critic_agent,
}

# デフォルトのファシリ Agent
facilitator_agent_default = LlmAgent(
    name="Facilitator",
    model="gemini-2.5-flash",
    instruction=FACILITATOR_INSTRUCTIONS,
    tools=[agent_tool.AgentTool(agent=idea_agent), agent_tool.AgentTool(agent=critic_agent)]
    # Alternatively, could use LLM Transfer if research_assistant is a sub_agent
)

root_agent = facilitator_agent_default

# ファクトリ関数
# TODO: 動的にファシリのインストラクションを変更
def create_facilitator_agent(selected_tool_names: list[str]) -> LlmAgent:
    """
    選択されたツールのリストに基づいて、ファシリテーターエージェントを動的に生成します。
    """
    selected_tools = [
        agent_tool.AgentTool(agent=available_tools[name])
        for name in selected_tool_names
        if name in available_tools
    ]
    
    facilitator_agent = LlmAgent(
        name="Facilitator",
        model="gemini-2.5-flash",
        description="会議の議論をリードするファシリテータAgentです。",
        instruction=FACILITATOR_INSTRUCTIONS,
        tools=selected_tools
    )
    return facilitator_agent