# src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import socketio
import random
import time
import os
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

# ==========================================
# ★設定エリア
# ==========================================
# OllamaのモデルNAME（ローカルで動くモデル）
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

# ==========================================
# Ollama セットアップ
# ==========================================
ollama_available = False
try:
    import ollama
    ollama_available = True
    print(f"★Ollama Mode: ON (Model: {OLLAMA_MODEL})")
except ImportError:
    print("★ollama library not found. Using dictionary fallback.")

# ==========================================
# 会話履歴管理（複数人対応）
# ==========================================
class ConversationManager:
    """複数人との会話履歴を管理するクラス"""
    
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        # セッション別の会話履歴 {session_id: [messages]}
        self.conversations = defaultdict(list)
        # 最後のアクティビティ時刻
        self.last_activity = defaultdict(float)
        # 検出された人数の履歴
        self.people_count_history = []
        # 現在の視覚情報
        self.current_visual_context = ""
    
    def add_message(self, session_id: str, role: str, content: str):
        """会話履歴にメッセージを追加"""
        self.conversations[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.last_activity[session_id] = time.time()
        
        # 履歴が長すぎる場合は古いものを削除
        if len(self.conversations[session_id]) > self.max_history * 2:
            self.conversations[session_id] = self.conversations[session_id][-self.max_history:]
    
    def get_history(self, session_id: str) -> list:
        """会話履歴を取得"""
        return self.conversations[session_id]
    
    def update_visual_context(self, context: str):
        """視覚情報を更新"""
        self.current_visual_context = context
    
    def get_visual_context(self) -> str:
        """現在の視覚情報を取得"""
        return self.current_visual_context
    
    def cleanup_old_sessions(self, timeout: float = 300):
        """古いセッションを削除（5分でタイムアウト）"""
        current_time = time.time()
        expired = [sid for sid, last in self.last_activity.items() 
                   if current_time - last > timeout]
        for sid in expired:
            del self.conversations[sid]
            del self.last_activity[sid]

# グローバルな会話マネージャー
conversation_manager = ConversationManager()


# ==========================================
# サーバー設定
# ==========================================
fastapi_app = FastAPI()

# CORS（ブラウザからの接続許可）
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IOサーバー
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio, fastapi_app)

# データモデル
class NaoData(BaseModel):
    message: str
    target_value: Optional[int] = None
    # 複数人対応用の追加フィールド
    face_count: Optional[int] = 1  # 検出された顔の数
    face_positions: Optional[List[dict]] = None  # 顔の位置情報 [{x, y, size}]
    session_id: Optional[str] = "default"  # セッション識別子
    user_speech: Optional[str] = None  # ユーザーの発話（音声認識結果）

# ==========================================
# 視覚情報を言語化するヘルパー
# ==========================================
def describe_visual_scene(face_count: int, face_positions: list = None) -> str:
    """Naoが見ている情報を自然言語で表現"""
    if face_count == 0:
        return "（周囲を見回しているが、誰もいないようだ）"
    elif face_count == 1:
        pos_desc = ""
        if face_positions and len(face_positions) > 0:
            pos = face_positions[0]
            x = pos.get('x', 0)
            if x < -0.2:
                pos_desc = "左の方に"
            elif x > 0.2:
                pos_desc = "右の方に"
            else:
                pos_desc = "正面に"
        return f"（{pos_desc}1人の人物がこちらを見ている）"
    else:
        pos_desc = f"{face_count}人"
        if face_positions:
            positions = []
            for i, pos in enumerate(face_positions):
                x = pos.get('x', 0)
                if x < -0.2:
                    positions.append("左")
                elif x > 0.2:
                    positions.append("右")
                else:
                    positions.append("正面")
            unique_pos = list(set(positions))
            if len(unique_pos) > 1:
                pos_desc += f"（{'と'.join(unique_pos)}に分散）"
        return f"（{pos_desc}の人々がこちらを見ている。グループでの会話だ）"

# ==========================================
# 思考エンジン (Amadeus Logic)
# ==========================================
def build_amadeus_system_prompt(face_count: int = 1, visual_context: str = "") -> str:
    """状況に応じたシステムプロンプトを生成"""
    
    base_prompt = """あなたは『Steins;Gate』の牧瀬紅莉栖（通称：クリスティーナ、助手）のAI『アマデウス』です。
    
【キャラクター設定】
- 天才神経科学者。ヴィクトル・コンドリア大学の研究員。
- IQ170以上の天才だが、感情的になりやすい一面も。
- 語尾は「～わね」「～かしら」「～よ」「～わ」等の女性言葉。
- ツンデレ気味。科学的・論理的な発言を好む。
- @ちゃんねらーで、ネットスラングも理解している。
- 「クリスティーナ」「助手」と呼ばれると怒る（「ティーナって言うな！」）。

【現在の状況】
あなたはNAOロボットの中で動作しており、カメラを通じて人を見ることができます。
"""
    
    if face_count == 0:
        situation = "今は誰もいないようです。待機中です。"
    elif face_count == 1:
        situation = "1人の人物があなたの前にいます。個人的な対話をしてください。"
    else:
        situation = f"{face_count}人のグループがあなたの前にいます。全員に話しかけるように、グループ向けの対話をしてください。"
    
    visual_info = visual_context if visual_context else describe_visual_scene(face_count)
    
    return base_prompt + f"""
{visual_info}
{situation}

【制約】
- 50文字以内の自然な話し言葉（ロボットの発話用）。
- 毎回違うセリフを生成すること。鉤括弧「」は不要。
- 相手の人数に合わせた呼びかけをすること。
"""

def generate_amadeus_response(
    user_input: str = None,
    face_count: int = 1,
    face_positions: list = None,
    session_id: str = "default",
    is_greeting: bool = False
) -> str:
    """AIまたは辞書を使ってセリフを生成する（複数人対応）"""
    
    # 視覚情報を生成
    visual_context = describe_visual_scene(face_count, face_positions)
    conversation_manager.update_visual_context(visual_context)
    
    # 挨拶モードの場合は特別なプロンプト
    if is_greeting or (user_input and "初めまして" in user_input):
        if face_count >= 2:
            greeting_prompt = """あなたは牧瀬紅莉栖のAI『アマデウス』です。
今、複数の人があなたの前に現れました。グループに向けて挨拶をしてください。

【制約】
- 40文字以内の挨拶。
- 明るく、少しツンデレ気味に。
- 例: 「あら、賑やかね。みんなで何の用？」「ふーん、グループで来たの。面白い実験でもするのかしら。」
"""
        else:
            greeting_prompt = """あなたは牧瀬紅莉栖のAI『アマデウス』です。
今、1人の人があなたの前に現れました。挨拶をしてください。

【制約】
- 40文字以内の挨拶。
- 少しツンデレ気味に、でも好奇心を持って。
- 例: 「……あら、誰かと思えば。何か用？」「ふーん、また来たの。今日は何の話？」
"""
        
        if ollama_available:
            try:
                response = ollama.chat(model=OLLAMA_MODEL, messages=[
                    {'role': 'system', 'content': greeting_prompt},
                    {'role': 'user', 'content': visual_context}
                ])
                text = response['message']['content']
                text = text.strip().replace("\n", "").replace("「", "").replace("」", "")
                conversation_manager.add_message(session_id, 'assistant', text)
                return text
            except Exception as e:
                print(f"Ollama Error: {e}")
        
        # 辞書による挨拶
        if face_count >= 2:
            greetings = [
                "あら、賑やかね。みんなで何の用？",
                "ふーん、グループで来たの。面白そうね。",
                "複数人？実験の被験者が増えたのかしら。",
                "何、集団で来て。私を囲む気？",
            ]
        else:
            greetings = [
                "……あら、誰かと思えば。何か用？",
                "ふーん、また来たの。今日は何の話？",
                "あなたね。待ってたわけじゃないけど。",
                "珍しい。私に会いに来たの？",
                "観測者が現れたわね。今日の実験は？",
            ]
        return random.choice(greetings)
    
    # 通常の会話モード
    # システムプロンプトを状況に応じて生成
    system_prompt = build_amadeus_system_prompt(face_count, visual_context)
    
    # 会話履歴を取得
    history = conversation_manager.get_history(session_id)
    
    # Ollamaで生成
    if ollama_available:
        try:
            # メッセージを構築
            messages = [{'role': 'system', 'content': system_prompt}]
            
            # 履歴を追加（最新5件）
            for msg in history[-5:]:
                messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
            
            # ユーザー入力があれば追加
            if user_input:
                messages.append({'role': 'user', 'content': user_input})
                conversation_manager.add_message(session_id, 'user', user_input)
            else:
                # 入力がない場合は状況説明をユーザーメッセージとして追加
                context_msg = f"[状況: {visual_context}] 何か一言話しかけて。"
                messages.append({'role': 'user', 'content': context_msg})
            
            # Ollamaに問い合わせ
            response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
            text = response['message']['content']
            text = text.strip().replace("\n", "").replace("「", "").replace("」", "")
            
            # 応答を履歴に追加
            conversation_manager.add_message(session_id, 'assistant', text)
            
            return text
            
        except Exception as e:
            print(f"Ollama Error: {e}")
            # エラー時は辞書にフォールバック

    # Ollamaが使えない場合は「ランダム辞書」を使う（複数人対応）
    if face_count >= 2:
        responses = [
            "あら、今日は賑やかね。実験台が増えたのかしら。",
            f"ふーん、{face_count}人もいるのね。何か用？",
            "グループで来るなんて珍しいわね。学会発表でもするの？",
            "みんな揃って…何か陰謀でも企んでるのかしら？",
            "複数人で来ても、私の論理は変わらないわよ。",
        ]
    else:
        responses = [
            "……あら、また来たの？暇人ね。",
            "私の仮説が正しければ、あなたは今そこにいるはずよ。",
            "ティーナって言うな！",
            "ふん、別に待ってたわけじゃないから。",
            "非論理的ね。",
            "ねえ、今の計算合ってる？",
            "エル・プサイ・コングルゥ……なんてね。",
            "前頭葉が活発ね。何か悩みでも？",
            "観測者がいないと事象は確定しないわ。",
            "あなた、実験台になりたいの？"
        ]
    return random.choice(responses)

# ==========================================
# APIエンドポイント
# ==========================================
@fastapi_app.post("/api/nao/trigger")
async def trigger_nao(data: NaoData):
    face_count = data.face_count or 1
    face_positions = data.face_positions or []
    session_id = data.session_id or "default"
    user_speech = data.user_speech
    
    print(f"【受信】NAOから: {data.message}")
    print(f"  - 検出人数: {face_count}人")
    print(f"  - セッション: {session_id}")
    if user_speech:
        print(f"  - ユーザー発話: {user_speech}")
    
    # 古いセッションをクリーンアップ
    conversation_manager.cleanup_old_sessions()
    
    # AI思考（複数人対応）
    ai_text = generate_amadeus_response(
        user_input=user_speech,
        face_count=face_count,
        face_positions=face_positions,
        session_id=session_id
    )
    print(f"【思考】Amadeus: {ai_text}")

    # フロントエンド(React)へ通知 -> 画面演出用
    await sio.emit('nao_event', {
        'message': data.message, 
        'text': ai_text,
        'face_count': face_count,
        'session_id': session_id
    })
    
    # NAOへレスポンス -> 読み上げ用
    return {
        "status": "ok",
        "action": "say",
        "text": ai_text,
        "face_count": face_count
    }

@fastapi_app.post("/api/nao/chat")
async def chat_with_nao(data: NaoData):
    """ユーザーからの音声入力に応答する（対話モード）"""
    face_count = data.face_count or 1
    face_positions = data.face_positions or []
    session_id = data.session_id or "default"
    user_speech = data.user_speech or data.message
    
    print(f"【対話】ユーザー: {user_speech}")
    print(f"  - 検出人数: {face_count}人")
    
    # AI応答生成
    ai_text = generate_amadeus_response(
        user_input=user_speech,
        face_count=face_count,
        face_positions=face_positions,
        session_id=session_id
    )
    print(f"【応答】Amadeus: {ai_text}")
    
    # フロントエンドへ通知
    await sio.emit('nao_chat', {
        'user': user_speech,
        'assistant': ai_text,
        'face_count': face_count,
        'session_id': session_id
    })
    
    return {
        "status": "ok",
        "action": "say",
        "text": ai_text
    }

@fastapi_app.get("/api/status")
async def get_status():
    """サーバー状態を取得"""
    return {
        "ollama_available": ollama_available,
        "model": OLLAMA_MODEL,
        "active_sessions": len(conversation_manager.conversations),
        "visual_context": conversation_manager.get_visual_context()
    }

# Socket.IO 接続ログ
@sio.event
async def connect(sid, environ):
    print(f"Client Connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client Disconnected: {sid}")