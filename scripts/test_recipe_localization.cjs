// Run with: node --test scripts/test_recipe_localization.cjs
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

function app(language) {
    const ready = [];
    const elements = new Map();
    const store = new Map([['chefLang', language]]);
    const messages = [];
    const requests = [];
    const context = vm.createContext({
        console, setTimeout() {},
        navigator: { language: 'en-US' },
        localStorage: {
            getItem: key => store.get(key) || null,
            setItem: (key, value) => store.set(key, value)
        },
        document: {
            documentElement: {},
            addEventListener: (event, callback) => ready.push(callback),
            querySelectorAll: () => [],
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, {
                    value: '', style: {}, scrollHeight: 20,
                    classList: { contains: () => true, add() {}, remove() {} },
                    handlers: {}, focus() {},
                    addEventListener(event, callback) { this.handlers[event] = callback; }
                });
                return elements.get(id);
            }
        },
        async fetch(url, options) {
            requests.push({ url, body: JSON.parse(options.body) });
            return { ok: true, async json() {
                return {
                    chat_id: 'test-chat', intent: 'revise',
                    recipe: { title: 'Eggs', servings: 1, total_time_minutes: 10,
                        ingredients: [{ name: 'salt', unit: 'to taste' }],
                        steps: [{ step_number: 1, action: 'Boil the eggs.',
                            place: 'кастрюля', time_minutes: 10 }] }
                };
            } };
        }
    });
    context.window = context;
    for (const file of ['js/i18n.js', 'js/ui.js']) {
        vm.runInContext(readFileSync(resolve(__dirname, '..', file), 'utf8'), context);
    }
    context.appendMessage = text => messages.push(text);
    ready.forEach(callback => callback());
    return { context, elements, messages, requests };
}

for (const language of ['en', 'ru', 'kk']) {
    test(`${language}: selected language reaches generation and revision`, async () => {
        const { context, elements, messages, requests } = app(language);
        const submit = elements.get('chat-form').handlers.submit;
        elements.get('chat-input').value = 'eggs';
        await submit({ preventDefault() {} });
        assert.equal(requests[0].body.language, language);
        assert.equal(requests[0].body.prompt, 'eggs');
        assert.ok(messages[1].includes(context.t('recipe_loading')));
        assert.ok(messages[2].includes(context.t('recipe_ingredients')));
        assert.ok(messages[2].includes(context.t('mock_recipe_btn')));
        assert.equal(context.mockRecipeData[0].title, `${context.t('step_word')} 1`);
        assert.equal(context.mockRecipeData[0].timer, 600);
        if (language === 'en') {
            assert.ok(!/[А-Яа-яЁё]/.test(messages[1] + messages[2]));
            assert.equal(context.mockRecipeData[0].desc, 'Boil the eggs.');
        }
        elements.get('chat-input').value = '2 servings';
        await submit({ preventDefault() {} });
        assert.equal(requests[1].body.language, language);
        assert.ok(requests[1].url.endsWith('/chats/test-chat/messages'));
    });
}

test('generated English headers are preserved, empty recipes are localized', () => {
    const { context } = app('en');
    const steps = context.buildMockRecipeData({ steps: [{
        step_number: 1, header: 'Prepare the eggs', action: 'Crack the eggs.', place: 'миска'
    }] });
    assert.equal(steps[0].title, 'Prepare the eggs');
    assert.equal(context.buildMockRecipeData({ steps: [] })[0].title, 'Empty recipe');
});
