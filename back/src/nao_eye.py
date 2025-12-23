# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import subprocess
import uuid
from naoqi import ALProxy

# 環境変数から設定を読み込み（デフォルト値付き）
PC_IP = os.getenv("PC_IP", "192.168.10.2")
PC_PORT = os.getenv("PC_PORT", "8000")
ENDPOINT_TRIGGER = "http://" + PC_IP + ":" + PC_PORT + "/api/nao/trigger"
ENDPOINT_CHAT = "http://" + PC_IP + ":" + PC_PORT + "/api/nao/chat"

# セッションIDを生成（Nao起動ごとに一意）
SESSION_ID = str(uuid.uuid4())[:8]

def extract_face_info(face_data):
    """
    顔認識データから人数と位置情報を抽出
    NAO FaceDetectedの実際の構造:
    [timestamp, [[[idx, alpha, beta, width, height], extra_info], ...], camera_info]
    """
    face_count = 0
    face_positions = []
    
    try:
        if face_data and isinstance(face_data, list) and len(face_data) >= 2:
            # face_data[1][0]が顔情報の配列
            face_info_array = face_data[1]
            if isinstance(face_info_array, list) and len(face_info_array) >= 1:
                faces = face_info_array[0]  # 顔のリスト
                
                if isinstance(faces, list):
                    for face in faces:
                        if isinstance(face, list) and len(face) >= 1:
                            shape = face[0]  # 実際の形: [idx, alpha, beta, width, height]
                            if isinstance(shape, list) and len(shape) >= 5:
                                # shape[0]はインデックス、shape[1]以降が座標
                                face_count += 1
                                face_positions.append({
                                    "x": float(shape[1]),  # alpha: 水平位置
                                    "y": float(shape[2]),  # beta: 垂直位置
                                    "size": float(shape[3]) * float(shape[4])  # width * height
                                })
                            elif isinstance(shape, (int, float)):
                                # shapeが数値の場合、face自体が座標配列
                                # [idx, alpha, beta, width, height] の形式
                                if len(face) >= 5:
                                    face_count += 1
                                    face_positions.append({
                                        "x": float(face[1]),
                                        "y": float(face[2]),
                                        "size": float(face[3]) * float(face[4])
                                    })
                                break
                    
                    # 顔が見つからなかったが、データがある場合は1人と仮定
                    if face_count == 0 and len(faces) > 0:
                        face_count = 1
                        
    except Exception as e:
        print("[Error] Parsing face data: " + str(e))
        if face_data:
            face_count = 1
    
    return face_count, face_positions

def main():
    nao_ip = "127.0.0.1"
    nao_port = 9559
    if len(sys.argv) > 1:
        nao_ip = sys.argv[1]
    if len(sys.argv) > 2:
        nao_port = int(sys.argv[2])

    print("-----------------------------------")
    print("Connecting to NAO: " + nao_ip)
    print("Session ID: " + SESSION_ID)
    
    try:
        # 各種プロキシへの接続
        memory = ALProxy("ALMemory", nao_ip, nao_port)
        tts = ALProxy("ALTextToSpeech", nao_ip, nao_port)
        leds = ALProxy("ALLeds", nao_ip, nao_port)
        motion = ALProxy("ALMotion", nao_ip, nao_port)
        face = ALProxy("ALFaceDetection", nao_ip, nao_port)  # ★顔認識プロキシ
        
        # 音声認識（対話モード用）- 初期化のみ、subscribeは会話モードで
        speech_recog = None
        speech_available = False
        try:
            speech_recog = ALProxy("ALSpeechRecognition", nao_ip, nao_port)
            speech_recog.setLanguage("Japanese")
            speech_available = True
            print("Speech Recognition: Available (will activate in conversation mode)")
        except Exception as e:
            print("Speech Recognition: Not available - " + str(e))

        # アニメーション音声（あれば）
        try:
            animated_speech = ALProxy("ALAnimatedSpeech", nao_ip, nao_port)
            use_animated = True
        except:
            use_animated = False

        # 顔認識を強制的にONにする（サブスクライブ）
        print("Subscribing to Face Detection...")
        face.subscribe("Amadeus_Eye")

        # 起立
        motion.wakeUp()
        
    except Exception as e:
        print("Error connecting to NAO modules: " + str(e))
        return

    # 準備完了の合図（目が紫になる）
    leds.fadeRGB("FaceLeds", 0.6, 0.0, 1.0, 1.0)
    print("NAO Eye Active. Target Server: " + PC_IP)
    print("Waiting for faces...")

    last_detect_time = 0
    cooldown = 5.0
    last_face_count = 0  # 前回検出した人数 
    
    # 状態管理
    # idle: 待機中、greeting: 挨拶中、conversation: 会話モード
    mode = "idle"
    no_face_timer = 0  # 顔が見えなくなってからの時間
    no_face_timeout = 3.0  # 3秒間顔が見えなかったら待機モードへ
    greeting_done = False  # 挨拶済みフラグ
    conversation_idle_time = 0  # 会話モード中の無音時間
    conversation_timeout = 15.0  # 15秒無音なら待機モードへ
    last_speech_time = 0  # 最後に発話した時刻
    speech_cooldown = 3.0  # 発話後3秒間は音声認識をスキップ

    try:
        while True:
            # 1. 顔認識メモリを監視
            val = memory.getData("FaceDetected")
            current_time = time.time()
            
            # データがあるかチェック
            if val and isinstance(val, list) and len(val) >= 2:
                # 顔情報を解析
                face_count, face_positions = extract_face_info(val)
                
                if face_count > 0:
                    # 顔が見えている - タイマーリセット
                    no_face_timer = 0
                    conversation_idle_time = current_time
                    
                    # == 待機モードからの遷移 ==
                    if mode == "idle":
                        # 初回検出：挨拶モードへ
                        if face_count == 1:
                            print("[!] 1 person detected! Greeting...")
                        else:
                            print("[!] " + str(face_count) + " people detected! Greeting...")
                        
                        mode = "greeting"
                        last_face_count = face_count
                        
                        # 挨拶を生成
                        payload = {
                            "message": "Greeting",
                            "face_count": face_count,
                            "face_positions": face_positions,
                            "session_id": SESSION_ID,
                            "user_speech": "初めまして"  # 挨拶トリガー
                        }
                        
                        cmd = [
                            "/usr/bin/curl",
                            "-s", "-X", "POST",
                            "-H", "Content-Type: application/json",
                            "-H", "Expect:",
                            "-d", json.dumps(payload),
                            "--max-time", "30",
                            ENDPOINT_TRIGGER
                        ]
                        
                        try:
                            # 思考中（白点滅）
                            leds.fadeRGB("FaceLeds", 1.0, 1.0, 1.0, 0.1)
                            
                            response_json = subprocess.check_output(cmd)
                            print("Server Response: " + str(response_json))
                            
                            data = json.loads(response_json)
                            if "text" in data:
                                ai_text = data["text"]
                                
                                # 発話中（赤）- 音声認識を一時停止
                                if speech_available:
                                    try:
                                        speech_recog.unsubscribe("Amadeus_Ear")
                                        print("[Speech] Recognition paused for speaking")
                                    except:
                                        pass
                                
                                leds.fadeRGB("FaceLeds", 1.0, 0.0, 0.0, 0.2)
                                print("[Speaking] " + ai_text[:50] + "...")
                                
                                if use_animated:
                                    gesture = "^start(animations/Stand/Gestures/Hey_1) "
                                    animated_speech.say(gesture + ai_text.encode('utf-8'))
                                else:
                                    tts.say(ai_text.encode('utf-8'))
                                
                                # 発話完了 - ここでタイマー記録
                                print("[Speaking] Finished. Starting cooldown.")
                                last_speech_time = time.time()
                                
                                # 会話モードへ移行（緑）
                                leds.fadeRGB("FaceLeds", 0.0, 1.0, 0.0, 1.0)
                                mode = "conversation"
                                greeting_done = True
                                print("--> Conversation mode activated")
                                
                                # 音声認識を再開（クールダウン後に有効になる）
                                if speech_available:
                                    try:
                                        vocabulary = [
                                            "こんにちは", "こんばんは", "おはよう",
                                            "ありがとう", "はい", "いいえ",
                                            "さようなら", "またね", "バイバイ",
                                            "アマデウス", "紅莉栖", "クリスティーナ",
                                            "元気", "質問", "教えて", "聞きたい",
                                            "面白い", "すごい", "なるほど"
                                        ]
                                        speech_recog.setVocabulary(vocabulary, False)
                                        speech_recog.subscribe("Amadeus_Ear")
                                        print("[Speech] Recognition restarted (cooldown active for " + str(speech_cooldown) + "s)")
                                    except Exception as e:
                                        print("[Error] Speech recognition subscribe failed: " + str(e))
                                
                        except subprocess.CalledProcessError as e:
                            print("[Error] Server unreachable.")
                            leds.fadeRGB("FaceLeds", 0.0, 0.0, 1.0, 0.5)
                            mode = "idle"
                    
                    # == 会話モード ==
                    elif mode == "conversation":
                        # 音声認識で会話（発話直後はスキップ）
                        time_since_speech = current_time - last_speech_time
                        
                        if speech_available and time_since_speech > speech_cooldown:
                            try:
                                # WordRecognizedイベントをチェック
                                speech_data = memory.getData("WordRecognized")
                                if speech_data and len(speech_data) > 0:
                                    recognized_word = speech_data[0]
                                    confidence = speech_data[1] if len(speech_data) > 1 else 0
                                    
                                    if confidence > 0.3:  # 信頼度30%以上
                                        print("[Speech] Recognized: " + str(recognized_word) + " (confidence: " + str(confidence) + ")")
                                        
                                        # サーバーに送信（会話エンドポイント）
                                        payload = {
                                            "message": recognized_word,
                                            "face_count": face_count,
                                            "face_positions": face_positions,
                                            "session_id": SESSION_ID,
                                            "user_speech": recognized_word
                                        }
                                        
                                        cmd = [
                                            "/usr/bin/curl",
                                            "-s", "-X", "POST",
                                            "-H", "Content-Type: application/json",
                                            "-H", "Expect:",
                                            "-d", json.dumps(payload),
                                            "--max-time", "30",
                                            ENDPOINT_CHAT
                                        ]
                                        
                                        try:
                                            leds.fadeRGB("FaceLeds", 1.0, 1.0, 1.0, 0.1)
                                            response_json = subprocess.check_output(cmd)
                                            data = json.loads(response_json)
                                            
                                            if "text" in data:
                                                ai_text = data["text"]
                                                print("[Speaking] " + ai_text[:50] + "...")
                                                leds.fadeRGB("FaceLeds", 1.0, 0.0, 0.0, 0.2)
                                                
                                                if use_animated:
                                                    gesture = "^start(animations/Stand/Gestures/Explain_1) "
                                                    animated_speech.say(gesture + ai_text.encode('utf-8'))
                                                else:
                                                    tts.say(ai_text.encode('utf-8'))
                                                
                                                # 発話完了 - ここでタイマー記録
                                                print("[Speaking] Finished. Starting cooldown.")
                                                last_speech_time = time.time()
                                                
                                                leds.fadeRGB("FaceLeds", 0.0, 1.0, 0.0, 1.0)
                                                conversation_idle_time = current_time
                                        except:
                                            print("[Error] Chat request failed")
                            except:
                                pass
                        elif speech_available and time_since_speech <= speech_cooldown:
                            # クールダウン中
                            remaining = speech_cooldown - time_since_speech
                            if int(remaining * 10) % 10 == 0:  # 0.1秒ごとに1回だけ表示
                                print("[Cooldown] Waiting " + str(round(remaining, 1)) + "s before listening...")
                        
                        # 会話タイムアウトチェック
                        if current_time - conversation_idle_time > conversation_timeout:
                            print("[Timeout] No conversation for " + str(conversation_timeout) + "s")
                            print("[Speaking] Saying goodbye...")
                            tts.say("また後で話しましょう".encode('utf-8'))
                            print("[Speaking] Finished. Starting cooldown.")
                            last_speech_time = time.time()  # 発話時刻を記録
                            mode = "idle"
                            greeting_done = False
                            leds.fadeRGB("FaceLeds", 0.6, 0.0, 1.0, 1.0)
                            # 音声認識停止
                            if speech_available:
                                try:
                                    speech_recog.unsubscribe("Amadeus_Ear")
                                except:
                                    pass
                        
                        # 人数変化の検出
                        if face_count != last_face_count:
                            print("[!] People count changed: " + str(last_face_count) + " -> " + str(face_count))
                            last_face_count = face_count
                
            else:
                # 顔が見つからない場合
                if last_face_count > 0 or mode != "idle":
                    no_face_timer += 0.2
                    
                    if no_face_timer >= no_face_timeout:
                        print("[!] No face detected for " + str(no_face_timeout) + "s. Returning to idle mode.")
                        if mode == "conversation":
                            print("[Speaking] Saying goodbye...")
                            tts.say("さようなら".encode('utf-8'))
                            print("[Speaking] Finished. Starting cooldown.")
                            last_speech_time = time.time()  # 発話時刻を記録
                            # 音声認識停止
                            if speech_available:
                                try:
                                    speech_recog.unsubscribe("Amadeus_Ear")
                                    print("[Speech] Recognition stopped")
                                except:
                                    pass
                        last_face_count = 0
                        mode = "idle"
                        greeting_done = False
                        leds.fadeRGB("FaceLeds", 0.6, 0.0, 1.0, 1.0)
                        no_face_timer = 0
                
        print("Stopping...")
    finally:
        # 終了時に顔認識をOFFにする（重要）
        try:
            face.unsubscribe("Amadeus_Eye")
        except:
            pass
        try:
            if speech_available:
                speech_recog.unsubscribe("Amadeus_Ear")
        except:
            pass
        motion.rest()
        print("Disconnected.")

if __name__ == "__main__":
    main()