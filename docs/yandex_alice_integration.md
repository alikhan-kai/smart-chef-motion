# Yandex Station / Alice timer integration

Smart Chef exposes a Yandex Dialogs webhook that lets an Alice custom skill
control the timer in the open cooking page. The Station receives the voice
command; the Smart Chef browser owns the countdown and alarm.

## What works

- `запусти таймер` — starts the current recipe-step timer;
- `поставь таймер на 5 минут` — replaces the displayed duration and starts it;
- combined durations such as `таймер на 2 минуты 30 секунд`;
- `останови таймер` / `стоп таймер` — stops the countdown;
- one-time six-digit pairing between a Station and a browser session.

## Create the Alice skill

1. Deploy Smart Chef at a public HTTPS address. Yandex Dialogs cannot call a
   localhost URL and requires a valid TLS certificate.
2. In the [Yandex Dialogs developer console](https://dialogs.yandex.ru/developer/),
   create an Alice skill. A suggested activation name is `Умный шеф`; the final
   name depends on Yandex availability and moderation.
3. Set its Webhook URL:
   - Docker/nginx deployment: `https://YOUR_DOMAIN/api/integrations/yandex-alice/webhook`
   - backend exposed directly: `https://YOUR_API_DOMAIN/integrations/yandex-alice/webhook`
4. Copy the skill id from its overview into the backend environment:

   ```env
   YANDEX_ALICE_SKILL_ID=your-skill-id
   ```

   This validation is optional for local console testing but recommended on a
   public deployment.
5. Test the skill in the Dialogs console, then publish it as a private skill.
   To use a private skill on a Station, use the same Yandex account and the
   approved activation name.

## Pair and use

1. Open a recipe and enter cooking mode.
2. Click **Подключить Алису**. Smart Chef displays a code for ten minutes.
3. Say: `Алиса, запусти навык Умный шеф`.
4. Say: `код 123456`, using the displayed digits.
5. The button turns green and reads **Алиса подключена** when pairing succeeds.
6. While the skill is active, say a timer command. If the Alice skill session
   has timed out, invoke the skill again; the pairing remains in place while the
   backend process is running.
7. To move the browser session from the Dialogs test console or an old Station
   to another real Station, click the discreet **Reconnect another Station**
   action below the connected status and say the newly generated code on that
   Station. No browser storage cleanup or backend restart is required.

The webhook and private-skill setup are performed once by the Smart Chef
developer. A regular user only opens cooking mode, presses the connection
button, invokes the skill, and reads the displayed code. Removing the code
entirely requires the separate OAuth account-linking architecture described
below.

## Recipe timer validation

For every recipe step, the browser publishes the expected timer duration to the
Alice bridge. If the recipe says 20 minutes and the user asks Alice for 10,
Alice rejects the command, tells the user that the step needs 20 minutes, and
does not change or start the browser timer. The browser repeats the same check
defensively before applying a command. On a step that has no recipe timer, the
user may create an arbitrary timer by voice.

## API summary

- `POST /integrations/yandex-alice/pairings` creates a short-lived code and an
  opaque browser token.
- `POST /integrations/yandex-alice/webhook` is the Yandex Dialogs webhook.
- `GET /integrations/yandex-alice/commands?connection_token=...&after=...` lets
  the cooking page fetch commands once using an id cursor.
- `POST /integrations/yandex-alice/expected-timer` synchronizes the current
  recipe step's required duration for voice-command validation.

## MVP limitations

- This uses process memory and therefore requires one backend worker. Pairings
  disappear on restart. Move the connection and command records to Redis or
  another shared store before horizontal scaling.
- It starts Smart Chef's timer, not the Station's built-in system timer. Yandex
  Dialogs provides a skill webhook, but no supported directive for a third-party
  skill to create the Station's native timer.
- The browser page must stay open and online to receive a command and sound the
  alarm. Polling latency is normally up to one second.

## Production account-linking path

The pairing code is deliberately the shortest MVP and is similar to pairing a
TV or Spotify client: end users do not configure the webhook or developer
console. For a code-free production experience, Smart Chef would need to become
an OAuth 2.0 authorization server for Alice account linking, offer Yandex ID as
an app login method, persist the Alice-to-Smart-Chef account mapping, and store
timer commands in a shared database. This is a separate authentication feature,
not just a frontend “Login with Yandex” button; Alice's skill-scoped user id
must not be assumed to equal the public Yandex ID account id.
