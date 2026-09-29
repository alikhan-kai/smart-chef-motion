# Hackathon Docker setup

This stack runs the final main UI and the **root-level backend** containing the
recipe-magazine features and ingredient-ID fixes. It uses root `backend/`,
`llm/`, `pyproject.toml`, and `uv.lock`. The separate `recipe-ai-backend/` tree
contains an earlier LangChain variant without the magazine routes; it is not
built here. `hand-tracking-sandbox/` is also excluded.

Docker Engine/Desktop and Docker Compose v2 are required. OpenAI, Supabase, and
the browser's CDN/model downloads still require internet access.

## First run

Run all commands from the repository root. Create `.env` only if it is missing:

```bash
test -f .env || cp .env.example .env
```

Edit **root `.env`** with a real `OPENAI_API_KEY` and the team's chosen
`OPENAI_MODEL`. The selected backend uses the OpenAI SDK and `OPENAI_*` settings;
the `LLM_*` variables from the nested LangChain variant do not configure it.
Keep `.env` local: Git ignores it, both image contexts exclude it, and Compose
injects its values into the backend at container startup.

For a test using in-memory recipe-book/magazine storage, leave `SUPABASE_URL`
and `SUPABASE_SERVICE_KEY` empty. To test persistent storage, have the database
owner apply the SQL in `docs/recipe_magazine_contract.md` once, then configure
both settings in root `.env`. The service key is backend-only; do not put it in
`js/config.js`. Frontend login/history still uses the existing Supabase project
even when backend persistence is disabled.

Ports **8000 and 8080 must be free** for the default local port bindings.

```bash
docker compose up --build -d --wait
docker compose ps
```

- Frontend: http://localhost:8080
- Backend API docs: http://localhost:8000/docs

Published ports bind to loopback, and camera access works on localhost. In Docker,
the browser uses relative `/api` URLs on the frontend's origin. Nginx forwards
them to the backend and strips `/api`, so the same images work behind an HTTPS
domain without hardcoding hostnames or adding cross-origin CORS rules.
Without Docker, `js/api-config.js` keeps the existing localhost:8000 behavior.
The frontend image copies only `index.html`, `favicon.png`, `css/`, and `js/`,
including the final `js/magazine.js`. The backend image runs as a non-root user
and includes the prompt/schema assets. `Dockerfile.backend.dockerignore` gives
the backend its own allowlist instead of the frontend's root `.dockerignore`.
Both services use `restart: unless-stopped`. Enable Docker at boot on the server;
containers intentionally stopped with `docker compose down` stay stopped.

## Automated smoke check

After the stack is healthy, run the read-only check with Python 3:

```bash
python3 scripts/smoke_docker.py
```

It verifies local assets, JavaScript MIME types, the magazine routes in OpenAPI,
chat/book/magazine list endpoints through `/api`, localhost CORS, and that secret/repository
paths are not served. It does not generate recipes, modify data, or validate
camera access. If Supabase persistence is configured, list requests do read it.

For startup checks without a real API key, explicitly use the example file:

```bash
BACKEND_ENV_FILE=./.env.example docker compose up --build -d --wait
python3 scripts/smoke_docker.py
```

Recipe generation fails with the example's placeholder key. Run the normal
Compose command after setting the real `.env`; it will recreate the backend
with the updated environment. A healthy container alone does not prove model
access or Supabase schema readiness.

For the existing automated backend suite, use Python 3.12 and uv from the root:

```bash
uv sync --frozen --extra dev
OPENAI_API_KEY=sk-test OPENAI_MODEL=gpt-test SUPABASE_URL= SUPABASE_SERVICE_KEY= \
  uv run --frozen --extra dev pytest -q
```

These are mocked tests. Dummy model/key settings are required by two revision
tests; empty Supabase settings force isolated in-memory repositories.

## Demo test sequence

1. Log in using a disposable demo account.
2. Generate a recipe and request a revision. These steps use the paid API.
3. Confirm it, check recipe history, and enter cooking mode.
4. Allow the camera; test next/previous gestures, timer start/stop, and exit.
5. Create a magazine, add the recipe, upload a cover, and publish it.
6. Search for it in the market; test both sorting options.
7. With a second demo user, view it, save a recipe with attribution, and cook it.
8. If testing persistence, restart the backend and verify the book/magazines
   remain. Chats themselves are always in memory and will reset.

## Everyday commands

```bash
# Follow logs; Ctrl+C stops following, not the containers.
docker compose logs -f --tail=100

# Rebuild after pulling changes; sources are copied into the images.
docker compose up --build -d --wait

# Restart the backend (loses its in-memory state).
docker compose restart backend

# Stop and remove this stack's containers/network.
docker compose down
```

Use the same `BACKEND_ENV_FILE` override on later Compose commands if you used
one for startup and root `.env` does not exist. Keep one backend instance and
one worker. Without Supabase settings, restarting also clears backend recipe
books and magazines. Data separately saved by the frontend in Supabase is not
removed by Compose.

## Troubleshooting

- **Missing `.env`:** use the root file, not `recipe-ai-backend/.env`.
  `docker compose config --quiet` validates without printing secret values.
- **Port already allocated:** inspect `docker ps` and stop your previous demo
  server if appropriate. Do not stop an unrelated service. Changing only the
  frontend's published port works with Docker's relative `/api` URLs; it does
  not change the non-Docker development configuration.
- **Magazine requests return 404:** verify `/recipe-magazines` exists at
  `/openapi.json`. Rebuild this root-backend image; the nested backend is older.
- **Backend unhealthy:** inspect `docker compose logs --tail=100 backend`.
- **Recipe generation fails:** check model access, API credentials, billing,
  timeout settings, and the backend logs.
- **Persistence fails:** check that the documented Supabase tables/function
  exist and that the backend has the service key rather than a publishable key.
- **Camera/model fails:** use localhost, allow camera permission, and check
  access to jsDelivr and Google-hosted MediaPipe assets.

## EC2 and Cloudflare Tunnel

1. Use an EC2 Linux instance with Docker Engine and Compose v2 installed. Enable
   Docker on boot: `sudo systemctl enable --now docker`.
2. Clone the reviewed branch/release, create root `.env` on the server, and
   configure the credentials as above. Never copy `.env` into Git or the image.
3. Build and start the images with a release tag (see below), then smoke-test.
4. Install `cloudflared` on the EC2 host using the command from the Cloudflare
   dashboard, and run it as a system service. Keep its tunnel token private.
5. Add one published application route: your hostname (for example,
   `chef.example.com`) -> `http://localhost:8080`. Since cloudflared runs on the
   host, it can reach Compose's loopback-bound port. No separate API domain is
   required: requests and magazine cover uploads use the same-origin `/api` path.
6. Test using `https://chef.example.com`, including camera access and a real
   recipe request. The proxy accepts cover uploads up to 10 MB.

EC2 needs outbound access for package downloads, OpenAI, Supabase, and Cloudflare
Tunnel. The application ports do not need public inbound access with this setup.
Configure your chosen SSH/management access separately. If cloudflared instead
runs in a container, `localhost:8080` is not the app host; attach it to the Compose
network and route it to `http://frontend:80`.

## Updating and rolling back

Build each release with a new tag, such as its Git commit hash. Keep the previous
images on the EC2 host; do not prune them during the hackathon.

```bash
# On the server, while on the reviewed deployment branch:
git pull --ff-only
export IMAGE_TAG=$(git rev-parse --short HEAD)
docker compose build
docker compose up -d --no-build --pull never --wait
python3 scripts/smoke_docker.py
```

Building happens while the existing containers are still running. Switching
containers may cause brief downtime; this is a single-instance demo deployment.
Record the successful IMAGE_TAG so the previous release is easy to identify.

For a code-only update with compatible Compose/environment configuration, return
to the previous image pair without rebuilding (replace `previous-commit`):

```bash
export IMAGE_TAG=previous-commit
docker compose up -d --no-build --pull never --wait
python3 scripts/smoke_docker.py
```

This restores application code, not database contents or previous environment
values. If a release changes Compose configuration or a database schema, review
those changes before rolling back. Backend replacement resets chats and any
journals/book data still in memory; Supabase-persisted data survives it.

Nginx resolves the backend through Docker DNS so backend replacement can recover
without rebuilding the frontend. The static UI uses `Cache-Control: no-store`
to pick up a new release on browser reload. Avoid Cloudflare rules that force
caching of `/api/*` or override this demo cache policy.
