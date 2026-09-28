// Настройки базы данных Supabase
const SUPABASE_URL = 'https://ytyjvmcfwkqnkzeodtnn.supabase.co'; // Достал из твоей ссылки
const SUPABASE_ANON_KEY = 'sb_publishable_6cZSm8qw7KyTnTZwQEzudQ_7TsPQD8k';

// Инициализация клиента Supabase (Доступен глобально для всех скриптов)
const supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
