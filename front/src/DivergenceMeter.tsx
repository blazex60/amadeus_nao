import React, { useState, useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import './App.css';

// バックエンドのURL（Docker Compose環境）
const SOCKET_URL = "http://localhost:8000";

const DivergenceMeter = () => {
  const [phase, setPhase] = useState('IDLE');
  const [displayChars, setDisplayChars] = useState(Array(8).fill('0'));
  const [lockedIndices, setLockedIndices] = useState([]);
  const targetValueRef = useRef("0.000000");
  const socketRef = useRef(null);

  // --- Socket.io 接続設定 ---
  useEffect(() => {
    socketRef.current = io(SOCKET_URL);

    // バックエンドからのフェーズ変更命令を受信
    socketRef.current.on("change_phase", (newPhase) => {
      setPhase(newPhase);
    });

    // バックエンドからの数値確定命令を受信
    socketRef.current.on("start_settling", (data) => {
      targetValueRef.current = data.target;
      setPhase('SETTLING');
    });

    return () => socketRef.current.disconnect();
  }, []);

  // --- ボタンクリック時の挙動 ---
  const handleScanClick = () => {
    // バックエンドにスキャン開始をリクエスト
    socketRef.current.emit("request_scan");
  };

  // --- アニメーション制御（前回のロジックを流用） ---
  useEffect(() => {
    let shuffleTimer;
    let lockTimer;

    if (phase === 'IDLE' || phase === 'RESULT') {
        // 結果表示
        setDisplayChars(targetValueRef.current.split(''));
    } else if (phase === 'SHUFFLE') {
        shuffleTimer = setInterval(() => {
            setDisplayChars(prev => prev.map((c, i) => i === 1 ? '.' : Math.floor(Math.random() * 10).toString()));
        }, 30);
    } else if (phase === 'SETTLING') {
        // 1. シャッフル継続
        shuffleTimer = setInterval(() => {
            setDisplayChars(prev => prev.map((char, idx) => {
                if (lockedIndices.includes(idx)) return targetValueRef.current[idx];
                return Math.floor(Math.random() * 10).toString();
            }));
        }, 30);

        // 2. 0.4秒ごとに一桁ロック（自動で進む）
        if (lockedIndices.length < 8) {
            lockTimer = setTimeout(() => {
                const unlocked = [0, 2, 3, 4, 5, 6, 7].filter(i => !lockedIndices.includes(i));
                if (unlocked.length > 0) {
                    const randomIdx = unlocked[Math.floor(Math.random() * unlocked.length)];
                    setLockedIndices([...lockedIndices, randomIdx]);
                } else {
                    setPhase('RESULT');
                }
            }, 400);
        } else {
            setPhase('RESULT');
        }
    }

    return () => {
        clearInterval(shuffleTimer);
        clearTimeout(lockTimer);
    };
  }, [phase, lockedIndices]);

  return (
    <div className="bg-black min-h-screen flex flex-col items-center justify-center">
      <div className="meter-container">
        {displayChars.map((char, index) => (
          <div key={index} className={`nixie-tube ${char === '.' ? 'dot' : ''}`}>
            <span className={`digit ${phase !== 'IDLE' ? 'active' : ''}`}>{char}</span>
            {char !== '.' && <span className="digit dim">8</span>}
          </div>
        ))}
      </div>

      <div className="mt-10">
        <button 
          onClick={handleScanClick}
          className="px-6 py-2 bg-red-900 text-white font-mono border border-red-500 hover:bg-red-700 transition"
          disabled={phase === 'SHUFFLE' || phase === 'SETTLING'}
        >
          CONNECT TO AMADEUS
        </button>
      </div>
    </div>
  );
};

export default DivergenceMeter;