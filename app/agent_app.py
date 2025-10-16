import asyncio
import json, os, pprint, time, uuid

from google.genai import types
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

class LocalApp:
    """Agentで推論を実行するためのクラス"""

    def __init__(self, agent):
        """
        LocalAppを初期化します。

        Args:
            agent: 実行するエージェント
        """
        self.agent = agent
        self._runner = Runner(
            app_name=self.agent.name,
            agent=self.agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def create_session(self, user_id: str) -> str:
        """Creates a new session and returns its ID."""
        session = await self._runner.session_service.create_session(
            app_name=self.agent.name,
            user_id=user_id,
            session_id=uuid.uuid4().hex,
        )
        return session.id

    async def stream(self, query: str, session_id: str, user_id: str):
        """
        クエリに対するエージェントの応答をストリーミングします。

        Args:
            query: ユーザーのクエリ
            session_id: セッションID
            user_id: ユーザーID

        Returns:
            イベントの非同期ジェネレータ
        """
        content = types.Content(role="user", parts=[types.Part.from_text(text=query)])
        async_events = self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        )

        return async_events
    
        #async_events は <class 'async_generator'> 
        # result = []
        # async for event in async_events:
        #     if debug:
        #         print(f'----\n{event}\n----')
        #     if (event.content and event.content.parts):
        #         response = '\n'.join([p.text for p in event.content.parts if p.text])
        #         if response:
        #             print(response)
        #             result.append(response)