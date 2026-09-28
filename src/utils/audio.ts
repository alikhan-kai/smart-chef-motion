// Инициализируем AudioContext только один раз при первом вызове
let audioCtx: AudioContext | null = null;

function getAudioContext() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

export function playGestureSound(gesture: string) {
  const ctx = getAudioContext();
  const t = ctx.currentTime;

  // Утилита для создания приятных "колокольчиков"
  const playSine = (freq: number, start: number, duration: number, vol = 0.1) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(vol, start + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
    osc.start(start);
    osc.stop(start + duration);
  };

  // Короткий "щелчок" (для прокрутки ползунка)
  const playTick = () => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'triangle';
    osc.frequency.value = 800;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.05, t + 0.005);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.05);
    osc.start(t);
    osc.stop(t + 0.05);
  };

  if (gesture === 'ThumbUp') {
    playSine(1318.51, t, 0.4); // Высокий колокольчик (Ми 6)
  } else if (gesture === 'ThumbDown') {
    playSine(1046.50, t, 0.4); // Низкий колокольчик (До 6)
  } else if (gesture === 'Peace') {
    // Двойной быстрый звук (активация)
    playSine(880, t, 0.1, 0.05);
    playSine(1108.73, t + 0.1, 0.3, 0.05); 
  } else if (gesture === 'Stop') {
    // Глухой, обрывающийся звук (отмена/пауза)
    playSine(440, t, 0.2, 0.1); 
  } else if (gesture === 'OK') {
    // Радостный мажорный аккорд (успех/закрытие)
    playSine(1046.50, t, 0.15, 0.05);
    playSine(1318.51, t + 0.15, 0.15, 0.05);
    playSine(1567.98, t + 0.3, 0.4, 0.05);
  } else if (gesture === 'PointUpTick') {
    playTick();
  }
}

let alarmOscillators: { osc: OscillatorNode; gain: GainNode }[] = [];

export function playAlarm() {
  stopAlarm(); // на случай если уже играет
  const ctx = getAudioContext();

  // Создаем 5 коротких писков подряд
  for (let i = 0; i < 15; i++) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.type = 'square';
    osc.frequency.value = 880; // Нота Ля

    const startTime = ctx.currentTime + i * 0.4;
    gain.gain.setValueAtTime(0, startTime);
    gain.gain.linearRampToValueAtTime(0.1, startTime + 0.05);
    gain.gain.linearRampToValueAtTime(0, startTime + 0.2);

    osc.start(startTime);
    osc.stop(startTime + 0.2);
    
    alarmOscillators.push({ osc, gain });
  }
}

export function stopAlarm() {
  const ctx = getAudioContext();
  alarmOscillators.forEach(({ osc, gain }) => {
    try {
      gain.gain.cancelScheduledValues(ctx.currentTime);
      gain.gain.setValueAtTime(0, ctx.currentTime);
      osc.stop(ctx.currentTime);
    } catch (e) {
      // Игнорируем ошибки остановки уже завершенных нот
    }
  });
  alarmOscillators = [];
}
