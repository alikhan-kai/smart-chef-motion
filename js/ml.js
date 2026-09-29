import { GestureRecognizer, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/vision_bundle.mjs";

let recognizer = null;
let lastVideoTime = -1;
let cooldownUntil = 0;
const COOLDOWN_MS = 1500; // Немного увеличим задержку от случайных срабатываний

// MediaPipe константы
const WRIST = 0;
const INDEX_TIP = 8;
const MIDDLE_TIP = 12;
const RING_TIP = 16;
const RING_MCP = 13;
const PINKY_TIP = 20;
const PINKY_MCP = 17;
const MIDDLE_MCP = 9;

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
];

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function isFingerFolded(tip, mcp, wrist) {
  return dist(tip, wrist) < dist(mcp, wrist);
}

export async function initML() {
    const video = document.getElementById('webcam');
    const canvas = document.getElementById('output_canvas');
    const debugEl = document.getElementById('gesture-debug');

    if (!video || !canvas) return;

    debugEl.innerText = window.translations[localStorage.getItem('chefLang') || 'ru']['ml_loading'] || 'Загрузка ИИ (MediaPipe)...';

    // 1. Загружаем модель (FilesetResolver)
    const vision = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm"
    );

    recognizer = await GestureRecognizer.createFromOptions(vision, {
        baseOptions: {
            // Подключаем стандартную модель жестов Google
            modelAssetPath: "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task",
            delegate: "GPU"
        },
        runningMode: "VIDEO",
        numHands: 1
    });

    debugEl.innerText = window.translations[localStorage.getItem('chefLang') || 'ru']['ml_camera_starting'] || 'Запуск камеры...';

    // 2. Включаем веб-камеру
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        video.srcObject = stream;
        video.addEventListener("loadeddata", () => {
            debugEl.innerText = "Готов к жестам!";
            predictWebcam(video, canvas, debugEl);
        });
    } catch (err) {
        console.error(err);
        debugEl.innerText = window.translations[localStorage.getItem('chefLang') || 'ru']['ml_camera_error'] || 'Ошибка доступа к камере';
        debugEl.classList.add("text-red-500");
    }
}

function predictWebcam(video, canvas, debugEl) {
    if (!recognizer) return;

    const ctx = canvas.getContext("2d");
    
    // Подгоняем канвас
    if (canvas.width !== video.videoWidth) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
    }

    if (video.currentTime !== lastVideoTime) {
        lastVideoTime = video.currentTime;
        
        const now = performance.now();
        const results = recognizer.recognizeForVideo(video, now);

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const inCooldown = now < cooldownUntil;

        if (results.landmarks && results.landmarks.length > 0) {
            // Рисуем скелет
            for (const lms of results.landmarks) {
                ctx.strokeStyle = '#f97316'; // Оранжевый (claude-accent)
                ctx.lineWidth = 3;
                for (const [i, j] of HAND_CONNECTIONS) {
                    ctx.beginPath();
                    ctx.moveTo(lms[i].x * canvas.width, lms[i].y * canvas.height);
                    ctx.lineTo(lms[j].x * canvas.width, lms[j].y * canvas.height);
                    ctx.stroke();
                }
                for (const lm of lms) {
                    ctx.fillStyle = '#FFFFFF';
                    ctx.beginPath();
                    ctx.arc(lm.x * canvas.width, lm.y * canvas.height, 5, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = '#f97316';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            }

            // Логика распознавания (по коду друга + новые жесты)
            if (results.gestures.length > 0) {
                const categoryName = results.gestures[0][0].categoryName;
                const lm = results.landmarks[0];

                if (categoryName === 'Thumb_Up') {
                    // Лайк -> Следующий шаг
                    const ringFolded = isFingerFolded(lm[RING_TIP], lm[RING_MCP], lm[WRIST]);
                    const pinkyFolded = isFingerFolded(lm[PINKY_TIP], lm[PINKY_MCP], lm[WRIST]);
                    const middleFolded = isFingerFolded(lm[MIDDLE_TIP], lm[MIDDLE_MCP], lm[WRIST]);

                    if (!ringFolded || !pinkyFolded || !middleFolded) {
                        showError(debugEl, 'Сожмите остальные пальцы в кулак, чтобы распознать жест "Лайк"');
                    } else if (!inCooldown) {
                        fireGesture(debugEl, window.translations[localStorage.getItem('chefLang') || 'ru']['ml_gesture_like'] || '👍 Лайк (Вперед)', () => window.nextStep(), now);
                    }
                } 
                else if (categoryName === 'Thumb_Down') {
                    // Дизлайк -> Предыдущий шаг
                    if (!inCooldown) {
                        fireGesture(debugEl, window.translations[localStorage.getItem('chefLang') || 'ru']['ml_gesture_dislike'] || '👎 Дизлайк (Назад)', () => window.prevStep(), now);
                    }
                }
                else if (categoryName === 'Victory') {
                    // Жест Два пальца -> Таймер
                    const fingerDist = dist(lm[INDEX_TIP], lm[MIDDLE_TIP]);
                    if (fingerDist < 0.045) {
                        showError(debugEl, 'Пальцы слишком близко! Раздвиньте указательный и средний пальцы шире, чтобы распознать жест "Peace"');
                    } else if (!inCooldown) {
                        fireGesture(debugEl, '✌️ Таймер (Peace)', () => {
                            if (window.startTimer) window.startTimer();
                        }, now);
                    }
                }
                else if (categoryName === 'Open_Palm') {
                    if (!inCooldown) {
                        fireGesture(debugEl, '✋ Пауза (Ладонь)', () => {
                            if (window.stopTimer) window.stopTimer();
                        }, now);
                    }
                }
                else if (categoryName === 'None' || categoryName === 'Closed_Fist') {
                    if (!inCooldown) {
                        showError(debugEl, 'Жест непонятный! Покажите жест четче (Лайк, Дизлайк или Peace).');
                    }
                }
            } else {
                if (!inCooldown) resetDebug(debugEl);
            }
        } else {
            if (!inCooldown) resetDebug(debugEl);
        }
    }

    requestAnimationFrame(() => predictWebcam(video, canvas, debugEl));
}

let errorTimeout;
function showError(el, msg) {
    el.innerText = msg;
    el.className = "font-bold text-orange-500 text-sm mt-2 transition-all";
    clearTimeout(errorTimeout);
    errorTimeout = setTimeout(() => resetDebug(el), 2000);
}

function fireGesture(el, name, actionFn, now) {
    cooldownUntil = now + COOLDOWN_MS;
    el.innerText = name;
    el.className = "font-bold text-green-600 text-xl transition-all scale-110 inline-block";
    
    // Выполняем UI экшен
    if (typeof actionFn === 'function') actionFn();
    
    setTimeout(() => {
        if (performance.now() >= cooldownUntil) {
            resetDebug(el);
        }
    }, COOLDOWN_MS);
}

function resetDebug(el) {
    el.innerText = window.translations[localStorage.getItem('chefLang') || 'ru']['gesture_waiting'] || 'Ожидание жеста...';
    el.className = "font-semibold text-gray-400 text-lg transition-all";
}
