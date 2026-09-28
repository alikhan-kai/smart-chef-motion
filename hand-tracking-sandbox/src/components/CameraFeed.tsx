import { useEffect, useRef, useState } from 'react';
import type { GestureEvent, GestureErrorEvent } from '../hooks/useHandTracking';
import { useHandTracking } from '../hooks/useHandTracking';

interface Props {
  onGesture: (e: GestureEvent) => void;
  onError: (e: GestureErrorEvent | null) => void;
  showVfx?: boolean;
  timerOpen?: boolean;
  timerRunning?: boolean;
  timeLeft?: number;
}

export function CameraFeed({ onGesture, onError, showVfx, timerOpen, timerRunning, timeLeft }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState('Запускаю камеру...');

  const { isLoading } = useHandTracking({
    videoRef,
    canvasRef,
    onGesture,
    onError,
    noCooldownGestures: ['PointUp'],
  });

  useEffect(() => {
    let stream: MediaStream | null = null;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          setStatus('Камера подключена, загрузка ИИ...');
        }
      } catch (err) {
        setStatus('Ошибка камеры: ' + String(err));
      }
    })();
    return () => { stream?.getTracks().forEach(t => t.stop()); };
  }, []);

  useEffect(() => {
    if (!isLoading) setStatus('✅ Готово! Покажи жест камере.');
  }, [isLoading]);

  const formatTime = (s: number | undefined) => {
    if (s === undefined) return '0:00';
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec < 10 ? '0' : ''}${sec}`;
  };

  return (
    <div>
      {/* Ключевые кадры для анимации VFX */}
      <style>{`
        @keyframes vfx-pulse {
          0% { box-shadow: inset 0 0 50px rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.1); }
          50% { box-shadow: inset 0 0 150px rgba(239, 68, 68, 0.9); background: rgba(239, 68, 68, 0.4); }
          100% { box-shadow: inset 0 0 50px rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.1); }
        }
        @keyframes vfx-bounce {
          0% { transform: scale(1); }
          50% { transform: scale(1.1); }
          100% { transform: scale(1); }
        }
      `}</style>
      
      <p style={{ marginBottom: 8, color: '#9ca3af', fontSize: 13 }}>{status}</p>
      
      <div style={{ position: 'relative', display: 'inline-block', borderRadius: 12, overflow: 'hidden', background: '#000' }}>
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          width={480}
          height={360}
          style={{ display: 'block', transform: 'scaleX(-1)' }}
        />
        <canvas
          ref={canvasRef}
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%',
            transform: 'scaleX(-1)', pointerEvents: 'none',
          }}
        />

        {/* Плавающий таймер поверх камеры */}
        {timerOpen && !showVfx && (
          <div style={{
            position: 'absolute', top: 16, right: 16,
            background: 'rgba(0,0,0,0.6)', padding: '6px 14px',
            borderRadius: 8, color: timerRunning ? '#22c55e' : '#fff',
            fontFamily: 'monospace', fontSize: 28, fontWeight: 'bold',
            backdropFilter: 'blur(4px)',
            border: timerRunning ? '2px solid #22c55e' : '2px solid #475569',
            zIndex: 5,
            boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
          }}>
            {formatTime(timeLeft)}
          </div>
        )}
        
        {/* Визуальный эффект при завершении таймера */}
        {showVfx && (
          <div style={{
            position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
            animation: 'vfx-pulse 1s infinite',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            pointerEvents: 'none', zIndex: 10
          }}>
            <h2 style={{
              fontSize: 64, margin: 0,
              textShadow: '0 4px 20px rgba(0,0,0,0.8)',
              animation: 'vfx-bounce 0.5s infinite alternate',
            }}>
              ⏰
            </h2>
          </div>
        )}
      </div>
    </div>
  );
}
