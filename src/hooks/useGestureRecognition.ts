import { useEffect, useRef, useState, useCallback } from 'react';
import {
  GestureRecognizer,
  FilesetResolver,
  type GestureRecognizerResult,
  type NormalizedLandmark,
} from '@mediapipe/tasks-vision';

// ─── Публичные типы ─────────────────────────────────────────
export type GestureName =
  | 'None'
  | 'SwipeLeft'
  | 'SwipeRight'
  | 'Victory'
  | 'ThumbUp';

export interface GestureEvent {
  gesture: GestureName;
  timestamp: number;
}

export interface GestureErrorEvent {
  message: string;
  timestamp: number;
}

interface Props {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  onGesture: (e: GestureEvent) => void;
  onError: (e: GestureErrorEvent | null) => void;
  enabled?: boolean;
}

// ─── Вспомогательные функции ────────────────────────────────
/** Расстояние между двумя 2D-точками (нормализованными 0..1) */
function dist(a: NormalizedLandmark, b: NormalizedLandmark): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** Палец «согнут», если кончик ближе к запястью, чем сустав MCP */
function isFingerFolded(
  tip: NormalizedLandmark,
  mcp: NormalizedLandmark,
  wrist: NormalizedLandmark,
): boolean {
  return dist(tip, wrist) < dist(mcp, wrist);
}

// MediaPipe hand landmark indices
const WRIST = 0;
const INDEX_TIP = 8;
const INDEX_MCP = 5;
const MIDDLE_TIP = 12;
const MIDDLE_MCP = 9;
const RING_TIP = 16;
const RING_MCP = 13;
const PINKY_TIP = 20;
const PINKY_MCP = 17;

// Connections for drawing skeleton
const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],     // thumb
  [0, 5], [5, 6], [6, 7], [7, 8],     // index
  [0, 9], [9, 10], [10, 11], [11, 12], // middle
  [0, 13], [13, 14], [14, 15], [15, 16], // ring
  [0, 17], [17, 18], [18, 19], [19, 20], // pinky
  [5, 9], [9, 13], [13, 17],           // palm
];

// ─── Хук ────────────────────────────────────────────────────
export function useGestureRecognition({
  videoRef,
  canvasRef,
  onGesture,
  onError,
  enabled = true,
}: Props) {
  const [isLoading, setIsLoading] = useState(true);
  const recognizerRef = useRef<GestureRecognizer | null>(null);
  const rafRef = useRef<number>(0);
  const lastVideoTimeRef = useRef(-1);

  // Кулдаун, чтобы один жест не срабатывал 100 раз подряд
  const cooldownUntilRef = useRef(0);
  const COOLDOWN_MS = 1200;

  // История x-координаты запястья для детекции свайпа
  const swipeTrailRef = useRef<{ x: number; t: number }[]>([]);

  // Ссылки на последний callback (чтобы не пересоздавать замыкания)
  const onGestureRef = useRef(onGesture);
  onGestureRef.current = onGesture;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  // ─── Инициализация модели ──────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function init() {
      const vision = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm',
      );
      if (cancelled) return;

      const recognizer = await GestureRecognizer.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: '/gesture_recognizer.task',
          delegate: 'GPU',
        },
        runningMode: 'VIDEO',
        numHands: 1,
      });
      if (cancelled) return;

      recognizerRef.current = recognizer;
      setIsLoading(false);
    }

    init();
    return () => {
      cancelled = true;
    };
  }, []);

  // ─── Рендер-луп ───────────────────────────────────────────
  const tick = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const recognizer = recognizerRef.current;

    if (!video || !canvas || !recognizer || video.readyState < 2) {
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    // Подгоняем canvas под видео
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }

    const ctx = canvas.getContext('2d')!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Чтобы не вызывать recognizer дважды на одном кадре
    if (video.currentTime === lastVideoTimeRef.current) {
      rafRef.current = requestAnimationFrame(tick);
      return;
    }
    lastVideoTimeRef.current = video.currentTime;

    const now = performance.now();
    let results: GestureRecognizerResult;
    try {
      results = recognizer.recognizeForVideo(video, now);
    } catch {
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    // ─── Рисуем скелет руки ────────────────────────────────
    if (results.landmarks && results.landmarks.length > 0) {
      for (const lms of results.landmarks) {
        // Рисуем соединения
        ctx.strokeStyle = '#00FF88';
        ctx.lineWidth = 3;
        for (const [i, j] of HAND_CONNECTIONS) {
          const a = lms[i];
          const b = lms[j];
          ctx.beginPath();
          ctx.moveTo(a.x * canvas.width, a.y * canvas.height);
          ctx.lineTo(b.x * canvas.width, b.y * canvas.height);
          ctx.stroke();
        }
        // Рисуем точки
        for (const lm of lms) {
          ctx.fillStyle = '#FFFFFF';
          ctx.beginPath();
          ctx.arc(lm.x * canvas.width, lm.y * canvas.height, 5, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#00FF88';
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }
    }

    // ─── Логика распознавания жестов ────────────────────────
    const inCooldown = now < cooldownUntilRef.current;

    if (!results.gestures?.length || !results.landmarks?.length) {
      // Нет руки — сбрасываем свайп-трейл и ошибку
      swipeTrailRef.current = [];
      onErrorRef.current(null);
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    const categoryName = results.gestures[0][0].categoryName;
    const score = results.gestures[0][0].score;
    const lm = results.landmarks[0];

    // ---------- 1. Victory (Peace ✌️) → таймер ----------
    if (categoryName === 'Victory') {
      const fingerDist = dist(lm[INDEX_TIP], lm[MIDDLE_TIP]);
      if (fingerDist < 0.045) {
        // ОШИБКА: пальцы слишком близко
        onErrorRef.current({
          message: 'Пальцы слиплись! Раздвинь указательный и средний палец шире, чтобы запустить таймер ✌️',
          timestamp: now,
        });
      } else if (!inCooldown) {
        // УСПЕХ
        onErrorRef.current(null);
        cooldownUntilRef.current = now + COOLDOWN_MS;
        onGestureRef.current({ gesture: 'Victory', timestamp: now });
      }
      swipeTrailRef.current = [];
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    // ---------- 2. Thumb_Up (Like 👍) → вычеркнуть ингредиент ----------
    if (categoryName === 'Thumb_Up') {
      // Проверяем, что остальные пальцы сжаты
      const ringFolded = isFingerFolded(lm[RING_TIP], lm[RING_MCP], lm[WRIST]);
      const pinkyFolded = isFingerFolded(lm[PINKY_TIP], lm[PINKY_MCP], lm[WRIST]);
      const middleFolded = isFingerFolded(lm[MIDDLE_TIP], lm[MIDDLE_MCP], lm[WRIST]);

      if (!ringFolded || !pinkyFolded || !middleFolded) {
        onErrorRef.current({
          message: 'Сожми остальные пальцы плотнее в кулак, чтобы вычеркнуть ингредиент 👍',
          timestamp: now,
        });
      } else if (!inCooldown) {
        onErrorRef.current(null);
        cooldownUntilRef.current = now + COOLDOWN_MS;
        onGestureRef.current({ gesture: 'ThumbUp', timestamp: now });
      }
      swipeTrailRef.current = [];
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    // ---------- 3. Свайп (кастомная логика) ----------
    // Свайп определяем по Open_Palm + движению запястья по оси X
    if (categoryName === 'Open_Palm' || categoryName === 'Closed_Fist' || categoryName === 'None') {
      const wrist = lm[WRIST];
      const trail = swipeTrailRef.current;
      trail.push({ x: wrist.x, t: now });

      // Оставляем только последние 500ms
      while (trail.length > 0 && now - trail[0].t > 500) {
        trail.shift();
      }

      if (trail.length >= 5 && !inCooldown) {
        const dx = trail[trail.length - 1].x - trail[0].x;
        const absDx = Math.abs(dx);

        if (absDx >= 0.08 && absDx < 0.18) {
          // ОШИБКА: движение есть, но слишком маленькое
          onErrorRef.current({
            message: 'Взмах слишком короткий — сделай плавное и широкое движение от плеча, чтобы перелистнуть ✋',
            timestamp: now,
          });
        } else if (absDx >= 0.18) {
          // УСПЕХ: настоящий свайп
          onErrorRef.current(null);
          cooldownUntilRef.current = now + COOLDOWN_MS;
          // NB: координаты зеркальные (камера), dx > 0 на экране = влево
          const gesture: GestureName = dx > 0 ? 'SwipeLeft' : 'SwipeRight';
          onGestureRef.current({ gesture, timestamp: now });
          swipeTrailRef.current = [];
        }
      }
    } else {
      // Для остальных жестов (Pointing_Up и т.д.) ничего не делаем
      onErrorRef.current(null);
      swipeTrailRef.current = [];
    }

    rafRef.current = requestAnimationFrame(tick);
  }, [videoRef, canvasRef]);

  useEffect(() => {
    if (!isLoading && enabled) {
      rafRef.current = requestAnimationFrame(tick);
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [isLoading, enabled, tick]);

  return { isLoading };
}
