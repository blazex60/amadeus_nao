import React, { useState, useEffect, useRef, useCallback } from 'react';
// 親のApp.tsxでApp.cssが読み込まれていればスタイルは適用されますが、
// 念のためここでもインポートしておくと確実です。
import './App.css'; 

// 1つのニキシー管を表示するサブコンポーネント
// ここで "nixie-digit" クラスを使うのがポイントです
const NixieTube = ({ value }: { value: string }) => {
  return (
    <div className="nixie-digit">
      {value}
    </div>
  );
};

// 小数点を表示するサブコンポーネント
const NixieDot = () => {
  return (
    <div className="nixie-dot">.</div>
  );
}

interface DivergenceMeterProps {
  targetValue?: string;
}

const DivergenceMeter = ({ targetValue }: DivergenceMeterProps) => {
  // 初期値
  const [displayValue, setDisplayValue] = useState("1.048596");
  
  const intervalRef = useRef<number | null>(null);

  // 数値整形関数
  const formatValue = useCallback((val: string): string => {
    const num = parseFloat(val);
    if (isNaN(num)) return "0.000000";
    return num.toFixed(6);
  }, []);

  // ランダム生成関数
  const generateRandomWorldLine = useCallback((): string => {
    const whole = Math.floor(Math.random() * 4); // 0-3
    const decimal = Math.floor(Math.random() * 1000000).toString().padStart(6, '0');
    return `${whole}.${decimal}`;
  }, []);

  // アニメーションロジック
  useEffect(() => {
    if (!targetValue) return;

    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
    }

    const duration = 2000; // 2秒間演出
    const startTime = Date.now();

    intervalRef.current = window.setInterval(() => {
      const elapsed = Date.now() - startTime;

      if (elapsed > duration) {
        setDisplayValue(formatValue(targetValue));
        if (intervalRef.current !== null) {
          window.clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      } else {
        setDisplayValue(generateRandomWorldLine());
      }
    }, 50);

    return () => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
      }
    };
  }, [targetValue, formatValue, generateRandomWorldLine]);

  // 文字列を分解して表示
  const chars = displayValue.split('');

  return (
    // ここで "meter-container" クラスを指定します
    <div className="meter-container">
      {chars.map((char, index) => {
        if (char === '.') {
          return <NixieDot key={`dot-${index}`} />;
        } else {
          return <NixieTube key={`digit-${index}`} value={char} />;
        }
      })}
    </div>
  );
};

export default DivergenceMeter;