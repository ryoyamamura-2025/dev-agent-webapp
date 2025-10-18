# main.py
import os
import uuid
import asyncio
import logging
import time
import pprint
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
from agent.agent import available_tools, create_facilitator_agent

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

        # 3. アクティブなセッションとエージェントインスタンスを保持する辞書を初期化
        app_state["local_app_cache"] = {} # ツール構成が同じ場合はAgentのインスタンスをキャッシュする
        app_state["session_to_cache_key"] = {} # session_idからツール構成のキーを引くためのマッピング
        logger.info("共有セッションストアを初期化しました。アプリケーションがリクエストを受け付けます。")

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
class ToolInfo(BaseModel):
    name: str
    description: str

class ToolsListResponse(BaseModel):
    tools: list[ToolInfo]

class CreateSessionRequest(BaseModel):
    user_id: str
    tool_names: list[str]

class CreateSessionResponse(BaseModel):
    session_id: str

class QueryRequest(BaseModel):
    user_id: str
    query: str
    session_id: str

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

@app.get("/tools", response_model=ToolsListResponse, tags=["Agent"])
def list_tools():
    """UIが選択肢を表示するために、利用可能なツールの一覧を返します。"""
    tool_list = [
        ToolInfo(name=name, description=tool.description)
        for name, tool in available_tools.items()
    ]
    return ToolsListResponse(tools=tool_list)


@app.post("/sessions/create", response_model=CreateSessionResponse, tags=["Agent"])
async def create_session(request: CreateSessionRequest):
    """
    選択されたツールでエージェントを初期化（またはキャッシュから取得）し、新しいセッションを開始します。
    """
    logger.info(f"新規セッション作成リクエスト (user: {request.user_id}, tools: {request.tool_names})")
    try:
        # ツールリストから一意なキャッシュキーを生成（順序を固定するためソート）
        cache_key = ",".join(sorted(request.tool_names))

        # キャッシュにエージェント（LocalApp）インスタンスがあるか確認
        local_app = app_state["local_app_cache"].get(cache_key)

        if not local_app:
            logger.info(f"キャッシュにインスタンスがないため新規作成します (key: {cache_key})")
    
            agent = create_facilitator_agent(request.tool_names)
            local_app = LocalApp(agent=agent)
            # 作成したインスタンスをキャッシュに保存
            app_state["local_app_cache"][cache_key] = local_app
        else:
            logger.info(f"キャッシュからインスタンスを再利用します (key: {cache_key})")

        # 取得または作成したLocalAppインスタンスでADKセッションを作成
        session_id = await local_app.create_session(user_id=request.user_id)
        
        # 新しいsession_idとキャッシュキーを紐づけて保存
        app_state["session_to_cache_key"][session_id] = cache_key
        
        logger.info(f"新規セッション作成完了: {session_id}")
        return CreateSessionResponse(session_id=session_id)
        
    except Exception as e:
        logger.error(f"セッション作成中にエラーが発生しました: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="セッションの作成に失敗しました。")


@app.post("/query", response_model=QueryResponse, tags=["Agent"])
async def query_agent(request: QueryRequest):
    """
    Agent Engineに問い合わせを行い、応答を取得します。
    """
    # session_idから、どのツール構成（キャッシュキー）が使われたかを取得
    cache_key = app_state["session_to_cache_key"].get(request.session_id)
    if not cache_key:
        raise HTTPException(status_code=404, detail=f"セッション設定が見つかりません: {request.session_id}")

    # Agent の初期化
    local_app = app_state["local_app_cache"].get(cache_key)
    if not local_app:
        raise HTTPException(status_code=500, detail=f"内部エラー: セッションに対応するエージェントが見つかりません")
    
    current_session_id = request.session_id
    user_id = request.user_id
    logger.info(f"クエリ受信 (session_id: {request.session_id}, cache_key: {cache_key})")

    # Agentに問い合わせをストリーミング
    try:
        logger.info(f"Agentに問い合わせ中 (session_id: {current_session_id})")
        response_stream = await local_app.stream(
            query=request.query,
            session_id=current_session_id,
            user_id=user_id
        )

        # ストリームから応答を連結して完全なレスポンスを作成
        response_parts = []
        async for event in response_stream:
            response_parts.append(_parse_agent_event(event))

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
        parts_text = []
        for part in event.content.parts:
            if part.text:
                # partにtext属性があれば、それを追加
                parts_text.append(part.text)
            elif part.function_response:
                # partにfunction_response属性があれば、その中の 'result' を文字列として追加
                if (hasattr(part.function_response, 'response') and
                    isinstance(part.function_response.response, dict) and
                    'result' in part.function_response.response):                 
                    function_name = part.function_response.name
                    result_data = part.function_response.response['result']
                    if isinstance(result_data, str):
                        parts_text.append(f"{function_name}: {result_data}")
        return "\n".join(parts_text)
    else:
        logger.warning("Agent からのメッセージが空でした")
        return "Agent からのメッセージが空でした"
    
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse('static/index.html')

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)