// Глобальный массив для шагов рецепта
window.mockRecipeData = [
    {
        title: "ИИ не загрузился",
        desc: "Пожалуйста, подождите или проверьте сервер",
        timer: null
    }
];

// Сохраняем ID чата для поддержания контекста (чтобы ИИ не страдал амнезией)
window.currentChatId = null;

function adjustTextareaHeight(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 128) + 'px';
}

document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('chat-input');
    const chatForm = document.getElementById('chat-form');

    if (chatInput) {
        chatInput.addEventListener('input', () => adjustTextareaHeight(chatInput));
        
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (chatInput.value.trim() !== '') {
                    chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                }
            }
        });
    }

    if (chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = chatInput.value.trim();
            if (!text) return; 
            
            chatInput.value = '';
            chatInput.disabled = true;
            document.getElementById('chat-submit-btn').disabled = true;
            adjustTextareaHeight(chatInput);

            appendMessage(text, 'user');

            const loadingId = 'loading-' + Date.now();
            appendMessage(
                `<div id="${loadingId}" class="flex items-center space-x-2 text-gray-500 italic">
                    <svg class="animate-spin h-5 w-5 text-claude-accent" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> 
                    <span>ИИ придумывает рецепт...</span>
                </div>`, 
                'ai', 
                true
            );

            try {
                if (!window.currentChatId) {
                    // 1. Первый запрос (Начинаем новый чат)
                    const response = await fetch('http://localhost:8000/chats', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-User-Id': localStorage.getItem('chefId') || 'test-user'
                        },
                        body: JSON.stringify({ prompt: text })
                    });
                    
                    removeLoading(loadingId);
                    await checkError(response);
                    
                    const data = await response.json();
                    window.currentChatId = data.chat_id; // Запоминаем ID!
                    
                    renderRecipeCard(data.recipe);
                } else {
                    // 2. Последующие запросы (Общаемся в текущем чате, ИИ помнит контекст)
                    const response = await fetch(`http://localhost:8000/chats/${window.currentChatId}/messages`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-User-Id': localStorage.getItem('chefId') || 'test-user'
                        },
                        body: JSON.stringify({ text: text })
                    });
                    
                    removeLoading(loadingId);
                    await checkError(response);
                    
                    const data = await response.json();
                    
                    // Если ИИ просто отвечает на вопрос (не меняя рецепт)
                    if (data.intent === 'answer') {
                        appendMessage(data.answer_text, 'ai', false);
                    } 
                    // Если ИИ понял, что нужно переделать рецепт (заменить ингредиент и т.д.)
                    else if (data.intent === 'revise') {
                        if (data.answer_text) {
                            appendMessage(data.answer_text, 'ai', false);
                        }
                        renderRecipeCard(data.recipe);
                    }
                }

            } catch (err) {
                console.error(err);
                removeLoading(loadingId);

                const msg = err.message || '';
                const isSystemError = msg.includes('Patch') || msg.includes('unknown') || msg.includes('Failed') || msg.includes('fetch') || msg.includes('network') || msg.includes('Failed to fetch');
                if (isSystemError) {
                    appendMessage(`<span class="text-red-500">Системная ошибка: ${msg}</span>`, 'ai', true);
                } else {
                    appendMessage(msg, 'ai', false);
                }

            }

            chatInput.disabled = false;
            document.getElementById('chat-submit-btn').disabled = false;
            chatInput.focus();
        });
    }
});

function removeLoading(loadingId) {
    const el = document.getElementById(loadingId);
    if (el && el.parentElement) el.parentElement.remove();
}

async function checkError(response) {
    if (!response.ok) {
        let errMsg = 'Ошибка сервера (убедитесь, что backend запущен)';
        try {
            const errData = await response.json();
            if (errData.detail) {
                // Избегаем вывода [object Object] при ошибках валидации FastAPI
                errMsg = Array.isArray(errData.detail) ? JSON.stringify(errData.detail) : errData.detail;
            }
        } catch(ex) {}
        throw new Error(errMsg);
    }
}

// Рендер карточки рецепта
window.buildMockRecipeData = function(recipe) {
    const steps = (recipe.steps || []).map((step) => {
                        let placeStr = step.place ? step.place.replace(/_/g, ' ') : '';
        if (placeStr) placeStr = placeStr.charAt(0).toUpperCase() + placeStr.slice(1);
        let title = step.header ? step.header : (placeStr ? `Шаг ${step.step_number}: ${placeStr}` : `Шаг ${step.step_number}`);
        return {
            title: title,
            desc: step.action,
            timer: step.time_minutes ? Math.round(step.time_minutes * 60) : null
        };
    });
    return steps.length > 0 ? steps : [{ title: "Пустой рецепт", desc: "Нет шагов.", timer: null }];
};

function renderRecipeCard(recipe) {
    if (!recipe) return;

    // Перезаписываем страницы книги новыми шагами
    window.mockRecipeData = window.buildMockRecipeData(recipe);

    // Ингредиенты
    let ingredientsHtml = '<div class="mt-3 mb-4"><p class="font-semibold text-gray-800 mb-2">🛒 Ингредиенты:</p><ul class="list-disc pl-5 text-sm text-gray-700 space-y-1">';
    if (recipe.ingredients && recipe.ingredients.length > 0) {
        recipe.ingredients.forEach(ing => {
            const amount = ing.amount ? ing.amount + ' ' : '';
            const unit = ing.unit && ing.unit !== 'по вкусу' ? ing.unit + ' ' : '';
            const form = ing.form ? ' (' + ing.form + ')' : '';
            ingredientsHtml += `<li><b>${ing.name}</b> — ${amount}${unit}${form}</li>`;
        });
    } else {
        ingredientsHtml += `<li>Не указаны</li>`;
    }
    ingredientsHtml += '</ul></div>';

    // Формируем HTML
    const btnId = 'accept-recipe-btn-' + Date.now();
    const recipeHtml = `
        <div class="mb-3 font-serif font-bold text-lg text-claude-text">🍳 ${recipe.title || "Ваш рецепт"}</div>
        <div class="text-sm text-gray-700">
            <p>⏱ Время: ${recipe.total_time_minutes || '?'} мин | 👥 Порций: ${recipe.servings || '?'}</p>
        </div>
        ${ingredientsHtml}
        <div class="mb-4 text-xs italic opacity-80 text-gray-500">Сгенерировано нейросетью. Страниц (шагов) в книге: ${window.mockRecipeData.length}</div>
        <button id="${btnId}" class="bg-claude-accent hover:bg-claude-accentHover text-white px-6 py-2 rounded-lg font-medium transition w-full shadow-sm text-center">
            Готово (Принять рецепт)
        </button>
    `;
    
    appendMessage(recipeHtml, 'ai', true);
    
    // Биндим кнопку к функции старта
    setTimeout(() => {
        const btn = document.getElementById(btnId);
        if (btn) {
                        btn.addEventListener('click', async () => {
                if (window.currentChatId) {
                    try {
                        await fetch('http://localhost:8000/chats/' + window.currentChatId + '/confirm', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-User-Id': localStorage.getItem('chefId') || 'test-user'
                            },
                            body: JSON.stringify({})
                        });
                        
                        if (typeof supabaseClient !== 'undefined') {
                            let user_id = null;
                            try {
                                user_id = localStorage.getItem('chefId');
                            } catch(ex) {}
                            
                            await supabaseClient
                                .from('ai_requests')
                                .insert([{
                                    user_id: user_id,
                                    user_prompt: 'Confirmed Recipe: ' + (recipe.title || 'Untitled'),
                                    ai_response: recipe
                                }]);
                        }
                    } catch(e) { console.error('Confirm error:', e); }
                }
                startCooking();
            });
        }
    }, 50);
}

function appendMessage(text, sender, isHtml = false) {
    const chatEmptyState = document.getElementById('chat-empty-state');
    if (chatEmptyState) chatEmptyState.style.display = 'none';

    const messagesContainer = document.getElementById('chat-messages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `max-w-2xl w-full mx-auto mb-6 flex ${sender === 'user' ? 'justify-end' : 'justify-start'}`;
    
    const bubble = document.createElement('div');
    bubble.className = `p-5 rounded-2xl text-sm sm:text-base ${
        sender === 'user' 
            ? 'bg-gray-100 text-gray-800 rounded-tr-sm' 
            : 'bg-white border border-gray-200 text-gray-800 shadow-sm rounded-tl-sm w-full'
    }`;
    
    if (isHtml) {
        bubble.innerHTML = text;
    } else {
        bubble.innerText = text;
    }

    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

let currentStepIndex = 0;
    if (window.completedSteps) window.completedSteps.clear();

function startCooking() {
    const screenChat = document.getElementById('screen-chat');
    const screenCooking = document.getElementById('screen-cooking');
    
    screenChat.style.transition = 'opacity 0.5s ease';
    screenChat.style.opacity = '0';
    
    setTimeout(() => {
        screenChat.classList.add('hidden');
        screenCooking.classList.remove('hidden');

        requestAnimationFrame(() => {
            screenCooking.classList.remove('opacity-0');
            // endCooking() (below) sets this element's opacity via inline
            // style, not the 'opacity-0' class - removing the class alone
            // does nothing once an inline style is set (inline always wins
            // over a class), so a *second* cooking session stayed stuck at
            // opacity:0 (a black screen) even after unhiding. Set it back
            // explicitly here too.
            screenCooking.style.opacity = '1';
        });

        currentStepIndex = 0;
    if (window.completedSteps) window.completedSteps.clear();
        updateRecipeUI();

        import('./ml.js').then(module => {
            if (module.initML) module.initML();
        }).catch(err => {
            console.error("Ошибка загрузки ML модуля:", err);
        });

    }, 500);
}

window.endCooking = function() {
    const screenCooking = document.getElementById('screen-cooking');
    const screenChat = document.getElementById('screen-chat');

    if (window.stopTimer) window.stopTimer();

    // Stop the camera/gesture-recognizer session - without this, starting a
    // new recipe on top of a still-running one is what caused the page to
    // glitch and show nothing (see js/ml.js's stopML()).
    import('./ml.js').then(module => {
        if (module.stopML) module.stopML();
    }).catch(err => {
        console.error("Ошибка остановки ML модуля:", err);
    });

    screenCooking.style.transition = 'opacity 0.5s ease';
    screenCooking.style.opacity = '0';
    
    setTimeout(() => {
        screenCooking.classList.add('hidden');
        screenChat.classList.remove('hidden');
        
        // Показываем экран чата плавно
        screenChat.style.transition = 'opacity 0.5s ease';
        screenChat.style.opacity = '0';
        void screenChat.offsetWidth;
        screenChat.style.opacity = '1';
        
        // Очищаем историю чата (возврат на главную)
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.querySelectorAll('.flex.w-full.mb-6').forEach(m => m.remove());
        }
        
        const chatEmptyState = document.getElementById('chat-empty-state');
        if (chatEmptyState) {
            chatEmptyState.style.display = 'block';
            chatEmptyState.style.opacity = '1';
            chatEmptyState.style.transform = 'scale(1)';
        }
        
        window.currentChatId = null;
        
        // Сброс страницы рецепта на первую
        if (typeof currentStepIndex !== 'undefined') currentStepIndex = 0;
    if (window.completedSteps) window.completedSteps.clear();
        const pageContent = document.getElementById('recipe-page-content');
        if (pageContent) {
            pageContent.style.transform = 'none';
            pageContent.style.opacity = '1';
        }
    }, 500);
}

function updateRecipeUI() {
    const step = window.mockRecipeData[currentStepIndex];
    
    const lang = localStorage.getItem('chefLang') || 'ru';
    const t = window.translations ? (window.translations[lang] || window.translations['ru']) : { step_word: "Шаг", out_of: "из" };
    
    document.getElementById('step-counter').innerText = `${t.step_word} ${currentStepIndex + 1} ${t.out_of} ${window.mockRecipeData.length}`;
    document.getElementById('step-title').innerText = step.title;
    document.getElementById('step-desc').innerText = step.desc;
    
    const progressPercent = ((currentStepIndex + 1) / window.mockRecipeData.length) * 100;
    document.getElementById('recipe-progress').style.width = `${progressPercent}%`;

    const timerContainer = document.getElementById('step-timer-container');
    
    if (window.activeTimerInterval) {
        clearInterval(window.activeTimerInterval);
        window.activeTimerInterval = null;
    }

    if (step.timer) {
        timerContainer.classList.remove('hidden');
        window.currentStepTimeLeft = step.timer;
        updateTimerDisplay(window.currentStepTimeLeft);
    } else {
        timerContainer.classList.add('hidden');
        window.currentStepTimeLeft = 0;
    }
}

function updateTimerDisplay(secondsTotal) {
    const timerDisplay = document.getElementById('step-timer-display');
    const minutes = Math.floor(secondsTotal / 60);
    const seconds = secondsTotal % 60;
    timerDisplay.innerText = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
}

window.startTimer = function() {
    if (window.AppAudio) window.AppAudio.timerStart();
    if (!window.currentStepTimeLeft || window.activeTimerInterval) return;
    
    const timerContainer = document.getElementById('step-timer-container').querySelector('div');
    timerContainer.classList.add('border-green-500', 'shadow-[6px_6px_0_#22c55e]'); 
    timerContainer.classList.remove('border-[#8B7355]', 'shadow-[6px_6px_0_#8B7355]');

    window.activeTimerInterval = setInterval(() => {
        if (window.currentStepTimeLeft > 0) {
            window.currentStepTimeLeft--;
            updateTimerDisplay(window.currentStepTimeLeft);
        } else {
            clearInterval(window.activeTimerInterval);
            window.activeTimerInterval = null;
            timerContainer.classList.remove('border-green-500', 'shadow-[6px_6px_0_#22c55e]');
            timerContainer.classList.add('border-[#8B7355]', 'shadow-[6px_6px_0_#8B7355]');
            alert("⏰ Время вышло!");
        }
    }, 1000);
}

// XP awarded once per completed recipe step.
const XP_PER_STEP = 20;

window.nextStep = function() {
    if (window.AppAudio) window.AppAudio.pageTurn();
    if (currentStepIndex < window.mockRecipeData.length - 1) {
        if (window.stopTimer) window.stopTimer();
        
        if (!window.completedSteps.has(currentStepIndex)) {
            window.completedSteps.add(currentStepIndex);
            if (window.addXP) window.addXP(XP_PER_STEP);
        }
        
        currentStepIndex++;
        
        const pageContent = document.getElementById('recipe-page-content');
        pageContent.style.animation = 'turnPageNextOut 0.4s cubic-bezier(0.4, 0.0, 0.2, 1) forwards';
        
        setTimeout(() => {
            updateRecipeUI();
            pageContent.style.animation = 'turnPageNextIn 0.4s cubic-bezier(0.4, 0.0, 0.2, 1) forwards';
        }, 400);
    } else {
        if (!window.completedSteps.has(currentStepIndex)) {
            window.completedSteps.add(currentStepIndex);
            if (window.addXP) window.addXP(XP_PER_STEP);
        }
        if (window.finishRecipe) window.finishRecipe();
    }
}

window.prevStep = function() {
    if (window.AppAudio) window.AppAudio.pageTurn();
    if (currentStepIndex > 0) {
        currentStepIndex--;
        
        const pageContent = document.getElementById('recipe-page-content');
        pageContent.style.animation = 'turnPagePrevOut 0.4s cubic-bezier(0.4, 0.0, 0.2, 1) forwards';
        
        setTimeout(() => {
            updateRecipeUI();
            pageContent.style.animation = 'turnPagePrevIn 0.4s cubic-bezier(0.4, 0.0, 0.2, 1) forwards';
        }, 400);
    }
}

window.updateGestureDebug = function(text) {
    const debugEl = document.getElementById('gesture-debug');
    if (debugEl) debugEl.innerText = text;
}

window.stopTimer = function() {
    if (window.AppAudio) window.AppAudio.timerStop();
    if (window.activeTimerInterval) {
        clearInterval(window.activeTimerInterval);
        window.activeTimerInterval = null;
        
        const timerContainer = document.getElementById('step-timer-container').querySelector('div');
        timerContainer.classList.remove('border-green-500', 'shadow-[6px_6px_0_#22c55e]'); 
        timerContainer.classList.add('border-[#8B7355]', 'shadow-[6px_6px_0_#8B7355]');
    }
};

window.finishRecipe = function() {
    if (window.AppAudio) window.AppAudio.success();
    const pageContent = document.getElementById('recipe-page-content');
    if (!pageContent) return;
    
    // Animate closing book
    pageContent.style.transformOrigin = 'left center';
    pageContent.style.transition = 'transform 1.5s cubic-bezier(0.4, 0.0, 0.2, 1), opacity 1s';
    pageContent.style.transform = 'rotateY(-180deg) scale(0.5)';
    pageContent.style.opacity = '0';
    
    // Confetti
    if (window.confetti) {
        confetti({
            particleCount: 150,
            spread: 80,
            origin: { y: 0.6 },
            zIndex: 9999,
            colors: ['#f97316', '#22c55e', '#3b82f6', '#facc15']
        });
    }

    // End cooking after animation
    setTimeout(() => {
        if (typeof endCooking === 'function') {
            endCooking();
        } else if (window.endCooking) {
            window.endCooking();
        }
    }, 2000);
};


window.toggleRecipeBook = function() {
    const sidebar = document.getElementById('recipe-book-sidebar');
    if (sidebar.classList.contains('-translate-x-full')) {
        sidebar.classList.remove('-translate-x-full');
        loadRecipeBook();
    } else {
        sidebar.classList.add('-translate-x-full');
    }
};

window.loadRecipeBook = async function() {
    const list = document.getElementById('recipe-book-list');
    list.innerHTML = '<div class="text-center mt-5 text-gray-500">Загрузка...</div>';
    
    try {
        let recipes = [];
        
        // 1. Попытка загрузить из Supabase
        if (typeof supabaseClient !== 'undefined') {
            let user_id = null;
            try {
                user_id = localStorage.getItem('chefId');
            } catch(ex) {}
            
            let query = supabaseClient.from('ai_requests').select('*').order('request_id', { ascending: false });
            if (user_id) {
                query = query.eq('user_id', user_id);
            }
            const { data, error } = await query;
            
            if (!error && data) {
                recipes = data.map(row => ({
                    recipe: row.ai_response,
                    confirmed_at: new Date().toISOString() // Or get from created_at if table has it
                }));
            }
        }
        
        // 2. Fallback на In-Memory бэкенд, если Supabase пуст или отвалился
        if (recipes.length === 0) {
            const response = await fetch('http://localhost:8000/recipe-book', {
                headers: { 'X-User-Id': localStorage.getItem('chefId') || 'test-user' }
            });
            if (response.ok) {
                const data = await response.json();
                recipes = data;
            }
        }
        
        if (recipes.length === 0) {
            list.innerHTML = '<div class="text-gray-400 text-sm text-center mt-10">Пока нет сохраненных рецептов.<br><br>Они появятся здесь, когда вы подтвердите готовку.</div>';
            return;
        }
        
        list.innerHTML = '';
        recipes.forEach(entry => {
            const recipe = entry.recipe;
            if (!recipe) return;
            const card = document.createElement('div');
            card.className = 'bg-white p-3 rounded-lg shadow-sm border border-gray-100 hover:shadow-md cursor-pointer transition';
            card.innerHTML = `
                <div class="font-bold text-gray-800 text-sm mb-1">${recipe.title || 'Рецепт'}</div>
                <div class="text-xs text-gray-500 flex justify-between">
                    <span>${recipe.total_time_minutes ? recipe.total_time_minutes + ' мин' : '?'}</span>
                    <span>${new Date(entry.confirmed_at).toLocaleDateString()}</span>
                </div>
            `;
            card.onclick = () => {
                toggleRecipeBook();
                renderRecipeCard(recipe);
                const chatEmptyState = document.getElementById('chat-empty-state');
                if (chatEmptyState) chatEmptyState.style.display = 'none';
            };
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
        list.innerHTML = '<div class="text-red-400 text-sm text-center mt-10">Ошибка загрузки</div>';
    }
};

window.startNewChat = function() {
    if (window.reshuffleDynamicGreetings) window.reshuffleDynamicGreetings();
    const screenChat = document.getElementById('screen-chat');
    
    // Если мы на экране готовки - используем endCooking, который все сбросит и вернет на главный экран
    if (screenChat && screenChat.classList.contains('hidden')) {
        if (typeof endCooking === 'function') endCooking();
        return;
    }
    
    const chatMessages = document.getElementById('chat-messages');
    let delay = 0;
    
    if (chatMessages) {
        const messages = chatMessages.querySelectorAll('.flex.w-full.mb-6');
        if (messages.length > 0) {
            delay = 300;
            messages.forEach(m => {
                m.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                m.style.opacity = '0';
                m.style.transform = 'translateY(10px)';
            });
        }
        
        setTimeout(() => {
            messages.forEach(m => m.remove());
            const chatEmptyState = document.getElementById('chat-empty-state');
            if (chatEmptyState) {
                chatEmptyState.style.opacity = '0';
                chatEmptyState.style.display = 'block';
                chatEmptyState.style.transform = 'scale(0.95)';
                void chatEmptyState.offsetWidth;
                chatEmptyState.style.transition = 'opacity 0.4s ease, transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
                chatEmptyState.style.opacity = '1';
                chatEmptyState.style.transform = 'scale(1)';
            }
            window.currentChatId = null;
        }, delay);
    }
    
    const sidebar = document.getElementById('recipe-book-sidebar');
    if (sidebar && !sidebar.classList.contains('-translate-x-full')) {
        toggleRecipeBook();
    }
};

const LEVELS = [
    { level: 1, title: 'Новичок на кухне', xp: 0, icon: '🥚' },
    { level: 2, title: 'Поваренок', xp: 1000, icon: '🥪' },
    { level: 3, title: 'Младший кулинар', xp: 2500, icon: '🥗' },
    { level: 4, title: 'Уверенный повар', xp: 4500, icon: '🍝' },
    { level: 5, title: 'Су-шеф', xp: 7000, icon: '🍣' },
    { level: 6, title: 'Шеф-повар', xp: 10000, icon: '👨‍🍳' },
    { level: 7, title: 'Мастер вкуса', xp: 15000, icon: '🔥' },
    { level: 8, title: 'Звезда Мишлен', xp: 20000, icon: '⭐' },
    { level: 9, title: 'Кулинарный гений', xp: 30000, icon: '👑' },
    { level: 10, title: 'Легенда кухни', xp: 50000, icon: '🏆' }
];

function getLevelInfo(xp) {
    let current = LEVELS[0];
    let next = LEVELS[1];
    for (let i = 0; i < LEVELS.length; i++) {
        if (xp >= LEVELS[i].xp) {
            current = LEVELS[i];
            next = LEVELS[i + 1] || null;
        } else break;
    }
    return { current, next };
}

window.addXP = async function(amount) {
    const userId = localStorage.getItem('chefId');
    if (!userId) return; // Not logged in
    
    const oldXp = parseInt(localStorage.getItem('chefPoints')) || 0;
    const newXp = oldXp + amount;
    localStorage.setItem('chefPoints', newXp);
    
    const oldLvl = getLevelInfo(oldXp).current.level;
    const newLvl = getLevelInfo(newXp).current.level;
    
    if (newLvl > oldLvl && window.AppAudio && window.AppAudio.success) {
        window.AppAudio.success();
        const toast = document.createElement('div');
        toast.className = 'fixed top-10 left-1/2 transform -translate-x-1/2 bg-yellow-400 text-white px-6 py-3 rounded-full font-bold shadow-2xl z-50 transition-all';
        toast.innerText = `${window.t('achieve_new')} ${getLevelInfo(newXp).current.icon} ${window.t('lvl_' + getLevelInfo(newXp).current.level)}`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }
    
    updateXPButton(newXp);
    
    if (typeof supabaseClient !== 'undefined') {
        try {
            await supabaseClient.from('users').update({ points: newXp }).eq('user_id', userId);
        } catch(e) { console.error('XP Sync Error', e); }
    }
};

function updateXPButton(xp) {
    const btnText = document.getElementById('xp-btn-text');
    if (btnText) btnText.innerText = `${xp} XP`;
}

window.toggleAchieveSidebar = function() {
    const sidebar = document.getElementById('achieve-sidebar');
    if (sidebar.classList.contains('-translate-x-full')) {
        sidebar.classList.remove('-translate-x-full');
        renderAchieveSidebar();
    } else {
        sidebar.classList.add('-translate-x-full');
    }
};

function renderAchieveSidebar() {
    let xp = parseInt(localStorage.getItem('chefPoints')) || 0;
    
    const { current, next } = getLevelInfo(xp);
    const container = document.getElementById('achieve-list');
    
    let html = `
        <div class="text-center mb-6 mt-4">
            <div class="text-6xl mb-2">${current.icon}</div>
            <h2 class="text-xl font-bold font-serif text-gray-800">${window.t('lvl_' + current.level)}</h2>
            <p class="text-gray-500 text-sm">${window.t('achieve_level')} ${current.level}</p>
        </div>
    `;
    
    if (next) {
        const progress = Math.min(100, Math.round(((xp - current.xp) / (next.xp - current.xp)) * 100));
        html += `
        <div class="mb-6 px-2">
            <div class="flex justify-between text-xs text-gray-500 mb-1 font-bold">
                <span>${xp} XP</span>
                <span>${next.xp} XP</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-3">
                <div class="bg-yellow-400 h-3 rounded-full transition-all duration-1000" style="width: ${progress}%"></div>
            </div>
            <p class="text-center text-xs text-gray-400 mt-2">${window.t('achieve_until')} "${window.t('lvl_' + next.level)}" ${window.t('achieve_left')} ${next.xp - xp} XP</p>
        </div>
        `;
    } else {
        html += `<div class="text-center text-sm text-yellow-500 font-bold mb-6">${window.t('achieve_max')}</div>`;
    }
    
    html += `<h3 class="font-bold text-gray-800 mb-3 uppercase text-xs tracking-wider px-2">${window.t('achieve_all')}</h3><div class="flex flex-col gap-2 px-2 pb-6">`;
    
    LEVELS.forEach(lvl => {
        const isUnlocked = xp >= lvl.xp;
        const isCurrent = current.level === lvl.level;
        const opacity = isUnlocked ? 'opacity-100' : 'opacity-40 grayscale';
        const border = isCurrent ? 'border-yellow-400 border-2 shadow-md bg-yellow-50' : 'border-gray-100 border bg-white';
        
        html += `
            <div class="flex items-center p-3 rounded-xl ${border} ${opacity} transition-all">
                <div class="text-2xl mr-4">${lvl.icon}</div>
                <div class="flex-1">
                    <div class="font-bold text-sm text-gray-800">${window.t('lvl_' + lvl.level)}</div>
                    <div class="text-xs text-gray-400">${lvl.xp} XP</div>
                </div>
                ${isUnlocked ? '<div class="text-green-500 font-bold">✓</div>' : '<div class="text-gray-300">🔒</div>'}
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

// Track completed steps to prevent spamming XP
window.completedSteps = new Set();

setTimeout(() => { if(window.updateXPButton) updateXPButton(parseInt(localStorage.getItem('chefPoints')) || 0); }, 500);


// ==========================================
// SWIPE TO CLOSE SIDEBARS (Mobile)
// ==========================================
let touchStartX = 0;
let touchEndX = 0;

function handleSwipeGesture(sidebarId, closeFunc) {
    const sidebar = document.getElementById(sidebarId);
    if (!sidebar) return;

    sidebar.addEventListener('touchstart', e => {
        touchStartX = e.changedTouches[0].screenX;
    }, {passive: true});

    sidebar.addEventListener('touchend', e => {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe(sidebar, closeFunc);
    }, {passive: true});
}

function handleSwipe(sidebar, closeFunc) {
    // Swipe left threshold: 50px
    if (touchEndX < touchStartX - 50) {
        if (!sidebar.classList.contains('-translate-x-full')) {
            closeFunc();
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    handleSwipeGesture('achieve-sidebar', () => {
        document.getElementById('achieve-sidebar').classList.add('-translate-x-full');
    });
    handleSwipeGesture('recipe-book-sidebar', () => {
        document.getElementById('recipe-book-sidebar').classList.add('-translate-x-full');
    });
});
