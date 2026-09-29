// "Recipe magazine" feature: shareable collections of recipes picked from
// the user's own recipe book (see backend/schemas/recipe_magazine.py).
// Not to be confused with the recipe-book sidebar (js/ui.js's
// toggleRecipeBook/loadRecipeBook), which is the user's full request
// history - a magazine is a separate, publishable subset of it.

const MAGAZINE_API_BASE = window.CHEF_API_BASE;

function getChefId() {
    try {
        return localStorage.getItem('chefId');
    } catch (ex) {
        return null;
    }
}

function magazineHeaders(extra) {
    // Falls back to 'test-user', matching js/ui.js's chat/recipe-book calls -
    // both must agree on the id, or entries confirmed via one code path
    // become invisible to the other (see REPORT.md for this fix).
    return Object.assign({ 'X-User-Id': getChefId() || 'test-user' }, extra || {});
}

// ==========================================
// Мои кулинарные журналы (сайдбар)
// ==========================================

window.toggleMyMagazines = function () {
    const sidebar = document.getElementById('magazine-sidebar');
    if (sidebar.classList.contains('-translate-x-full')) {
        sidebar.classList.remove('-translate-x-full');
        loadMyMagazines();
    } else {
        sidebar.classList.add('-translate-x-full');
    }
};

window.loadMyMagazines = async function () {
    const list = document.getElementById('magazine-list');
    list.innerHTML = '<div class="text-center mt-5 text-gray-500">Загрузка...</div>';
    try {
        const response = await fetch(`${MAGAZINE_API_BASE}/recipe-magazines`, {
            headers: magazineHeaders()
        });
        if (!response.ok) throw new Error('request failed');
        const magazines = await response.json();

        if (magazines.length === 0) {
            list.innerHTML = '<div class="text-gray-400 text-sm text-center mt-10">У вас пока нет кулинарных журналов.</div>';
            return;
        }

        list.innerHTML = '';
        magazines.forEach(magazine => {
            const card = document.createElement('div');
            card.className = 'bg-white p-3 rounded-lg shadow-sm border border-gray-100 hover:shadow-md transition flex items-center justify-between gap-2';
            card.innerHTML = `
                <div class="flex-1 cursor-pointer min-w-0">
                    <div class="font-bold text-gray-800 text-sm mb-1 truncate">${magazine.title}</div>
                    <div class="text-xs text-gray-500 flex justify-between">
                        <span>${magazine.recipe_count} рец.</span>
                        <span>${magazine.is_public ? '🌐 Опубликован · 👁 ' + magazine.view_count : '🔒 Черновик'}</span>
                    </div>
                </div>
                <button class="text-xs text-claude-accent hover:underline shrink-0" title="Смотреть рецепты и готовить">👁 Смотреть</button>
            `;
            card.querySelector('.flex-1').onclick = () => openMagazineEditor(magazine.id);
            card.querySelector('button').onclick = () => openMagazineDetail(magazine.id);
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
        list.innerHTML = '<div class="text-red-400 text-sm text-center mt-10">Ошибка загрузки</div>';
    }
};

// ==========================================
// Витрина (маркет) кулинарных журналов
// ==========================================

let magazineMarketSearchTimer = null;
let magazineMarketSort = 'popular';

window.toggleMagazineMarket = function () {
    const page = document.getElementById('magazine-market-page');
    if (page.classList.contains('hidden')) {
        page.classList.remove('hidden');
        page.classList.add('flex');
        loadMagazineMarket();
    } else {
        page.classList.add('hidden');
        page.classList.remove('flex');
    }
};

window.closeMagazineMarketToHome = function () {
    const page = document.getElementById('magazine-market-page');
    page.classList.add('hidden');
    page.classList.remove('flex');
    if (typeof window.startNewChat === 'function') {
        window.startNewChat();
    }
};

window.setMagazineMarketSort = function (sort) {
    magazineMarketSort = sort;
    const popularBtn = document.getElementById('magazine-market-sort-popular');
    const latestBtn = document.getElementById('magazine-market-sort-latest');
    const activeClasses = ['bg-white', 'shadow-sm', 'text-claude-text'];
    const inactiveClasses = ['text-gray-500'];
    if (sort === 'popular') {
        popularBtn.classList.add(...activeClasses);
        popularBtn.classList.remove(...inactiveClasses);
        latestBtn.classList.remove(...activeClasses);
        latestBtn.classList.add(...inactiveClasses);
    } else {
        latestBtn.classList.add(...activeClasses);
        latestBtn.classList.remove(...inactiveClasses);
        popularBtn.classList.remove(...activeClasses);
        popularBtn.classList.add(...inactiveClasses);
    }
    const searchInput = document.getElementById('magazine-market-search');
    loadMagazineMarket(searchInput ? searchInput.value.trim() : '');
};

window.loadMagazineMarket = async function (query) {
    const list = document.getElementById('magazine-market-list');
    list.innerHTML = '<div class="col-span-full text-center mt-5 text-gray-500">Загрузка...</div>';
    try {
        const params = new URLSearchParams();
        if (query) params.set('q', query);
        params.set('sort', magazineMarketSort);
        const response = await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/market?${params.toString()}`);
        if (!response.ok) throw new Error('request failed');
        const magazines = await response.json();

        if (magazines.length === 0) {
            list.innerHTML = '<div class="col-span-full text-gray-400 text-sm text-center mt-10">Пока нет опубликованных журналов.</div>';
            return;
        }

        list.innerHTML = '';
        magazines.forEach(magazine => {
            const card = document.createElement('div');
            card.className = 'bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-lg hover:-translate-y-0.5 cursor-pointer transition-all overflow-hidden flex flex-col';
            const coverHtml = magazine.has_cover
                ? `<img src="${MAGAZINE_API_BASE}/recipe-magazines/${magazine.id}/cover" class="w-full h-32 object-cover" alt="">`
                : `<div class="w-full h-32 bg-gradient-to-br from-claude-accent/10 to-claude-accent/30 flex items-center justify-center text-3xl">📖</div>`;
            card.innerHTML = `
                ${coverHtml}
                <div class="p-3 flex flex-col gap-1 flex-1">
                    <div class="font-bold text-gray-800 text-sm">${magazine.title}</div>
                    <div class="text-xs text-gray-500 line-clamp-2 flex-1">${magazine.description || ''}</div>
                    <div class="text-xs text-gray-400 flex justify-between pt-1">
                        <span>${magazine.recipe_count} рец.</span>
                        <span>👁 ${magazine.view_count}</span>
                    </div>
                </div>
            `;
            card.onclick = () => openMagazineDetail(magazine.id);
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
        list.innerHTML = '<div class="col-span-full text-red-400 text-sm text-center mt-10">Ошибка загрузки</div>';
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('magazine-market-search');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearTimeout(magazineMarketSearchTimer);
            const value = searchInput.value.trim();
            magazineMarketSearchTimer = setTimeout(() => loadMagazineMarket(value), 300);
        });
    }
});

// ==========================================
// Редактор журнала (создание / редактирование)
// ==========================================

window.currentEditingMagazineId = null;

window.openMagazineEditor = async function (magazineId) {
    window.currentEditingMagazineId = magazineId || null;

    const modal = document.getElementById('magazine-editor-modal');
    const titleEl = document.getElementById('magazine-editor-title');
    const titleInput = document.getElementById('magazine-editor-title-input');
    const descriptionInput = document.getElementById('magazine-editor-description-input');
    const shareBtn = document.getElementById('magazine-editor-share-btn');
    const unpublishBtn = document.getElementById('magazine-editor-unpublish-btn');
    const deleteBtn = document.getElementById('magazine-editor-delete-btn');

    titleInput.value = '';
    descriptionInput.value = '';
    document.getElementById('magazine-editor-cover-input').value = '';
    unpublishBtn.classList.add('hidden');
    deleteBtn.classList.add('hidden');
    shareBtn.classList.remove('hidden');
    renderMagazineEditorCurrentItems([]);

    let selectedRecipeIds = new Set();

    if (magazineId) {
        titleEl.innerText = 'Редактировать журнал';
        deleteBtn.classList.remove('hidden');
        try {
            const response = await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}`, {
                headers: magazineHeaders()
            });
            if (response.ok) {
                const detail = await response.json();
                titleInput.value = detail.title;
                descriptionInput.value = detail.description || '';
                if (detail.is_public) {
                    shareBtn.classList.add('hidden');
                    unpublishBtn.classList.remove('hidden');
                }
                // Editing an existing magazine's items isn't matched back to
                // a history row's id from the snapshot alone - re-selecting
                // a recipe below just re-adds it, matched by title.
                selectedRecipeIds = new Set(detail.items.map(item => item.recipe.title));
                renderMagazineEditorCurrentItems(detail.items);
            }
        } catch (e) {
            console.error(e);
        }
    } else {
        titleEl.innerText = 'Новый журнал';
    }

    await renderMagazineRecipeChecklist(selectedRecipeIds);

    modal.classList.remove('hidden');
    modal.classList.add('flex');
};

window.closeMagazineEditor = function () {
    const modal = document.getElementById('magazine-editor-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    window.currentEditingMagazineId = null;
};

// key -> Recipe object, populated by renderMagazineRecipeChecklist() and
// read back by getSelectedRecipes() - a checkbox's `value` only holds a
// string, so the actual Recipe payload is kept here instead.
let magazineChecklistRecipesByKey = {};

// itemId -> Recipe, populated by renderMagazineEditorCurrentItems(), looked
// up by cookMagazineEditorItem().
let magazineEditorItemsByItemId = {};

function renderMagazineEditorCurrentItems(items) {
    const wrapper = document.getElementById('magazine-editor-current-items-wrapper');
    const container = document.getElementById('magazine-editor-current-items');
    magazineEditorItemsByItemId = {};

    if (!items || items.length === 0) {
        wrapper.classList.add('hidden');
        container.innerHTML = '';
        return;
    }

    wrapper.classList.remove('hidden');
    container.innerHTML = items.map(item => {
        magazineEditorItemsByItemId[item.id] = item.recipe;
        return `
            <div class="flex items-center justify-between gap-2 text-sm text-gray-700 py-1">
                <span class="truncate">${item.recipe.title || 'Без названия'}</span>
                <button onclick="cookMagazineEditorItem('${item.id}')" class="text-xs bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded-lg shrink-0" title="Готовить с помощью жестов">👋 Готовить</button>
            </div>
        `;
    }).join('');
}

window.cookMagazineEditorItem = function (itemId) {
    const recipe = magazineEditorItemsByItemId[itemId];
    if (!recipe) return;
    window.startCookingRecipe(recipe);
};

async function fetchUsersRecipeHistory() {
    // Same source as js/ui.js's loadRecipeBook(): the frontend's actual,
    // durable recipe history lives in Supabase's `ai_requests` table, not
    // in this backend's (currently in-memory, wiped on every restart)
    // /recipe-book endpoint - see REPORT.md for how this was found.
    if (typeof supabaseClient === 'undefined') return [];
    const userId = getChefId();
    if (!userId) return [];
    const { data, error } = await supabaseClient
        .from('ai_requests')
        .select('*')
        .eq('user_id', userId)
        .order('request_id', { ascending: false });
    if (error || !data) return [];
    return data
        .filter(row => row.ai_response)
        .map(row => ({ key: String(row.request_id), recipe: row.ai_response }));
}

async function renderMagazineRecipeChecklist(selectedTitles) {
    const container = document.getElementById('magazine-editor-recipe-list');
    container.innerHTML = '<div class="text-xs text-gray-400 text-center">Загрузка рецептов...</div>';
    try {
        const historyRows = await fetchUsersRecipeHistory();
        magazineChecklistRecipesByKey = {};

        if (historyRows.length === 0) {
            container.innerHTML = '<div class="text-xs text-gray-400 text-center">В вашей книге рецептов пока пусто.</div>';
            return;
        }

        container.innerHTML = '';
        historyRows.forEach(({ key, recipe }) => {
            magazineChecklistRecipesByKey[key] = recipe;
            const label = document.createElement('label');
            label.className = 'flex items-center gap-2 text-sm text-gray-700 py-1';
            const checked = selectedTitles.has(recipe.title) ? 'checked' : '';
            label.innerHTML = `
                <input type="checkbox" value="${key}" ${checked} class="magazine-recipe-checkbox">
                <span>${recipe.title || 'Без названия'}</span>
            `;
            container.appendChild(label);
        });
    } catch (e) {
        console.error(e);
        container.innerHTML = '<div class="text-xs text-red-400 text-center">Ошибка загрузки рецептов</div>';
    }
}

function getSelectedRecipes() {
    return Array.from(document.querySelectorAll('.magazine-recipe-checkbox:checked'))
        .map(el => magazineChecklistRecipesByKey[el.value])
        .filter(Boolean);
}

async function ensureMagazineCreatedOrUpdated() {
    const title = document.getElementById('magazine-editor-title-input').value.trim();
    const description = document.getElementById('magazine-editor-description-input').value.trim() || null;
    if (!title) {
        alert('Введите название журнала.');
        return null;
    }

    let magazineId = window.currentEditingMagazineId;
    if (magazineId) {
        const response = await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}`, {
            method: 'PATCH',
            headers: magazineHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ title, description })
        });
        if (!response.ok) throw new Error('update failed');
    } else {
        const response = await fetch(`${MAGAZINE_API_BASE}/recipe-magazines`, {
            method: 'POST',
            headers: magazineHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ title, description })
        });
        if (!response.ok) throw new Error('create failed');
        const created = await response.json();
        magazineId = created.id;
        window.currentEditingMagazineId = magazineId;
    }

    const recipes = getSelectedRecipes();
    await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}/items`, {
        method: 'PUT',
        headers: magazineHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ recipes })
    });

    const coverInput = document.getElementById('magazine-editor-cover-input');
    if (coverInput.files && coverInput.files[0]) {
        const formData = new FormData();
        formData.append('cover', coverInput.files[0]);
        await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}/cover`, {
            method: 'PUT',
            headers: magazineHeaders(),
            body: formData
        });
    }

    return magazineId;
}

window.saveMagazineEditor = async function () {
    try {
        const magazineId = await ensureMagazineCreatedOrUpdated();
        if (!magazineId) return;
        closeMagazineEditor();
        loadMyMagazines();
    } catch (e) {
        console.error(e);
        alert('Не удалось сохранить журнал.');
    }
};

window.shareMagazineFromEditor = async function () {
    try {
        const magazineId = await ensureMagazineCreatedOrUpdated();
        if (!magazineId) return;
        await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}/share`, {
            method: 'POST',
            headers: magazineHeaders()
        });
        closeMagazineEditor();
        loadMyMagazines();
    } catch (e) {
        console.error(e);
        alert('Не удалось опубликовать журнал.');
    }
};

window.unpublishMagazineFromEditor = async function () {
    const magazineId = window.currentEditingMagazineId;
    if (!magazineId) return;
    try {
        await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}/unpublish`, {
            method: 'POST',
            headers: magazineHeaders()
        });
        closeMagazineEditor();
        loadMyMagazines();
    } catch (e) {
        console.error(e);
        alert('Не удалось снять журнал с публикации.');
    }
};

window.deleteMagazineFromEditor = async function () {
    const magazineId = window.currentEditingMagazineId;
    if (!magazineId) return;
    if (!confirm('Удалить этот журнал? Это действие необратимо.')) return;
    try {
        await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}`, {
            method: 'DELETE',
            headers: magazineHeaders()
        });
        closeMagazineEditor();
        loadMyMagazines();
    } catch (e) {
        console.error(e);
        alert('Не удалось удалить журнал.');
    }
};

// ==========================================
// Просмотр журнала (свой или чужой)
// ==========================================

let currentDetailMagazineId = null;
// itemId -> Recipe, populated by openMagazineDetail() - looked up by
// cookMagazineItem() since a button's onclick can't hold a full object.
let magazineDetailRecipesByItemId = {};

function renderReadonlyRecipeHtml(recipe, actionButtonHtml, sourceMagazineTitle) {
    let ingredientsHtml = '<p class="font-semibold text-gray-800 mb-2">🛒 Ингредиенты:</p><ul class="list-disc pl-5 text-sm text-gray-700 space-y-1 mb-3">';
    (recipe.ingredients || []).forEach(ing => {
        const amount = ing.amount ? ing.amount + ' ' : '';
        const unit = ing.unit && ing.unit !== 'по вкусу' ? ing.unit + ' ' : '';
        ingredientsHtml += `<li><b>${ing.name}</b> — ${amount}${unit}</li>`;
    });
    ingredientsHtml += '</ul>';

    let stepsHtml = '<p class="font-semibold text-gray-800 mb-2">👩‍🍳 Шаги:</p><ol class="list-decimal pl-5 text-sm text-gray-700 space-y-1">';
    (recipe.steps || []).forEach(step => {
        stepsHtml += `<li>${step.display_text || step.action}</li>`;
    });
    stepsHtml += '</ol>';

    // Never rendered as if it were the viewer's own creation once it was
    // saved from someone else's magazine - see backend's
    // RecipeMagazineItem.source_magazine_title docstring.
    const attributionHtml = sourceMagazineTitle
        ? `<p class="text-xs text-gray-400 italic mb-2">📌 Источник: «${sourceMagazineTitle}»</p>`
        : '';

    return `
        <div class="border-b border-gray-100 pb-6 last:border-0">
            <div class="flex justify-between items-start mb-2">
                <div class="font-serif font-bold text-lg text-claude-text">🍳 ${recipe.title || 'Рецепт'}</div>
                ${actionButtonHtml || ''}
            </div>
            ${attributionHtml}
            <p class="text-sm text-gray-500 mb-3">⏱ ${recipe.total_time_minutes || '?'} мин | 👥 ${recipe.servings || '?'} порц.</p>
            ${ingredientsHtml}
            ${stepsHtml}
        </div>
    `;
}

window.openMagazineDetail = async function (magazineId) {
    currentDetailMagazineId = magazineId;
    const modal = document.getElementById('magazine-detail-modal');
    const itemsContainer = document.getElementById('magazine-detail-items');
    itemsContainer.innerHTML = '<div class="text-center text-gray-500">Загрузка...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    try {
        const response = await fetch(`${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}`, {
            headers: magazineHeaders()
        });
        if (!response.ok) throw new Error('request failed');
        const detail = await response.json();

        document.getElementById('magazine-detail-title').innerText = detail.title;
        document.getElementById('magazine-detail-description').innerText = detail.description || '';
        document.getElementById('magazine-detail-views').innerText = `👁 ${detail.view_count} просмотров`;

        const coverImg = document.getElementById('magazine-detail-cover');
        if (detail.has_cover) {
            coverImg.src = `${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}/cover`;
            coverImg.classList.remove('hidden');
        } else {
            coverImg.classList.add('hidden');
        }

        const isOwner = detail.user_id === (getChefId() || 'test-user');
        magazineDetailRecipesByItemId = {};
        itemsContainer.innerHTML = detail.items.map(item => {
            magazineDetailRecipesByItemId[item.id] = item.recipe;
            const saveButton = isOwner
                ? ''
                : `<button onclick="openSaveItemPicker('${magazineId}', '${item.id}')" class="text-xs bg-claude-accent hover:bg-claude-accentHover text-white px-3 py-1 rounded-lg shrink-0">Сохранить в мой журнал</button>`;
            const cookButton = `<button onclick="cookMagazineItem('${item.id}')" class="text-xs bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded-lg shrink-0" title="Готовить с помощью жестов">👋 Готовить</button>`;
            const actionsHtml = `<div class="flex gap-2 shrink-0 ml-2">${cookButton}${saveButton}</div>`;
            return renderReadonlyRecipeHtml(item.recipe, actionsHtml, item.source_magazine_title);
        }).join('');
    } catch (e) {
        console.error(e);
        itemsContainer.innerHTML = '<div class="text-center text-red-400">Ошибка загрузки журнала</div>';
    }
};

window.closeMagazineDetail = function () {
    const modal = document.getElementById('magazine-detail-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    currentDetailMagazineId = null;
};

function closeAllMagazineOverlays() {
    ['magazine-detail-modal', 'magazine-editor-modal', 'magazine-save-picker-modal', 'magazine-market-page']
        .forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.classList.add('hidden');
            el.classList.remove('flex');
        });
    ['magazine-sidebar', 'recipe-book-sidebar', 'achieve-sidebar'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('-translate-x-full');
    });
}

window.cookMagazineItem = function (itemId) {
    const recipe = magazineDetailRecipesByItemId[itemId];
    if (!recipe) return;
    window.startCookingRecipe(recipe);
};

window.startCookingRecipe = function (recipe) {
    // Cooking mode (gesture control) is the same #screen-cooking used from
    // the chat flow (js/ui.js's renderRecipeCard -> startCooking()) - here
    // we just feed it a recipe that came from a magazine instead of a fresh
    // chat, and make sure no magazine overlay is left covering the screen.
    closeAllMagazineOverlays();
    window.mockRecipeData = window.buildMockRecipeData(recipe);
    window.currentChatId = null; // not tied to any chat - there's no "confirm" step here
    startCooking();
};

// ==========================================
// Пикер "в какой мой журнал сохранить"
// ==========================================

let saveItemPickerSource = null; // { magazineId, itemId }

window.openSaveItemPicker = async function (magazineId, itemId) {
    saveItemPickerSource = { magazineId, itemId };
    const modal = document.getElementById('magazine-save-picker-modal');
    const list = document.getElementById('magazine-save-picker-list');
    list.innerHTML = '<div class="text-center text-sm text-gray-500 py-4">Загрузка...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    try {
        const response = await fetch(`${MAGAZINE_API_BASE}/recipe-magazines`, { headers: magazineHeaders() });
        if (!response.ok) throw new Error('request failed');
        const myMagazines = await response.json();

        if (myMagazines.length === 0) {
            list.innerHTML = '<div class="text-center text-sm text-gray-400 py-4">У вас пока нет своих журналов - создайте новый.</div>';
            return;
        }

        list.innerHTML = '';
        myMagazines.forEach(magazine => {
            const row = document.createElement('button');
            row.className = 'text-left px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition';
            row.innerText = magazine.title;
            row.onclick = () => saveItemToMagazine(magazine.id);
            list.appendChild(row);
        });
    } catch (e) {
        console.error(e);
        list.innerHTML = '<div class="text-center text-sm text-red-400 py-4">Ошибка загрузки</div>';
    }
};

window.closeSaveItemPicker = function () {
    const modal = document.getElementById('magazine-save-picker-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    saveItemPickerSource = null;
};

window.saveItemToMagazine = async function (targetMagazineId) {
    if (!saveItemPickerSource) return;
    const { magazineId, itemId } = saveItemPickerSource;
    try {
        const response = await fetch(
            `${MAGAZINE_API_BASE}/recipe-magazines/${magazineId}/items/${itemId}/save`,
            {
                method: 'POST',
                headers: magazineHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ target_magazine_id: targetMagazineId })
            }
        );
        if (!response.ok) throw new Error('save failed');
        closeSaveItemPicker();
        alert('Рецепт сохранён в ваш журнал.');
    } catch (e) {
        console.error(e);
        alert('Не удалось сохранить рецепт.');
    }
};

window.saveItemToNewMagazine = async function () {
    const title = prompt('Название нового журнала:');
    if (!title || !title.trim()) return;
    try {
        const response = await fetch(`${MAGAZINE_API_BASE}/recipe-magazines`, {
            method: 'POST',
            headers: magazineHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ title: title.trim(), description: null })
        });
        if (!response.ok) throw new Error('create failed');
        const created = await response.json();
        await saveItemToMagazine(created.id);
    } catch (e) {
        console.error(e);
        alert('Не удалось создать журнал.');
    }
};
