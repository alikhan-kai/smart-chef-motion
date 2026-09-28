const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playTone(freq, type, duration, vol=0.1) {
    if(audioCtx.state === 'suspended') audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    
    gain.gain.setValueAtTime(vol, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration);
    
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
}

function playPageTurnSound() {
    if(audioCtx.state === 'suspended') audioCtx.resume();
    const bufferSize = audioCtx.sampleRate * 0.15; // 150ms
    const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
        data[i] = Math.random() * 2 - 1;
    }
    
    const noise = audioCtx.createBufferSource();
    noise.buffer = buffer;
    
    const filter = audioCtx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 1500;
    
    const gain = audioCtx.createGain();
    gain.gain.setValueAtTime(0.8, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.15);
    
    noise.connect(filter);
    filter.connect(gain);
    gain.connect(audioCtx.destination);
    
    noise.start();
}

function playTimerStartSound() {
    playTone(660, 'sine', 0.2, 0.2);
    setTimeout(() => playTone(880, 'sine', 0.4, 0.2), 150);
}

function playTimerStopSound() {
    playTone(440, 'sine', 0.2, 0.2);
    setTimeout(() => playTone(330, 'sine', 0.4, 0.2), 150);
}

function playSuccessSound() {
    // Красивый аккорд (C major arpeggio)
    const notes = [261.63, 329.63, 392.00, 523.25];
    notes.forEach((freq, i) => {
        setTimeout(() => {
            playTone(freq, 'triangle', 1.5, 0.3);
            playTone(freq * 1.01, 'sine', 1.5, 0.1); // chorus effect
        }, i * 120);
    });
}

window.AppAudio = {
    pageTurn: playPageTurnSound,
    timerStart: playTimerStartSound,
    timerStop: playTimerStopSound,
    success: playSuccessSound
};
