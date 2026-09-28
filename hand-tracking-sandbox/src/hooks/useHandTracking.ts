import { useEffect, useRef, useState, useCallback } from 'react';
import {
  HandLandmarker,
  FilesetResolver,
  type NormalizedLandmark,
} from '@mediapipe/tasks-vision';

// ═══════════════════════════════════════════════════════════
//  Публичные типы
// ═══════════════════════════════════════════════════════════
export type GestureName = 'ThumbUp' | 'ThumbDown' | 'Peace' | 'Stop' | 'OK' | 'PointUp';

export interface GestureEvent {
  gesture: GestureName;
  hand: 'Left' | 'Right';
  timestamp: number;
  /** Для PointUp: Y-позиция указательного пальца (0 = верх, 1 = низ) */
  value?: number;
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
  /** Жесты, у которых НЕТ кулдауна (например PointUp для слайдера) */
  noCooldownGestures?: GestureName[];
}

// ═══════════════════════════════════════════════════════════
//  Landmark индексы
// ═══════════════════════════════════════════════════════════
const WRIST = 0;
const THUMB_MCP = 2;
const THUMB_IP = 3;
const THUMB_TIP = 4;
const INDEX_MCP = 5;
const INDEX_PIP = 6;
const INDEX_TIP = 8;
const MIDDLE_MCP = 9;
const MIDDLE_PIP = 10;
const MIDDLE_TIP = 12;
const RING_MCP = 13;
const RING_PIP = 14;
const RING_TIP = 16;
const PINKY_MCP = 17;
const PINKY_PIP = 18;
const PINKY_TIP = 20;

const CONNECTIONS: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
];

// ═══════════════════════════════════════════════════════════
//  Утилиты
// ═══════════════════════════════════════════════════════════
function dist(a: NormalizedLandmark, b: NormalizedLandmark): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function isExtended(
  tip: NormalizedLandmark,
  pip: NormalizedLandmark,
  _mcp: NormalizedLandmark,
  wrist: NormalizedLandmark,
): boolean {
  return dist(tip, wrist) > dist(pip, wrist);
}

// ═══════════════════════════════════════════════════════════
//  Распознавание жеста
// ═══════════════════════════════════════════════════════════
interface Result {
  gesture: GestureName | null;
  error: string | null;
  value?: number;
}

function recognizeGesture(lm: NormalizedLandmark[]): Result {
  const w = lm[WRIST];

  const indexExt = isExtended(lm[INDEX_TIP], lm[INDEX_PIP], lm[INDEX_MCP], w);
  const middleExt = isExtended(lm[MIDDLE_TIP], lm[MIDDLE_PIP], lm[MIDDLE_MCP], w);
  const ringExt = isExtended(lm[RING_TIP], lm[RING_PIP], lm[RING_MCP], w);
  const pinkyExt = isExtended(lm[PINKY_TIP], lm[PINKY_PIP], lm[PINKY_MCP], w);

  // СТРОГАЯ проверка: большой палец должен не просто быть выше сустава, 
  // а быть вытянут вверх/вниз на значительное расстояние (> 0.06).
  const thumbUp = (lm[THUMB_MCP].y - lm[THUMB_TIP].y) > 0.06 && lm[THUMB_TIP].y < w.y;
  const thumbDown = (lm[THUMB_TIP].y - lm[THUMB_MCP].y) > 0.06 && lm[THUMB_TIP].y > w.y;

  const allFourCurled = !indexExt && !middleExt && !ringExt && !pinkyExt;
  const extCount = [indexExt, middleExt, ringExt, pinkyExt].filter(Boolean).length;

  // ─── 1. OK 👌: thumb tip + index tip close, middle+ring+pinky extended ───
  // СТРОГАЯ проверка: расстояние < 0.04 (пальцы плотно сомкнуты), указательный согнут в кольцо
  const thumbIndexDist = dist(lm[THUMB_TIP], lm[INDEX_TIP]);
  if (thumbIndexDist < 0.04 && !indexExt && middleExt && ringExt && pinkyExt) {
    return { gesture: 'OK', error: null };
  }
  
  // Подсказки для режима ошибок (если пальцы почти сомкнуты)
  if (thumbIndexDist < 0.06) {
    // Пальцы почти соединены, но остальные не выпрямлены
    const missing: string[] = [];
    if (!middleExt) missing.push('средний');
    if (!ringExt) missing.push('безымянный');
    if (!pinkyExt) missing.push('мизинец');
    if (missing.length > 0) {
      return { gesture: null, error: `Выпрями ${missing.join(' и ')} палец для жеста OK 👌` };
    }
    // Если остальные выпрямлены, но пальцы не дожаты (0.04 < dist < 0.06)
    if (middleExt && ringExt && pinkyExt) {
      return { gesture: null, error: 'Сомкни большой и указательный палец плотнее для OK 👌' };
    }
  }
  // Пальцы выпрямлены, но большой и указательный не соединены
  if (middleExt && ringExt && pinkyExt && !indexExt && thumbIndexDist >= 0.06) {
    return { gesture: null, error: 'Соедини большой и указательный палец в кольцо для OK 👌' };
  }

  // ─── 2. Stop ✋: все 5 разогнуты ───
  if (indexExt && middleExt && ringExt && pinkyExt && thumbUp) {
    return { gesture: 'Stop', error: null };
  }
  if (extCount >= 3 && !(indexExt && middleExt && ringExt && pinkyExt)) {
    const missing: string[] = [];
    if (!indexExt) missing.push('указательный');
    if (!middleExt) missing.push('средний');
    if (!ringExt) missing.push('безымянный');
    if (!pinkyExt) missing.push('мизинец');
    return { gesture: null, error: `Выпрями ${missing.join(' и ')} палец полностью для жеста Стоп ✋` };
  }
  if (indexExt && middleExt && ringExt && pinkyExt && !thumbUp) {
    return { gesture: null, error: 'Отведи большой палец в сторону — раскрой ладонь полностью ✋' };
  }

  // ─── 3. Peace ✌️: index + middle, rest curled ───
  if (indexExt && middleExt && !ringExt && !pinkyExt) {
    const fingerDist = dist(lm[INDEX_TIP], lm[MIDDLE_TIP]);
    if (fingerDist < 0.04) {
      return { gesture: null, error: 'Раздвинь указательный и средний палец шире для Peace ✌️' };
    }
    return { gesture: 'Peace', error: null };
  }
  // Почти Peace: index + middle, но ring или pinky тоже торчат
  if (indexExt && middleExt && (ringExt || pinkyExt)) {
    if (ringExt && pinkyExt) {
      return { gesture: null, error: 'Согни безымянный и мизинец — оставь только два пальца для Peace ✌️' };
    }
    if (ringExt) {
      return { gesture: null, error: 'Согни безымянный палец для чистого жеста Peace ✌️' };
    }
    // pinkyExt
    return { gesture: null, error: 'Согни мизинец для чистого жеста Peace ✌️' };
  }

  // ─── 4. PointUp ☝️: only index extended ───
  if (indexExt && !middleExt && !ringExt && !pinkyExt) {
    return { gesture: 'PointUp', error: null, value: lm[INDEX_TIP].y };
  }
  // Почти PointUp: index + ещё один палец
  if (indexExt && extCount === 2 && !middleExt) {
    return { gesture: null, error: 'Согни все пальцы кроме указательного для слайдера ☝️' };
  }

  // ─── 5. Thumb Up 👍 ───
  if (thumbUp && allFourCurled) {
    return { gesture: 'ThumbUp', error: null };
  }
  if (thumbUp && !allFourCurled && extCount <= 2) {
    const sticking: string[] = [];
    if (indexExt) sticking.push('указательный');
    if (middleExt) sticking.push('средний');
    if (ringExt) sticking.push('безымянный');
    if (pinkyExt) sticking.push('мизинец');
    return { gesture: null, error: `Согни ${sticking.join(' и ')} в кулак для жеста 👍` };
  }

  // ─── 6. Thumb Down 👎 ───
  if (thumbDown && allFourCurled) {
    return { gesture: 'ThumbDown', error: null };
  }
  if (thumbDown && !allFourCurled && extCount <= 2) {
    const sticking: string[] = [];
    if (indexExt) sticking.push('указательный');
    if (middleExt) sticking.push('средний');
    if (ringExt) sticking.push('безымянный');
    if (pinkyExt) sticking.push('мизинец');
    return { gesture: null, error: `Согни ${sticking.join(' и ')} в кулак для жеста 👎` };
  }

  return { gesture: null, error: null };
}

// ═══════════════════════════════════════════════════════════
//  Хук
// ═══════════════════════════════════════════════════════════
export function useHandTracking({
  videoRef,
  canvasRef,
  onGesture,
  onError,
  noCooldownGestures = [],
}: Props) {
  const [isLoading, setIsLoading] = useState(true);
  const landmarkerRef = useRef<HandLandmarker | null>(null);
  const rafRef = useRef(0);
  const lastTimeRef = useRef(-1);
  const cooldownUntilRef = useRef(0);

  // Буфер уверенности: жест должен держаться N кадров подряд
  const pendingGestureRef = useRef<GestureName | null>(null);
  const pendingGestureCountRef = useRef(0);

  const onGestureRef = useRef(onGesture);
  onGestureRef.current = onGesture;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const noCooldownRef = useRef(noCooldownGestures);
  noCooldownRef.current = noCooldownGestures;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const vision = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm',
      );
      if (cancelled) return;
      const landmarker = await HandLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: '/hand_landmarker.task', delegate: 'GPU' },
        runningMode: 'VIDEO',
        numHands: 2,
        minHandDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });
      if (cancelled) return;
      landmarkerRef.current = landmarker;
      setIsLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const tick = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const landmarker = landmarkerRef.current;

    if (!video || !canvas || !landmarker || video.readyState < 2) {
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    const ctx = canvas.getContext('2d')!;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (video.currentTime === lastTimeRef.current) {
      rafRef.current = requestAnimationFrame(tick);
      return;
    }
    lastTimeRef.current = video.currentTime;

    const now = performance.now();
    let results;
    try {
      results = landmarker.detectForVideo(video, now);
    } catch {
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    // Рисуем скелеты
    const colors = ['#00FF88', '#FF6B6B'];
    if (results.landmarks) {
      results.landmarks.forEach((lms, hi) => {
        const c = colors[hi % 2];
        ctx.strokeStyle = c;
        ctx.lineWidth = 3;
        for (const [i, j] of CONNECTIONS) {
          ctx.beginPath();
          ctx.moveTo(lms[i].x * canvas.width, lms[i].y * canvas.height);
          ctx.lineTo(lms[j].x * canvas.width, lms[j].y * canvas.height);
          ctx.stroke();
        }
        for (const l of lms) {
          ctx.fillStyle = '#fff';
          ctx.beginPath();
          ctx.arc(l.x * canvas.width, l.y * canvas.height, 4, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = c;
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      });
    }

    // Распознавание
    const inCooldown = now < cooldownUntilRef.current;

    if (!results.landmarks?.length) {
      onErrorRef.current(null);
      pendingGestureRef.current = null;
      pendingGestureCountRef.current = 0;
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    let found = false;
    for (let h = 0; h < results.landmarks.length; h++) {
      const lm = results.landmarks[h];
      const hand = (results.handednesses?.[h]?.[0]?.categoryName ?? 'Right') as 'Left' | 'Right';
      const { gesture, error, value } = recognizeGesture(lm);

      if (error) {
        onErrorRef.current({ message: error, timestamp: now });
        found = true;
        pendingGestureRef.current = null;
        pendingGestureCountRef.current = 0;
        break;
      }

      if (gesture) {
        const skipCooldown = noCooldownRef.current.includes(gesture);
        // Требуемое количество кадров подряд:
        // Для слайдера (PointUp) 4 кадра, для остальных 15 кадров (~0.5 сек стабильного удержания)
        const requiredFrames = skipCooldown ? 4 : 15;

        if (pendingGestureRef.current === gesture) {
          pendingGestureCountRef.current++;
        } else {
          pendingGestureRef.current = gesture;
          pendingGestureCountRef.current = 1;
        }

        // Логика срабатывания:
        // Слайдер (skipCooldown=true) срабатывает каждый кадр после достижения requiredFrames.
        // Обычные жесты (ThumbUp, Peace) срабатывают РОВНО 1 РАЗ. Чтобы сделать жест снова, 
        // нужно убрать руку (сбросить счетчик) и показать жест заново. Это блокирует дабл-клики.
        const shouldFire = skipCooldown 
          ? pendingGestureCountRef.current >= requiredFrames 
          : pendingGestureCountRef.current === requiredFrames;

        if (shouldFire) {
          if (skipCooldown || !inCooldown) {
            onErrorRef.current(null);
            if (!skipCooldown) cooldownUntilRef.current = now + 1500;
            onGestureRef.current({ gesture, hand, timestamp: now, value });
          }
        }
        found = true;
        break;
      }
    }

    if (!found) {
      onErrorRef.current(null);
      pendingGestureRef.current = null;
      pendingGestureCountRef.current = 0;
    }
    rafRef.current = requestAnimationFrame(tick);
  }, [videoRef, canvasRef]);

  useEffect(() => {
    if (!isLoading) rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [isLoading, tick]);

  return { isLoading };
}
