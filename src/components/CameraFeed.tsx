import { useEffect, useRef, useState } from 'react';
import type { GestureEvent, GestureErrorEvent } from '../hooks/useHandTracking';
import { useHandTracking } from '../hooks/useHandTracking';

interface Props {
  onGesture: (e: GestureEvent) => void;
  onError: (e: GestureErrorEvent | null) => void;
}

export function CameraFeed({ onGesture, onError }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState('Запускаю камеру...');

  const { isLoading } = useHandTracking({
    videoRef,
    canvasRef,
    onGesture,
    onError,
    noCooldownGestures: ['PointUp'], // слайдер без задержки
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

  return (
    <div>
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
      </div>
    </div>
  );
}
