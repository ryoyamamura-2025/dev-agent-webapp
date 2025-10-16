# main.py
import os
import uuid
import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel

import vertexai

from config import APP_CONFIG
from agent_app import LocalApp
from agent.agent import root_agent

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# app 全体の状態管理用の dict
app_state = {}

# --- FastAPIのライフサイクル管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    アプリケーションの起動・終了時に実行される処理を定義します。
    起動時にVertex AI Agent Engineを初期化し、app_stateに格納します。
    初期化に失敗した場合、アプリケーションは起動しません。
    """
    logger.info("アプリケーションの起動処理を開始します...")
    try:
        # 1. 環境変数の読み込みと検証
        project_id = APP_CONFIG.GOOGLE_CLOUD_PROJECT
        location = APP_CONFIG.GOOGLE_CLOUD_LOCATION
        bucket = APP_CONFIG.GOOGLE_CLOUD_BUCKET

        if not all([project_id, location, bucket]):
            raise ValueError(
                "以下の環境変数が設定されていません: "
                "GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, "
                "GOOGLE_CLOUD_STORAGE_BUCKET"
            )

        # 2. Vertex AI SDKの初期化
        # これはブロッキング処理のため、非同期のイベントループをブロックしないように
        # asyncio.to_threadを使って別スレッドで実行します。
        logger.info(f"Vertex AI SDKを初期化中 (Project: {project_id}, Location: {location})...")
        await asyncio.to_thread(
            vertexai.init,
            project=project_id,
            location=location,
            staging_bucket=f"gs://{bucket}"
        )

        # 3. Agent のインスタンス化
        logger.info(f"Agent を取得中...")
        agent = LocalApp(agent=root_agent)
        
        # 4. 取得したクライアントをアプリケーションの状態として保持
        app_state["local_agent"] = agent
        logger.info("Agentの初期化が正常に完了しました。アプリケーションがリクエストを受け付けます。")

    except Exception as e:
        logger.critical(f"アプリケーションの初期化中に致命的なエラーが発生しました: {e}", exc_info=True)
        # ここで発生した例外はFastAPIによって捕捉され、アプリケーションの起動が中止されます。
        # Cloud Run環境では、コンテナが異常終了したとみなされ、設定に応じて再起動が試みられます。
        raise

    # `yield`でFastAPIアプリケーション本体の処理に制御を移す
    yield
    
    # --- アプリケーション終了時の処理 ---
    # 今回は特にクリーンアップ処理は不要
    logger.info("アプリケーションをシャットダウンします。")

# --- FastAPIアプリケーションのインスタンス化 ---
app = FastAPI(
    title="Agent App",
    lifespan=lifespan # 上で定義したlifespanハンドラを登録
)

# Allow all origins for CORS (useful for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydanticモデル定義（APIのI/Fを定義） ---
class QueryRequest(BaseModel):
    user_id: str
    query: str
    session_id: str | None = None

class QueryResponse(BaseModel):
    response: str
    session_id: str

class HealthResponse(BaseModel):
    status: str

# ====== エンドポイント ======
# 静的ファイル提供
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- APIエンドポイント定義 ---
@app.get("/health", response_model=HealthResponse)
def health_check():
    """
    サービスが正常に起動しているかを確認するヘルスチェックエンドポイント。
    このエンドポイントが200 OKを返す場合、Agentの初期化は成功しています。
    """
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse, tags=["Agent"])
async def query_agent(request: QueryRequest):
    """
    Agent Engineに問い合わせを行い、応答を取得します。
    セッションIDが指定されていない場合は、新しいセッションを自動的に作成します。
    """
    # lifespanで初期化が完了しているため、app_stateから常にagentインスタンスを取得できる
    local_agent = app_state.get("local_agent")
    if not local_agent:
        # 基本的にこのエラーは発生しないはずだが、念のためハンドリング
        raise HTTPException(status_code=503, detail="サービスが利用できません。")

    current_session_id = request.session_id
    user_id = request.user_id

    try:
        # セッションIDがない場合は新しいセッションを作成
        if not current_session_id:
            logger.info(f"新規セッションを作成します (user_id: {user_id})")
            current_session_id = await local_agent.create_session(user_id=user_id)
            logger.info(f"新規セッション作成完了: {current_session_id}")

        # Agentに問い合わせをストリーミング
        logger.info(f"Agentに問い合わせ中 (session_id: {current_session_id})")
        response_stream = await local_agent.stream(
            query=request.query,
            session_id=current_session_id,
            user_id=user_id
        )

        # ストリームから応答を連結して完全なレスポンスを作成
        response_parts = [_parse_agent_event(event) async for event in response_stream]
        full_response = "".join(response_parts)

        logger.info(f"Agentからの最終応答長: {len(full_response)}")
        if not full_response:
            logger.warning("Agentからの応答が空でした。")
            full_response = "すみません、応答を生成できませんでした。"
        logger.info(f"Agentからの最終応答: {full_response}")

        return QueryResponse(response=full_response, session_id=current_session_id)

    except Exception as e:
        logger.error(f"Agentへの問い合わせ中にエラーが発生しました: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"内部サーバーエラー: {str(e)}")

def _parse_agent_event(event: dict | object) -> str:
    """Agentからのイベントをパースして、テキスト部分を抽出するヘルパー関数。"""
    if (event.content and event.content.parts):
        response = '\n'.join([p.text for p in event.content.parts if p.text])
        if response:
            return response
    else:
        logger.warning("Agent からのメッセージが空でした")
        return "Agent からのメッセージが空でした"
    
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse('static/index.html')

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)