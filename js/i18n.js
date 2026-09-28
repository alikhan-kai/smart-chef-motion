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
        xp_points: "Очки (XP):",
        welcome_chef: "Здравствуйте, ",
        chat_prompt: "Что мы будем готовить сегодня?",
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
        btn_prev: "← Назад (Свайп вправо)",
        btn_next: "Далее (Свайп влево) →",
        
        // Динамика
        step_word: "Шаг",
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
        xp_points: "Points (XP):",
        welcome_chef: "Hello, ",
        chat_prompt: "What are we cooking today?",
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
        btn_prev: "← Prev (Swipe Right)",
        btn_next: "Next (Swipe Left) →",
        
        // Динамика
        step_word: "Step",
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
        xp_points: "Ұпайлар (XP):",
        welcome_chef: "Сәлеметсіз бе, ",
        chat_prompt: "Бүгін не пісіреміз?",
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
        btn_prev: "← Артқа (Оңға сырғыту)",
        btn_next: "Алға (Солға сырғыту) →",
        
        // Динамика
        step_word: "Қадам",
        out_of: "/",
        mock_recipe_title: "Генерацияланған рецепт",
        mock_recipe_li1: "Балғын ингредиенттер дайын",
        mock_recipe_li2: "Пісіру уақыты: ~25 мин",
        mock_recipe_btn: "Дайын (Рецепті қабылдау)"
    }
};

// Главная функция перевода страницы
window.changeLanguage = function(lang) {
    localStorage.setItem('chefLang', lang);
    
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
            if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
                element.setAttribute('placeholder', window.translations[lang][key]);
            } else {
                element.innerText = window.translations[lang][key];
            }
        }
    });

    // Если мы на экране готовки, обновляем счетчик шагов
    if (typeof updateRecipeUI === 'function' && !document.getElementById('screen-cooking').classList.contains('hidden')) {
        updateRecipeUI();
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
