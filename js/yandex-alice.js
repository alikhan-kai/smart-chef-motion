(function () {
    const STORAGE_KEY = 'chefYandexAliceConnection';
    let pollTimer = null;
    let polling = false;

    function translated(key, fallback, values = {}) {
        let text = window.t ? window.t(key) : fallback;
        if (text === key) text = fallback;
        for (const [name, value] of Object.entries(values)) {
            text = text.replace(`{${name}}`, String(value));
        }
        return text;
    }

    function elements() {
        return {
            button: document.getElementById('alice-connect-btn'),
            status: document.getElementById('alice-status'),
            code: document.getElementById('alice-pairing-code')
        };
    }

    function readConnection() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
        } catch (_) {
            return null;
        }
    }

    function saveConnection(connection) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(connection));
    }

    function clearConnection() {
        localStorage.removeItem(STORAGE_KEY);
    }

    function setConnectedState(connected) {
        const ui = elements();
        if (!ui.button) return;
        ui.button.setAttribute('aria-pressed', connected ? 'true' : 'false');
        ui.button.textContent = connected
            ? translated('alice_connected', '✓ Алиса подключена')
            : translated('alice_connect', '🎙 Подключить Алису');
        ui.button.classList.toggle('bg-green-100', connected);
        ui.button.classList.toggle('text-green-700', connected);
        ui.button.classList.toggle('border-green-200', connected);
        ui.button.classList.toggle('bg-violet-50', !connected);
        ui.button.classList.toggle('text-violet-700', !connected);
        ui.button.classList.toggle('border-violet-100', !connected);
        ui.button.disabled = connected;
    }

    function setStatus(message, code) {
        const ui = elements();
        if (ui.status) ui.status.textContent = message;
        if (ui.code) {
            ui.code.textContent = code || '';
            ui.code.classList.toggle('hidden', !code);
        }
    }

    function applyVoiceCommand(command) {
        if (command.action === 'stop') {
            if (window.stopTimer) window.stopTimer();
            setStatus(translated('alice_stopped', 'Алиса остановила таймер'));
            return;
        }

        if (command.seconds !== null) {
            const expected = window.currentStepExpectedSeconds;
            if (expected !== null && expected !== undefined && command.seconds !== expected) {
                setStatus(translated(
                    'alice_wrong_time',
                    'Неверное время. Для этого шага нужно {seconds} сек.',
                    { seconds: expected }
                ));
                return;
            }
            if (window.activeTimerInterval || window.timerHasExpired) {
                window.stopTimer();
            }
            window.currentStepTimeLeft = command.seconds;
            const container = document.getElementById('step-timer-container');
            if (container) container.classList.remove('hidden');
            if (window.updateTimerDisplay) window.updateTimerDisplay(command.seconds);
        }
        if (window.startTimer) window.startTimer();
        setStatus(command.seconds === null
            ? translated('alice_started_step', 'Алиса запустила таймер шага')
            : translated(
                'alice_started_custom',
                'Алиса запустила таймер на {seconds} сек.',
                { seconds: command.seconds }
            ));
    }

    async function poll() {
        if (polling) return;
        const connection = readConnection();
        if (!connection || !connection.token) return;
        polling = true;
        try {
            const params = new URLSearchParams({
                connection_token: connection.token,
                after: String(connection.lastCommandId || 0)
            });
            const response = await fetch(
                `${window.CHEF_API_BASE}/integrations/yandex-alice/commands?${params}`
            );
            if (response.status === 404) {
                clearConnection();
                setConnectedState(false);
                setStatus(translated(
                    'alice_expired',
                    'Подключение устарело — подключите Алису снова'
                ));
                return;
            }
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const ui = elements();
            const wasConnected = ui.button?.getAttribute('aria-pressed') === 'true';
            if (data.paired) {
                setConnectedState(true);
                if (!wasConnected) {
                    setStatus(translated(
                        'alice_active',
                        'Алиса подключена — голосовое управление активно'
                    ));
                }
            }
            for (const command of data.commands || []) {
                applyVoiceCommand(command);
                connection.lastCommandId = command.id;
            }
            saveConnection(connection);
        } catch (error) {
            console.error('Yandex Alice polling error:', error);
        } finally {
            polling = false;
        }
    }

    function startPolling() {
        if (pollTimer) return;
        poll();
        pollTimer = window.setInterval(poll, 1000);
    }

    function stopPolling() {
        if (pollTimer) window.clearInterval(pollTimer);
        pollTimer = null;
    }

    async function syncExpectedTimer() {
        const connection = readConnection();
        if (!connection || !connection.token) return;
        try {
            const response = await fetch(
                `${window.CHEF_API_BASE}/integrations/yandex-alice/expected-timer`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        connection_token: connection.token,
                        seconds: window.currentStepExpectedSeconds ?? null
                    })
                }
            );
            if (response.status === 404) {
                clearConnection();
                setConnectedState(false);
            }
        } catch (error) {
            console.error('Yandex Alice timer sync error:', error);
        }
    }

    async function connect() {
        const ui = elements();
        if (ui.button) ui.button.disabled = true;
        setStatus(translated('alice_creating', 'Создаю код подключения…'));
        try {
            const response = await fetch(
                `${window.CHEF_API_BASE}/integrations/yandex-alice/pairings`,
                { method: 'POST' }
            );
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const pairing = await response.json();
            saveConnection({ token: pairing.connection_token, lastCommandId: 0 });
            setConnectedState(false);
            setStatus(
                translated(
                    'alice_pair_steps',
                    '1. Скажите: «Алиса, запусти навык Умный шеф». 2. Назовите код:'
                ),
                pairing.code
            );
            await syncExpectedTimer();
            startPolling();
        } catch (error) {
            console.error('Yandex Alice pairing error:', error);
            setStatus(translated(
                'alice_backend_error',
                'Не удалось подключиться. Проверьте backend.'
            ));
        } finally {
            if (ui.button) ui.button.disabled = false;
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const ui = elements();
        if (ui.button) ui.button.addEventListener('click', connect);
        if (readConnection()) {
            setStatus(translated(
                'alice_checking',
                'Проверяю подключение Алисы…'
            ));
        }
    });

    function refreshLanguage() {
        const connected = elements().button?.getAttribute('aria-pressed') === 'true';
        setConnectedState(connected);
    }

    window.YandexAlice = {
        startPolling,
        stopPolling,
        connect,
        syncExpectedTimer,
        refreshLanguage
    };
})();
