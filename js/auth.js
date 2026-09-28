// Элементы форм
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const toRegisterBtn = document.getElementById('to-register');
const toLoginBtn = document.getElementById('to-login');

// Экраны
const screenAuth = document.getElementById('screen-auth');
const screenChat = document.getElementById('screen-chat');
const userNameDisplay = document.getElementById('user-name-display');

// ==========================================
// 1. АНИМАЦИИ ПЕРЕКЛЮЧЕНИЯ ФОРМ И ОЧИСТКА
// ==========================================

function clearForms() {
    loginForm.reset();
    registerForm.reset();
}

toRegisterBtn.addEventListener('click', (e) => {
    e.preventDefault();
    clearForms();
    
    // Прячем логин (уезжает влево)
    loginForm.classList.add('opacity-0', 'pointer-events-none', '-translate-x-8');
    loginForm.classList.remove('relative');
    loginForm.classList.add('absolute');
    
    // Показываем регистрацию (приезжает справа)
    registerForm.classList.remove('opacity-0', 'pointer-events-none', 'translate-x-8');
    registerForm.classList.remove('absolute');
    registerForm.classList.add('relative');
});

toLoginBtn.addEventListener('click', (e) => {
    e.preventDefault();
    clearForms();
    
    // Прячем регистрацию
    registerForm.classList.add('opacity-0', 'pointer-events-none', 'translate-x-8');
    registerForm.classList.remove('relative');
    registerForm.classList.add('absolute');
    
    // Показываем логин
    loginForm.classList.remove('opacity-0', 'pointer-events-none', '-translate-x-8');
    loginForm.classList.remove('absolute');
    loginForm.classList.add('relative');
});

// ==========================================
// 2. ПОКАЗАТЬ/СКРЫТЬ ПАРОЛЬ (ГЛАЗИК)
// ==========================================

document.querySelectorAll('.toggle-password').forEach(button => {
    button.addEventListener('click', function() {
        const input = this.previousElementSibling;
        const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
        input.setAttribute('type', type);
        
        // Меняем цвет глазика, когда пароль видно
        if (type === 'text') {
            this.classList.add('text-claude-accent');
            this.classList.remove('text-gray-400');
        } else {
            this.classList.remove('text-claude-accent');
            this.classList.add('text-gray-400');
        }
    });
});

// ==========================================
// 3. РАБОТА С БАЗОЙ ДАННЫХ SUPABASE
// ==========================================

function fakeHash(password) {
    return btoa(password + "salt123");
}

// ВХОД
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    
    const btn = loginForm.querySelector('button');
    const originalText = btn.innerText;
    btn.innerText = 'Проверка данных...';
    btn.disabled = true;

    const { data, error } = await supabaseClient
        .from('users')
        .select('*')
        .eq('login', email)
        .eq('password_hash', fakeHash(password));

    if (error) {
        alert("Ошибка БД: " + error.message);
        btn.innerText = originalText;
        btn.disabled = false;
        return;
    }

    if (data && data.length > 0) {
        const user = data[0];
        loginUser(user.login, user.user_id, user.points);
    } else {
        alert("Неверный email или пароль!");
    }
    
    btn.innerText = originalText;
    btn.disabled = false;
});

// РЕГИСТРАЦИЯ
registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    
    const btn = registerForm.querySelector('button');
    const originalText = btn.innerText;
    btn.innerText = 'Создаем аккаунт...';
    btn.disabled = true;

    const { data, error } = await supabaseClient
        .from('users')
        .insert([
            { login: email, password_hash: fakeHash(password), points: 0 }
        ])
        .select();

    if (error) {
        // Ловим ошибку дубликата от Postgres (Код 23505)
        if (error.code === '23505' || error.message.includes('duplicate key')) {
            alert("Пользователь с таким Email уже существует! Пожалуйста, перейдите на вкладку входа.");
        } else {
            alert("Ошибка регистрации: " + error.message);
        }
    } else if (data && data.length > 0) {
        const newUser = data[0];
        // Для простоты подставляем имя как логин при регистрации
        loginUser(name, newUser.user_id, newUser.points);
    }

    btn.innerText = originalText;
    btn.disabled = false;
});

// УСПЕШНЫЙ ВХОД
function loginUser(name, userId, points) {
    localStorage.setItem('chefName', name);
    localStorage.setItem('chefId', userId);
    localStorage.setItem('chefPoints', points);
    
    // Красивое приветствие без очков
    userNameDisplay.innerText = name;
    
    // Обновляем очки в боковом меню
    const pointsDisplay = document.getElementById('user-points-display');
    if (pointsDisplay) pointsDisplay.innerText = points || 0;

    // Очищаем формы, чтобы при выходе они были пустыми
    clearForms();

    screenAuth.classList.add('opacity-0');
    setTimeout(() => {
        screenAuth.classList.add('hidden');
        screenChat.classList.remove('hidden');
        
        screenChat.style.opacity = '0';
        setTimeout(() => {
            screenChat.style.transition = 'opacity 0.5s ease';
            screenChat.style.opacity = '1';
        }, 50);
    }, 500);
}

// ВЫХОД
window.logout = function() {
    localStorage.removeItem('chefName');
    localStorage.removeItem('chefId');
    localStorage.removeItem('chefPoints');
    
    screenChat.classList.add('hidden');
    screenAuth.classList.remove('hidden');
    
    setTimeout(() => {
        screenAuth.classList.remove('opacity-0');
    }, 50);
};

// Проверка при загрузке страницы
window.addEventListener('DOMContentLoaded', () => {
    const savedName = localStorage.getItem('chefName');
    const savedPoints = localStorage.getItem('chefPoints');
    if (savedName) {
        screenAuth.classList.add('hidden');
        screenChat.classList.remove('hidden');
        
        userNameDisplay.innerText = savedName;
        const pointsDisplay = document.getElementById('user-points-display');
        if (pointsDisplay) pointsDisplay.innerText = savedPoints || 0;
    }
});
