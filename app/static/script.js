// --- 定数 ---
// API エンドポイント
const getToolListEndpoint = "/tools"
const createSessionEndpoint = "/sessions/create"
const queryEndpoint = "/query"

// DOM
const createSessionBtn = document.getElementById("create-session-btn")
const sendMessageBtn = document.getElementById("send-message-btn")
const chatContentTmp = document.getElementById("chat-content-tmp")

// 共通
let currentSessinId = null;
let userId = 'default_user'

// ---- API Call ----
async function callGetToolList() {
    try {
        const response = await fetch(getToolListEndpoint);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const result = await response.json();
        return result;
    } catch (e) {
        console.error(e.message);
    }
}

async function callCreateSession(selectedTools) {
    try {
        const response = await fetch(createSessionEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                tool_names: selectedTools
            })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const result = await response.json();
        return result;
    } catch (e) {
        console.error(e.message);
    }
}

async function callQuery(query) {
    try {
        const response = await fetch(queryEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                query: query,
                session_id: currentSessinId
            })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const result = await response.json();
        return result;
    } catch (e) {
        console.error(e.message);
    }
}

// --- Helper ---
// 画面ロード時にAgentのツール一覧を取得しチェックボックスで表示する
async function initCheckbox() {
    const container = document.getElementById('tool-container');

    toolList = await callGetToolList();

    // tools 配列をループ処理
    toolList.tools.forEach(tool => {
        // ツールごとを囲む 'div' を作成
        const toolWrapper = document.createElement('div');
        toolWrapper.className = 'tool-item'; 

        // チェックボックスを作成
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = tool.name; // (ラベルと紐づけるためにIDをつけます)
        checkbox.value = tool.name;

        // ラベル (tool.name) を作成
        const label = document.createElement('label');
        label.htmlFor = tool.name; // (チェックボックスのIDと紐づけます)
        label.textContent = tool.name;

        // 説明文 (tool.description) を作成
        const description = document.createElement('p'); // <p>タグで説明文
        description.textContent = tool.description;
        description.className = 'tool-description';

        // 作成した要素をコンテナに追加
        toolWrapper.appendChild(checkbox);
        toolWrapper.appendChild(label);
        toolWrapper.appendChild(description);
        
        // 最後に、全部をまとめた 'toolWrapper' を親コンテナに追加
        container.appendChild(toolWrapper);
    });
}

// 選択されたツールを取得
async function getSelectedTools() {
    const checkBoxes = document.querySelectorAll('#tool-container input[type="checkbox"]:checked');
    const selectedTools = [];
    checkBoxes.forEach(checkbox => {
        selectedTools.push(checkbox.value);
    })
    console.log(selectedTools);
    return selectedTools;
}

// セッションを開始
async function createSession() {
    const selectedTools = await getSelectedTools();
    if (selectedTools.length == 0) {
        alert('ツールが選択されていません')
    } else {
        const newSessinId = await callCreateSession(selectedTools);
        currentSessinId = newSessinId.session_id;
    }
}

// クエリを送信し結果を得る
async function sendQuery() {
    if (currentSessinId == null) {
        alert('セッションが開始されていません。ツールを選択しセッションを開始してください')
    }
    else {
        const query = document.getElementById("query-input").value;
        // queryが空文字列 "" だった場合にアラートを表示
        if (query === "") {
            alert("何も入力されていません。");
        } else {
            console.log(`現在のセッション: ${currentSessinId}`);
            console.log(`入力されたクエリ: ${query}`);
            result = await callQuery(query);
            document.getElementById('chat-content-tmp').textContent = result.response;
        }
    }
}

// ---- UI ----
// 読み込み時
document.addEventListener("DOMContentLoaded", async () => {
    // チェックボックスの読み込み
    await initCheckbox();
    // セッション開始ボタンの初期化
    createSessionBtn.addEventListener("click", async () => {
        await createSession();
    });
    sendMessageBtn.addEventListener("click", async () => {
        await sendQuery();
    });
})