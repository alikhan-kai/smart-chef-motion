// Словарь переводов
// Словарь переводов
window.translations = {
    ru: {
        app_subtitle: "Ваш ИИ-су-шеф, управляемый жестами",
        email_label: "Email",
        password_label: "Пароль",
        name_label: "Имя",
        login_btn: "Войти",
        register_btn: "Создать аккаунт",
        no_account: "Нет аккаунта?",
        have_account: "Уже есть аккаунт?",
        to_register: "Зарегистрироваться",
        to_login: "Войти",
        placeholder_name: "Иван Иванов",
        
        // Экран Чата
        history_title: "История рецептов",
        history_empty: "Тут будут сохраненные рецепты...",
        magazine_mine_title: "Мои кулинарные журналы",
        magazine_mine_empty: "У вас пока нет кулинарных журналов.",
        magazine_new_button: "+ Новый журнал",
        magazine_market_title: "Витрина журналов",
        magazine_market_search_placeholder: "Поиск по названию...",
        magazine_market_empty: "Пока нет опубликованных журналов.",
        magazine_editor_title_new: "Новый журнал",
        magazine_field_title: "Название",
        magazine_field_description: "Описание",
        magazine_field_cover: "Обложка",
        magazine_field_current_items: "Рецепты в этом журнале",
        magazine_field_recipes: "Рецепты из вашей книги",
        magazine_save_button: "Сохранить",
        magazine_share_button: "Поделиться",
        magazine_unpublish_button: "Снять с публикации",
        magazine_delete_button: "Удалить",
        magazine_sort_popular: "Популярное",
        magazine_sort_latest: "Новое",
        magazine_save_picker_title: "Сохранить в журнал",
        magazine_save_picker_new: "+ Новый журнал",
        achievements_title: "Достижения",
        achieve_level: "Уровень",
        achieve_until: "До звания",
        achieve_left: "осталось",
        achieve_max: "Вы достигли максимального уровня!",
        achieve_all: "Все звания:",
        achieve_new: "Новый уровень!",
        lvl_1: "Новичок на кухне",
        lvl_2: "Поваренок",
        lvl_3: "Младший кулинар",
        lvl_4: "Уверенный повар",
        lvl_5: "Су-шеф",
        lvl_6: "Шеф-повар",
        lvl_7: "Мастер вкуса",
        lvl_8: "Звезда Мишлен",
        lvl_9: "Легендарный шеф",
        lvl_10: "Бог кухни",
        xp_points: "Очки (XP):",
        welcome_chef: [
            "Здравствуйте, ",
            "Рады видеть вас, ",
            "Добро пожаловать на кухню, ",
            "Приветствую, "
        ],
        chat_prompt: [
            "Что мы будем готовить сегодня?",
            "Какой рецепт вам подсказать?",
            "Чем займемся на кухне?",
            "Готовы к кулинарным шедеврам?"
        ],
        input_placeholder: "Напишите ингредиенты или блюдо...",
        ai_disclaimer: "Пожалуйста, укажите, если у вас есть аллергия на какие-либо продукты.",
        logout_btn: "Выйти",

        // Экран Готовки (Статика)
        camera_title: "Камера",
        camera_active: "Активно",
        camera_placeholder: "Здесь будет видео с камеры\n(ML MediaPipe)",
        recognized_gesture: "Распознанный жест",
        gesture_waiting: "Ожидание...",
        end_cooking_btn: "Завершить готовку",
        alice_connect: "🎙 Подключить Алису",
        alice_connected: "✓ Алиса подключена",
        alice_helper: "Управляйте таймером голосом через Яндекс Станцию",
        alice_active: "Алиса подключена — голосовое управление активно",
        alice_checking: "Проверяю подключение Алисы…",
        alice_expired: "Подключение устарело — подключите Алису снова",
        alice_creating: "Создаю код подключения…",
        alice_pair_steps: "1. Скажите: «Алиса, запусти навык Умный шеф». 2. Назовите код:",
        alice_stopped: "Алиса остановила таймер",
        alice_started_step: "Алиса запустила таймер шага",
        alice_started_custom: "Алиса запустила таймер на {seconds} сек.",
        alice_wrong_time: "Неверное время. Для этого шага нужно {seconds} сек.",
        alice_backend_error: "Не удалось подключиться. Проверьте backend.",
        alice_time_up: "⏰ Время вышло — скажите «останови таймер» или покажите ладонь",
        ml_loading: "Загрузка ИИ (MediaPipe)...",
        ml_camera_starting: "Запуск камеры...",
        ml_camera_ready: "Камера готова!",
        ml_camera_error: "Ошибка доступа к камере",
        ml_gesture_unknown: "Жест не распознан! Сделайте четкий жест.",
        ml_gesture_like: "👍 Лайк (Вперед)",
        ml_gesture_dislike: "👎 Дизлайк (Назад)",
        ml_gesture_peace: "✌️ Старт (Peace)",
        ml_gesture_palm: "✋ Стоп (Открытая ладонь)",
        ml_error_peace: "Пальцы слишком близко!",
        ml_error_thumb: "Вы не согнули пальцы для Лайка",
        btn_prev: "← Назад (Свайп вправо)",
        btn_next: "Далее (Свайп влево) →",
        
        // Динамика
        step_word: "Шаг",
        recipe_loading: "ИИ придумывает рецепт...",
        recipe_not_ready: "Рецепт ещё не загружен",
        recipe_wait: "Пожалуйста, подождите или проверьте сервер",
        recipe_empty: "Пустой рецепт",
        recipe_no_steps: "Нет шагов.",
        recipe_ingredients: "Ингредиенты",
        recipe_not_specified: "Не указаны",
        recipe_time: "Время",
        recipe_minutes: "мин",
        recipe_servings: "Порций",
        recipe_generated: "Сгенерировано нейросетью. Шагов в книге:",
        recipe_server_error: "Ошибка сервера (убедитесь, что backend запущен)",
        recipe_system_error: "Системная ошибка",
        out_of: "из",
        mock_recipe_title: "Сгенерированный рецепт",
        mock_recipe_li1: "Свежие ингредиенты подготовлены",
        mock_recipe_li2: "Время готовки: ~25 минут",
        mock_recipe_btn: "Готово (Принять рецепт)"
    },
    en: {
        app_subtitle: "Your gesture-controlled AI Sous-Chef",
        email_label: "Email Address",
        password_label: "Password",
        name_label: "Full Name",
        login_btn: "Sign In",
        register_btn: "Create Account",
        no_account: "Don't have an account?",
        have_account: "Already have an account?",
        to_register: "Sign Up",
        to_login: "Sign In",
        placeholder_name: "John Doe",

        // Экран Чата
        history_title: "Recipe History",
        history_empty: "Saved recipes will appear here...",
        magazine_mine_title: "My Recipe Magazines",
        magazine_mine_empty: "You don't have any recipe magazines yet.",
        magazine_new_button: "+ New Magazine",
        magazine_market_title: "Magazine Marketplace",
        magazine_market_search_placeholder: "Search by title...",
        magazine_market_empty: "No published magazines yet.",
        magazine_editor_title_new: "New Magazine",
        magazine_field_title: "Title",
        magazine_field_description: "Description",
        magazine_field_cover: "Cover photo",
        magazine_field_current_items: "Recipes in this magazine",
        magazine_field_recipes: "Recipes from your book",
        magazine_save_button: "Save",
        magazine_share_button: "Share",
        magazine_unpublish_button: "Unpublish",
        magazine_delete_button: "Delete",
        magazine_sort_popular: "Popular",
        magazine_sort_latest: "Latest",
        magazine_save_picker_title: "Save to magazine",
        magazine_save_picker_new: "+ New magazine",
        achievements_title: "Achievements",
        achieve_level: "Level",
        achieve_until: "XP left to",
        achieve_left: "",
        achieve_max: "You reached the maximum level!",
        achieve_all: "All Ranks:",
        achieve_new: "New Level Up!",
        lvl_1: "Kitchen Novice",
        lvl_2: "Cook's Helper",
        lvl_3: "Junior Cook",
        lvl_4: "Confident Cook",
        lvl_5: "Sous-Chef",
        lvl_6: "Head Chef",
        lvl_7: "Master of Taste",
        lvl_8: "Michelin Star",
        lvl_9: "Legendary Chef",
        lvl_10: "God of the Kitchen",
        xp_points: "Points (XP):",
        welcome_chef: [
            "Hello, ",
            "Glad to see you, ",
            "Welcome to the kitchen, ",
            "Greetings, "
        ],
        chat_prompt: [
            "What are we cooking today?",
            "What recipe can I help you with?",
            "Ready for a culinary masterpiece?",
            "What's on the menu today?"
        ],
        input_placeholder: "Type ingredients or a dish name...",
        ai_disclaimer: "Please specify if you have any food allergies.",
        logout_btn: "Log Out",

        // Экран Готовки (Статика)
        camera_title: "Camera",
        camera_active: "Active",
        camera_placeholder: "Camera feed will appear here\n(ML MediaPipe)",
        recognized_gesture: "Recognized Gesture",
        gesture_waiting: "Waiting...",
        end_cooking_btn: "End Cooking",
        alice_connect: "🎙 Connect Alice",
        alice_connected: "✓ Alice connected",
        alice_helper: "Control the timer by voice through Yandex Station",
        alice_active: "Alice is connected — voice control is active",
        alice_checking: "Checking the Alice connection…",
        alice_expired: "Connection expired — connect Alice again",
        alice_creating: "Creating a pairing code…",
        alice_pair_steps: "1. Say: “Alice, launch Smart Chef.” 2. Say this code:",
        alice_stopped: "Alice stopped the timer",
        alice_started_step: "Alice started the step timer",
        alice_started_custom: "Alice started a timer for {seconds} sec.",
        alice_wrong_time: "Wrong duration. This step requires {seconds} sec.",
        alice_backend_error: "Could not connect. Check the backend.",
        alice_time_up: "⏰ Time is up — say “stop timer” or show an open palm",
        ml_loading: "Loading AI (MediaPipe)...",
        ml_camera_starting: "Starting camera...",
        ml_camera_ready: "Camera ready!",
        ml_camera_error: "Camera access error",
        ml_gesture_unknown: "Unknown gesture! Make a clear gesture.",
        ml_gesture_like: "👍 Like (Next)",
        ml_gesture_dislike: "👎 Dislike (Prev)",
        ml_gesture_peace: "✌️ Start (Peace)",
        ml_gesture_palm: "✋ Stop (Open Palm)",
        ml_error_peace: "Fingers too close for Peace!",
        ml_error_thumb: "Fingers not folded for Like",
        btn_prev: "← Prev (Swipe Right)",
        btn_next: "Next (Swipe Left) →",
        
        // Динамика
        step_word: "Step",
        recipe_loading: "AI is creating your recipe...",
        recipe_not_ready: "Recipe not loaded yet",
        recipe_wait: "Please wait or check the server",
        recipe_empty: "Empty recipe",
        recipe_no_steps: "No steps.",
        recipe_ingredients: "Ingredients",
        recipe_not_specified: "Not specified",
        recipe_time: "Time",
        recipe_minutes: "min",
        recipe_servings: "Servings",
        recipe_generated: "AI-generated recipe. Steps in the book:",
        recipe_server_error: "Server error (check that the backend is running)",
        recipe_system_error: "System error",
        out_of: "of",
        mock_recipe_title: "Generated Recipe",
        mock_recipe_li1: "Fresh ingredients are ready",
        mock_recipe_li2: "Cooking time: ~25 mins",
        mock_recipe_btn: "Ready (Accept Recipe)"
    },
    kk: {
        app_subtitle: "Сіздің қимылмен басқарылатын AI-су-аспазыңыз",
        email_label: "Электрондық пошта",
        password_label: "Құпия сөз",
        name_label: "Аты-жөні",
        login_btn: "Кіру",
        register_btn: "Аккаунт жасау",
        no_account: "Аккаунтыңыз жоқ па?",
        have_account: "Аккаунтыңыз бар ма?",
        to_register: "Тіркелу",
        to_login: "Кіру",
        placeholder_name: "Асқар Ерасыл",

        // Экран Чата
        history_title: "Рецепттер тарихы",
        history_empty: "Мұнда сақталған рецепттер болады...",
        magazine_mine_title: "Менің кулинарлық журналдарым",
        magazine_mine_empty: "Сізде әлі кулинарлық журналдар жоқ.",
        magazine_new_button: "+ Жаңа журнал",
        magazine_market_title: "Журналдар витринасы",
        magazine_market_search_placeholder: "Атауы бойынша іздеу...",
        magazine_market_empty: "Әзірге жарияланған журналдар жоқ.",
        magazine_editor_title_new: "Жаңа журнал",
        magazine_field_title: "Атауы",
        magazine_field_description: "Сипаттама",
        magazine_field_cover: "Мұқаба",
        magazine_field_current_items: "Осы журналдағы рецепттер",
        magazine_field_recipes: "Сіздің кітабыңыздағы рецепттер",
        magazine_save_button: "Сақтау",
        magazine_share_button: "Бөлісу",
        magazine_unpublish_button: "Жариялаудан алу",
        magazine_delete_button: "Жою",
        magazine_sort_popular: "Танымал",
        magazine_sort_latest: "Жаңа",
        magazine_save_picker_title: "Журналға сақтау",
        magazine_save_picker_new: "+ Жаңа журнал",
        achievements_title: "Жетістіктер",
        achieve_level: "Деңгей",
        achieve_until: "Келесі атаққа дейін",
        achieve_left: "XP қалды",
        achieve_max: "Сіз ең жоғары деңгейге жеттіңіз!",
        achieve_all: "Барлық атақтар:",
        achieve_new: "Жаңа деңгей!",
        lvl_1: "Ас үй жаңадан бастаушысы",
        lvl_2: "Аспаз көмекшісі",
        lvl_3: "Кіші аспаз",
        lvl_4: "Сенімді аспаз",
        lvl_5: "Су-шеф",
        lvl_6: "Шеф-аспаз",
        lvl_7: "Дәм шебері",
        lvl_8: "Мишлен жұлдызы",
        lvl_9: "Аңызға айналған шеф",
        lvl_10: "Ас үй құдайы",
        xp_points: "Ұпайлар (XP):",
        welcome_chef: [
            "Сәлеметсіз бе, ",
            "Сізді көргеніме қуаныштымын, ",
            "Ас үйге қош келдіңіз, ",
            "Армысыз, "
        ],
        chat_prompt: [
            "Бүгін не пісіреміз?",
            "Қандай рецепт іздеп жүрсіз?",
            "Ас үйде не істейміз?",
            "Кулинарлық шедеврге дайынсыз ба?"
        ],
        input_placeholder: "Ингредиенттерді немесе тағам атауын жазыңыз...",
        ai_disclaimer: "Қандай да бір өнімдерге аллергияңыз болса, көрсетуіңізді сұраймыз.",
        logout_btn: "Шығу",

        // Экран Готовки (Статика)
        camera_title: "Камера",
        camera_active: "Белсенді",
        camera_placeholder: "Мұнда камерадан видео болады\n(ML MediaPipe)",
        recognized_gesture: "Танылған қимыл",
        gesture_waiting: "Күтілуде...",
        end_cooking_btn: "Пісіруді аяқтау",
        alice_connect: "🎙 Алисаны қосу",
        alice_connected: "✓ Алиса қосылды",
        alice_helper: "Таймерді Яндекс Станция арқылы дауыспен басқарыңыз",
        alice_active: "Алиса қосылды — дауыспен басқару белсенді",
        alice_checking: "Алиса қосылымы тексерілуде…",
        alice_expired: "Қосылым мерзімі аяқталды — Алисаны қайта қосыңыз",
        alice_creating: "Қосылу коды жасалуда…",
        alice_pair_steps: "1. «Алиса, Умный шеф дағдысын іске қос» деңіз. 2. Кодты атаңыз:",
        alice_stopped: "Алиса таймерді тоқтатты",
        alice_started_step: "Алиса қадам таймерін іске қосты",
        alice_started_custom: "Алиса таймерді {seconds} секундқа іске қосты",
        alice_wrong_time: "Уақыт дұрыс емес. Бұл қадамға {seconds} секунд қажет.",
        alice_backend_error: "Қосылу мүмкін болмады. Backend-ті тексеріңіз.",
        alice_time_up: "⏰ Уақыт бітті — «таймерді тоқтат» деңіз немесе ашық алақан көрсетіңіз",
        ml_loading: "Жасанды интеллект жүктелуде...",
        ml_camera_starting: "Камера іске қосылуда...",
        ml_camera_ready: "Камера дайын!",
        ml_camera_error: "Камераға қол жеткізу қатесі",
        ml_gesture_unknown: "Қимыл танылмады! Анық қимыл жасаңыз.",
        ml_gesture_like: "👍 Лайк (Алға)",
        ml_gesture_dislike: "👎 Дизлайк (Артқа)",
        ml_gesture_peace: "✌️ Бастау (Peace)",
        ml_gesture_palm: "✋ Тоқтату (Ашық алақан)",
        ml_error_peace: "Саусақтар бір-біріне тым жақын!",
        ml_error_thumb: "Лайк жасау үшін саусақтар бүгілмеген",
        btn_prev: "← Артқа (Оңға сырғыту)",
        btn_next: "Алға (Солға сырғыту) →",
        
        // Динамика
        step_word: "Қадам",
        recipe_loading: "ЖИ рецепт дайындап жатыр...",
        recipe_not_ready: "Рецепт әлі жүктелмеді",
        recipe_wait: "Күте тұрыңыз немесе серверді тексеріңіз",
        recipe_empty: "Бос рецепт",
        recipe_no_steps: "Қадамдар жоқ.",
        recipe_ingredients: "Ингредиенттер",
        recipe_not_specified: "Көрсетілмеген",
        recipe_time: "Уақыт",
        recipe_minutes: "мин",
        recipe_servings: "Порция саны",
        recipe_generated: "ЖИ жасаған рецепт. Кітаптағы қадамдар:",
        recipe_server_error: "Сервер қатесі (бэкенд іске қосылғанын тексеріңіз)",
        recipe_system_error: "Жүйелік қате",
        out_of: "/",
        mock_recipe_title: "Генерацияланған рецепт",
        mock_recipe_li1: "Балғын ингредиенттер дайын",
        mock_recipe_li2: "Пісіру уақыты: ~25 мин",
        mock_recipe_btn: "Дайын (Рецепті қабылдау)"
    }
};

// Главная функция перевода страницы
window.changeLanguage = function(lang) {
    if (!window.translations[lang]) lang = 'ru';
    localStorage.setItem('chefLang', lang);
    document.documentElement.lang = lang;
    
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.remove('bg-white', 'shadow-sm', 'text-claude-text');
        btn.classList.add('text-gray-500');
    });
    
    const activeBtn = document.getElementById(`btn-lang-${lang}`);
    if (activeBtn) {
        activeBtn.classList.remove('text-gray-500');
        activeBtn.classList.add('bg-white', 'shadow-sm', 'text-claude-text');
    }

    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (window.translations[lang] && window.translations[lang][key]) {
            let text = window.translations[lang][key];
            if (Array.isArray(text)) {
                if (!window.activeRandomPhrases) window.activeRandomPhrases = {};
                
                // If it's already selected and we're just switching languages, keep the same index if possible
                if (window.activeRandomPhrases[key] !== undefined && window.activeRandomPhrases[key] < text.length) {
                    text = text[window.activeRandomPhrases[key]];
                } else {
                    const idx = Math.floor(Math.random() * text.length);
                    window.activeRandomPhrases[key] = idx;
                    text = text[idx];
                }
            }
            
            if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
                element.setAttribute('placeholder', text);
            } else if (element.tagName === 'SPAN' && element.id !== 'user-name-display') {
                 // For welcome_chef we need to avoid overwriting the child elements if any, but in our HTML it's a separate span!
                 element.innerText = text;
            } else {
                element.innerText = text;
            }
        }
    });

    // Если мы на экране готовки, обновляем счетчик шагов
    if (typeof updateRecipeUI === 'function' && !document.getElementById('screen-cooking').classList.contains('hidden')) {
        updateRecipeUI();
    }

    if (window.YandexAlice) window.YandexAlice.refreshLanguage();
    
    // Обновляем сайдбар достижений, если он открыт
    const achieveSidebar = document.getElementById('achieve-sidebar');
    if (achieveSidebar && typeof renderAchieveSidebar === 'function' && !achieveSidebar.classList.contains('-translate-x-full')) {
        renderAchieveSidebar();
    }

}

document.addEventListener('DOMContentLoaded', () => {
    let savedLang = localStorage.getItem('chefLang');
    if (!savedLang || !translations[savedLang]) {
        const browserLang = navigator.language.slice(0, 2);
        savedLang = translations[browserLang] ? browserLang : 'ru';
    }
    changeLanguage(savedLang);
});


window.reshuffleDynamicGreetings = function() {
    window.activeRandomPhrases = {};
    const lang = localStorage.getItem('chefLang') || 'ru';
    changeLanguage(lang);
};

window.t = function(key) {
    const lang = localStorage.getItem('chefLang') || 'ru';
    return (window.translations[lang] && window.translations[lang][key]) ? window.translations[lang][key] : key;
};
