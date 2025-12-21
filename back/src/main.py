import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import random

# Socket.ioサーバーの設定
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()
app_sio = socketio.ASGIApp(sio, app)

# CORS設定（ブラウザからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

# --- 制御用イベント ---

@sio.on("request_scan")
async def handle_scan(sid):
    """
    フロントエンドのボタンや、NAOのトリガーから呼ばれる
    """
    print("計測リクエストを受信。スキャンを開始します。")
    
    # 1. フロントエンドにシャッフル開始を命じる
    await sio.emit("change_phase", "SHUFFLE")
    
    # 2. ここで本来はLLM推論などを行う（演出用に3秒待機）
    await asyncio.sleep(3)
    
    # 3. 診断結果（目標値）を決定
    # 本来はここでAIの回答から数値を算出
    target_val = "{:.6f}".format(random.uniform(0.0, 1.048596))
    if random.random() > 0.8: target_val = "1.048596" # 20%でSG世界線
    
    print(f"計測完了。目標値: {target_val}")
    
    # 4. フロントエンドに数値確定（SETTLING）フェーズへの移行を命じる
    await sio.emit("start_settling", {"target": target_val})

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

from pydantic import BaseModel

class ScanTrigger(BaseModel):
    message: str
    target_value: str | None = None

@app.post("/api/nao/trigger")
async def nao_trigger(data: ScanTrigger):
    """
    NAOが人を検知したら、このAPIを叩く
    """
    print(f"NAOからの信号を受信: {data.message}")
    
    # フロントエンドにシャッフル開始を命じる
    await sio.emit("change_phase", "SHUFFLE")
    
    # ここでOllamaなどの推論を走らせる
    # ...
    
    return {"status": "accepted"}