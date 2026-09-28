import { useState, useEffect } from 'react';
import { CameraFeed } from './components/CameraFeed';
import type { GestureEvent, GestureErrorEvent, GestureName } from './hooks/useHandTracking';

export default function App() {
  const [lastGesture, setLastGesture] = useState<string>('—');
  const [errorPrompt, setErrorPrompt] = useState<GestureErrorEvent | null>(null);
  const [log, setLog] = useState<{ time: string; label: string }[]>([]);

  // Таймер
  const [timerOpen, setTimerOpen] = useState(false);
  const [timerMinutes, setTimerMinutes] = useState(5);
  const [timerRunning, setTimerRunning] = useState(false);
  const [timeLeft, setTimeLeft] = useState(300);

  // Countdown
  useEffect(() => {
    if (!timerRunning || timeLeft <= 0) return;
    const id = setInterval(() => setTimeLeft(t => t - 1), 1000);
    return () => clearInterval(id);
  }, [timerRunning, timeLeft]);

  function addToLog(label: string) {
    setLog(prev => [{ time: new Date().toLocaleTimeString(), label }, ...prev.slice(0, 14)]);
  }

  function handleGesture(e: GestureEvent) {
    // ─── PointUp ☝️ = слайдер (без лога, просто двигает значение) ───
    if (e.gesture === 'PointUp' && timerOpen && !timerRunning && e.value !== undefined) {
      const MINUTE_OPTIONS = [1, 2, 3, 4, 5, 10, 15, 20, 30, 50, 60, 120, 180];
      const clamped = Math.max(0.15, Math.min(0.85, e.value));
      const idx = Math.round(((clamped - 0.15) / 0.7) * (MINUTE_OPTIONS.length - 1));
      const mins = MINUTE_OPTIONS[MINUTE_OPTIONS.length - 1 - idx]; // верх = больше
      setTimerMinutes(mins);
      setTimeLeft(mins * 60);
      return;
    }

    // Для остальных жестов — логируем
    const LABELS: Record<string, string> = {
      ThumbUp: '👍 Следующий шаг',
      ThumbDown: '👎 Предыдущий шаг',
      Peace: '✌️ Peace',
      Stop: '✋ Стоп',
      OK: '👌 OK',
      PointUp: '☝️ Слайдер',
    };
    const label = `${LABELS[e.gesture] ?? e.gesture} (${e.hand})`;
    setLastGesture(label);
    addToLog(label);

    // ─── Peace ✌️ = открыть / запустить таймер ───
    if (e.gesture === 'Peace') {
      if (!timerOpen) {
        setTimerOpen(true);
        setTimerMinutes(5);
        setTimeLeft(300);
        setTimerRunning(false);
      } else {
        setTimerRunning(true);
      }
    }

    // ─── Stop ✋ = остановить (пауза) таймер ───
    if (e.gesture === 'Stop' && timerOpen) {
      setTimerRunning(false);
    }

    // ─── OK 👌 = закрыть таймер ───
    if (e.gesture === 'OK' && timerOpen) {
      setTimerOpen(false);
      setTimerRunning(false);
    }
  }

  function handleError(e: GestureErrorEvent | null) {
    setErrorPrompt(e);
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec < 10 ? '0' : ''}${sec}`;
  };

  // ─── Стили ──────────────────────────────────────────────
  const page: React.CSSProperties = {
    minHeight: '100vh', background: '#0f172a', color: '#fff',
    fontFamily: 'system-ui, sans-serif', padding: 24,
  };
  const card: React.CSSProperties = {
    background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 16,
  };
  const labelStyle: React.CSSProperties = {
    fontSize: 11, color: '#64748b', textTransform: 'uppercase',
    letterSpacing: 2, marginBottom: 8,
  };

  const sliderMarks = [180, 120, 60, 50, 30, 20, 15, 10, 5, 4, 3, 2, 1];

  const formatMinLabel = (m: number) => {
    if (m >= 60) return `${m / 60}ч`;
    return `${m}м`;
  };

  return (
    <div style={page}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 2 }}>
          🍳 Smart Chef — CV Playground
        </h1>
        <p style={{ color: '#64748b', fontSize: 13, marginBottom: 20 }}>
          Hand Landmarker · 2 руки · 6 кастомных жестов · режим ошибок
        </p>

        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {/* ═══ Камера ═══ */}
          <div style={{ flex: '0 0 auto' }}>
            <CameraFeed onGesture={handleGesture} onError={handleError} />

            <div style={{ ...card, marginTop: 16, fontSize: 13 }}>
              <p style={labelStyle}>Доступные жесты</p>
              <div style={{ lineHeight: 2.2 }}>
                👍 <b>Палец вверх</b> — следующий шаг<br/>
                👎 <b>Палец вниз</b> — предыдущий шаг<br/>
                ✌️ <b>Peace</b> — {timerOpen ? 'запустить таймер' : 'открыть таймер'}<br/>
                {timerOpen && <>☝️ <b>Указательный палец</b> — двигай руку вверх/вниз для выбора минут<br/></>}
                ✋ <b>Стоп</b> — {timerOpen ? 'остановить таймер' : <span style={{ color: '#475569' }}>нет действия</span>}<br/>
                👌 <b>OK</b> — {timerOpen ? 'закрыть таймер' : <span style={{ color: '#475569' }}>нет действия</span>}
              </div>
            </div>
          </div>

          {/* ═══ Результаты ═══ */}
          <div style={{ flex: 1, minWidth: 300 }}>
            {/* Последний жест */}
            <div style={{ ...card, textAlign: 'center' }}>
              <p style={labelStyle}>Последний жест</p>
              <p style={{ fontSize: 28, fontWeight: 900 }}>{lastGesture}</p>
            </div>

            {/* ═══ Таймер ═══ */}
            {timerOpen ? (
              <div style={{
                ...card,
                border: timerRunning ? '2px solid #22c55e' : '2px solid #334155',
                transition: 'all 0.3s',
              }}>
                <p style={labelStyle}>⏱ Таймер ({formatMinLabel(timerMinutes)})</p>

                <div style={{ display: 'flex', alignItems: 'center', gap: 24, justifyContent: 'center' }}>
                  {/* Слайдер визуал */}
                  {!timerRunning && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'center' }}>
                      <p style={{ fontSize: 10, color: '#64748b', marginBottom: 4 }}>☝️</p>
                      {sliderMarks.map(m => (
                        <div key={m} style={{
                          width: 42, height: 20, borderRadius: 4,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 11, fontWeight: 700,
                          background: m === timerMinutes ? '#22c55e' : '#0f172a',
                          color: m === timerMinutes ? '#fff' : '#475569',
                          transition: 'all 0.15s',
                        }}>
                          {formatMinLabel(m)}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Время */}
                  <div style={{ textAlign: 'center' }}>
                    <p style={{
                      fontSize: 64, fontWeight: 900, fontFamily: 'monospace',
                      color: timeLeft <= 10 && timerRunning ? '#ef4444' : (timerRunning ? '#22c55e' : '#94a3b8'),
                      lineHeight: 1,
                    }}>
                      {formatTime(timeLeft)}
                    </p>
                    <p style={{ fontSize: 13, color: '#64748b', marginTop: 8 }}>
                      {timerRunning
                        ? '▶ Идёт · ✋ пауза · 👌 закрыть'
                        : '⏸ Пауза · ☝️ выбери минуты · ✌️ старт · 👌 закрыть'}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ ...card, textAlign: 'center', border: '2px dashed #334155' }}>
                <p style={{ fontSize: 14, color: '#64748b' }}>
                  ✌️ Покажи <b>Peace</b>, чтобы открыть таймер
                </p>
              </div>
            )}

            {/* Ошибка (Twist) */}
            <div style={{
              ...card, textAlign: 'center',
              background: errorPrompt ? 'rgba(127,29,29,0.4)' : '#1e293b',
              border: errorPrompt ? '1px solid rgba(239,68,68,0.5)' : '1px solid transparent',
              transition: 'all 0.3s',
            }}>
              <p style={labelStyle}>Твист: подсказка</p>
              {errorPrompt ? (
                <p style={{ fontSize: 16, fontWeight: 700, color: '#f87171' }}>
                  ⚠️ {errorPrompt.message}
                </p>
              ) : (
                <p style={{ color: '#475569', fontStyle: 'italic', fontSize: 14 }}>Ошибок нет</p>
              )}
            </div>

            {/* Лог */}
            <div style={card}>
              <p style={labelStyle}>Лог распознаваний</p>
              {log.length === 0 ? (
                <p style={{ color: '#475569', fontStyle: 'italic', fontSize: 13 }}>Покажи жест камере...</p>
              ) : (
                <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                  {log.map((entry, i) => (
                    <div key={i} style={{
                      display: 'flex', justifyContent: 'space-between',
                      background: '#0f172a', padding: '5px 10px', borderRadius: 6,
                      marginBottom: 3, fontSize: 13,
                    }}>
                      <span style={{ color: '#64748b' }}>{entry.time}</span>
                      <span style={{ color: '#4ade80', fontWeight: 600 }}>{entry.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
