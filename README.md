# Study Serverless WebApp

## 1. アプリケーション概要

本アプリケーションは、バックエンドで時間のかかる非同期処理を実行するウェブアプリケーションのモックです。
Google Cloudのサーバーレスサービスである **Cloud Run**, **Cloud Tasks**, **Firestore** を利用して、スケーラブルな構成を学習するために作成しました。

### アーキテクチャ概要

```mermaid
graph TD
    subgraph "User"
        Client[Browser]
    end

    subgraph "Google Cloud"
        subgraph "Cloud Run Service"
            CR_API[FastAPI App<br>/start-task<br>/progress]
            CR_Worker[FastAPI App<br>/run-task]
        end

        CloudTasks[Cloud Tasks]
        Firestore[Firestore Database]
    end

    Client -- "1. POST /start-task" --> CR_API
    CR_API -- "2. Create Task Document" --> Firestore
    CR_API -- "3. Create Task" --> CloudTasks
    Client -- "4. GET /progress/{task_id} (SSE)" --> CR_API
    CloudTasks -- "5. POST /run-task" --> CR_Worker
    CR_Worker -- "6. Update Task Status & Progress" --> Firestore
    CR_API -- "7. Read Task Status" --> Firestore
    CR_API -- "8. Stream Progress Update" --> Client
```

### 主な特徴

- **非同期タスク処理**: 時間のかかる処理（動画分析やデータ処理などを想定）をCloud Tasksにキューイングし、Cloud Runの別インスタンスで非同期に実行します。
- **リアルタイム進捗更新**: Server-Sent Events (SSE) を利用して、クライアント（ブラウザ）に処理の進捗をリアルタイムで通知します。
- **スケーラブルなアーキテクチャ**: 各コンポーネントが独立しており、負荷に応じてスケールしやすい構成になっています。
- **使用技術**:
    - バックエンド: Python, FastAPI
    - クラウド: Google Cloud Run, Cloud Tasks, Firestore
    - フロントエンド: HTML, JavaScript

## 2. 環境構築 (ローカル)

### 前提条件

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`コマンド) がインストールおよび初期化済みであること。
- [Python 3.12](https://www.python.org/) 以降がインストール済みであること。
- [uv](https://github.com/astral-sh/uv) がインストール済みであること。

### 手順

1.  **リポジトリをクローン**
    ```bash
    git clone <repository-url>
    cd study-serverless-webapp
    ```

2.  **Python仮想環境の作成と依存パッケージのインストール**
    `uv` を使って仮想環境を作成し、`pyproject.toml`, `uv.lock` から依存関係をインストールします。
    ```bash
    uv venv
    uv sync
    ```

3.  **環境変数ファイルの設定**
    プロジェクトルートに `.env.dev` ファイルを作成します。
    ```ini
    GCP_PROJECT_ID=your-gcp-project-id
    LOCATION=your-cloud-tasks-region #例: asia-northeast1
    GCP_TASK_QUEUE_ID=your-cloud-tasks-queue-id
    GCP_FIRESTORE_DB_NAME=your-firestore-db-name
    BASE_URL=your-cloud-run-service-url #デプロイ後に設定
    ```

4.  **Dockerイメージのビルドとコンテナの起動**
    `rebuild_or_restart.sh` スクリプトを使用します。このスクリプトは、開発用のDockerイメージをビルドし、コンテナを起動します。
    ```bash
    # スクリプトに実行権限を付与
    chmod +x rebuild_or_restart.sh

    # イメージをビルドしてコンテナを起動
    bash rebuild_or_restart.sh build
    ```
    コンテナが起動すると、`http://localhost:3232` でアプリケーションにアクセスできます。  
    docker コンテナにて以下のコマンドでFastAPIサーバーが起動されます。
    ```bash
    uv run python main.py
    ```

## 4. デプロイ方法

`deploy.sh.dev` スクリプトを使用して、アプリケーションをCloud Runにデプロイします。

### 前提条件

- `.env.yaml.dev` ファイルが作成済みであること。
    ```yaml
    GCP_PROJECT_ID: "your-gcp-project-id"
    LOCATION: "your-cloud-tasks-region"
    GCP_TASK_QUEUE_ID: "your-cloud-tasks-queue-id"
    GCP_FIRESTORE_DB_NAME: "your-firestore-db-name"
    BASE_URL: "your-cloud-run-service-url" # デプロイ後に設定
    ```

### 手順

1.  **gcloud CLIでの認証**
    ```bash
    gcloud auth login
    gcloud config set project your-gcp-project-id
    ```

2.  **デプロイスクリプトの編集**
    `deploy.sh.dev` ファイル内の以下の変数を、ご自身の環境に合わせて編集します。
    ```bash
    PROJECT_ID="your-gcp-project-id"
    REGION="your-cloud-run-region" # 例: asia-northeast1
    SERVICE_NAME="study-serverless-webapp"
    ```

3.  **スクリプトの実行権限を付与**
    ```bash
    chmod +x deploy.sh.dev
    ```

4.  **デプロイの実行**
    ```bash
    bash deploy.sh.dev
    ```
    このコマンドは、現在のディレクトリのソースコードを元にコンテナイメージをビルドし、Cloud Runにデプロイします。
    デプロイが完了すると、サービスのURLが出力されます。そのURLを `.env.yaml.dev` の `BASE_URL` に設定し、再度デプロイしてください。