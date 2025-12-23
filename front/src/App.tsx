import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './App.css'; 
import DivergenceMeter from './DivergenceMeter';

// ★★★★★ 重要：ここに Pop!_OS の IPアドレス を入力 ★★★★★
// 例: 'http://192.168.10.105:8000'
const SOCKET_URL = 'http://192.168.10.2:8000'; 

// ★ 音声ファイルのリスト (public/voices/ フォルダに入れてください)
// ファイルがない場合は空配列 [] でもエラーにはなりませんが音は出ません
const VOICE_LIST = [
  '/voices/greeting.mp3',
  '/voices/alert.mp3',
];

function App() {
  // --- ステート管理 ---
  const [worldLine, setWorldLine] = useState("1.048596");
  const [statusLog, setStatusLog] = useState("System Initialized.");
  const [socketStatus, setSocketStatus] = useState("Disconnected");
  
  // 音声・演出系ステート
  const [isAudioEnabled, setIsAudioEnabled] = useState(false); // ブラウザの音声許可フラグ
  const [amadeusMessage, setAmadeusMessage] = useState("Listening for signal...");
  const [isGlitching, setIsGlitching] = useState(false); // グリッチ発動フラグ

  // --- ソケット通信とイベント処理 ---
  useEffect(() => {
    const socket = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
    });

    // 接続成功
    socket.on('connect', () => {
      console.log("Socket Connected:", socket.id);
      setSocketStatus("Connected");
      setStatusLog("Connection Established. Waiting for Amadeus...");
    });

    // 接続エラー
    socket.on('connect_error', (err) => {
      console.error("Socket Error:", err);
      setSocketStatus("Connection Error");
      setStatusLog(`Error: ${err.message}`);
    });

    // ★ NAOからのイベント受信 (ここが心臓部)
    socket.on('nao_event', (data: any) => {
      console.log("Event Received:", data);

      // 1. 演出開始（グリッチ＆フラッシュ）
      triggerGlitchEffect();

      // 2. 世界線変動（ランダム値）
      const randomDecimal = Math.floor(Math.random() * 1000000).toString().padStart(6, '0');
      setWorldLine(`1.${randomDecimal}`);

      // 3. AIのセリフを表示 (data.text があればそれを、なければデフォルト)
      const aiText = data.text || "Target confirmed.";
      setAmadeusMessage(aiText);
      
      // ログ更新
      setStatusLog(`Signal Detected. AI Response: "${aiText}"`);

      // 4. 音声再生 (許可済みの場合のみ)
      if (isAudioEnabled) {
        playRandomVoice();
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [isAudioEnabled]); // 音声許可フラグが変わったら再設定

  // --- 演出用関数 ---

  // グリッチを0.5秒だけONにする
  const triggerGlitchEffect = () => {
    setIsGlitching(true);
    setTimeout(() => {
      setIsGlitching(false);
    }, 500); // 0.5秒後に元に戻す
  };

  // 音声をランダム再生
  const playRandomVoice = () => {
    if (VOICE_LIST.length === 0) return;
    const randomIndex = Math.floor(Math.random() * VOICE_LIST.length);
    const audio = new Audio(VOICE_LIST[randomIndex]);
    audio.volume = 1.0;
    audio.play().catch(e => console.error("Play error:", e));
  };

  // システム起動ボタン（音声許可のため）
  const handleStart = () => {
    setIsAudioEnabled(true);
    // ダミー再生で制限解除
    new Audio().play().catch(() => {});
    triggerGlitchEffect(); // 起動時も演出を入れるとかっこいい
    setStatusLog("System Started. Audio Output Enabled.");
  };

// src/App.tsx の return の中身を以下のように修正

return (
  <div className="App">
    {/* ヘッダーエリア */}
    <div>
      <h1>Amadeus System</h1>
      {/* クラス名を適用 */}
      <div className="net-status" style={{ color: socketStatus === "Connected" ? '#0f0' : '#f00' }}>
        NET STATUS: [{socketStatus}]
      </div>
    </div>

    {/* ダイバージェンスメーターエリア */}
    {/* ここは DivergenceMeter コンポーネント側で .meter-container, .nixie-digit を使う想定 */}
    <DivergenceMeter targetValue={worldLine} />

    {/* AIセリフエリア */}
    <div className="amadeus-text-box">
      <div className="amadeus-text">
        <span className="ai-label">AI:</span>
        {amadeusMessage}
      </div>
    </div>

    {/* システムログエリア */}
    <div className="system-log">
      <div><span className="log-prompt">&gt;</span> {statusLog}</div>
      {/* カーソルの点滅演出などを入れても良いでしょう */}
    </div>
  </div>
)};

export default App;