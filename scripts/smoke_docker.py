"""Read-only HTTP checks for the local Docker demo; Python standard library only."""

import argparse
import json
from email.message import Message
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class Assets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paths: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        path = None
        if tag == "script":
            path = attributes.get("src")
        elif tag == "link":
            path = attributes.get("href")
        if path and not urlparse(path).netloc and not urlparse(path).scheme:
            self.paths.add(path)


def request(
    url: str,
    status: int = 200,
    headers: dict[str, str] | None = None,
    method: str = "GET",
) -> tuple[bytes, Message]:
    try:
        response = urlopen(Request(url, headers=headers or {}, method=method), timeout=10)
    except HTTPError as error:
        response = error
    with response:
        if response.status != status:
            raise RuntimeError(f"{method} {url}: expected {status}, got {response.status}")
        return response.read(), response.headers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-url", default="http://localhost:8080")
    parser.add_argument("--backend-url", help="Defaults to the frontend's /api proxy")
    args = parser.parse_args()
    frontend = args.frontend_url.rstrip("/")
    backend = (args.backend_url or frontend + "/api").rstrip("/")

    page, _ = request(frontend + "/")
    page_text = page.decode("utf-8")
    assets = Assets()
    assets.feed(page_text)
    config_position = page_text.find('src="js/api-config.js"')
    if config_position < 0 or any(
        page_text.find(f'src="{path}"') <= config_position
        for path in ("js/ui.js", "js/magazine.js")
    ):
        raise RuntimeError("API configuration must load before its consumers")
    config, _ = request(frontend + "/js/api-config.js")
    if "window.CHEF_API_BASE = '/api';" not in config.decode("utf-8"):
        raise RuntimeError("Docker frontend must use same-origin /api")
    if "js/magazine.js" not in assets.paths:
        raise RuntimeError("Frontend does not load the final magazine script")
    assets.paths.add("js/ml.js")  # Dynamically imported by cooking mode.
    for path in sorted(assets.paths):
        _, headers = request(urljoin(frontend + "/", path))
        if path.endswith(".js") and "javascript" not in headers.get("Content-Type", ""):
            raise RuntimeError(f"{path}: incorrect JavaScript MIME type")
    print(f"PASS frontend and {len(assets.paths)} local assets")

    for path in ("/.env", "/.git/config", "/backend/main.py", "/recipe-ai-backend/.env"):
        request(frontend + path, status=404)
    print("PASS repository and environment paths excluded")

    schema, _ = request(backend + "/openapi.json")
    paths = json.loads(schema)["paths"]
    for path in ("/chats", "/recipe-book", "/recipe-magazines", "/recipe-magazines/market"):
        if path not in paths:
            raise RuntimeError(f"Backend missing {path}; rebuild the root backend")
        request_headers = {} if path.endswith("/market") else {"X-User-Id": "docker-smoke"}
        body, _ = request(backend + path, headers=request_headers)
        if not isinstance(json.loads(body), list):
            raise RuntimeError(f"{path}: expected a list response")
    request(backend + "/chats", status=422)
    print("PASS backend routes, list endpoints, and required user header")

    origin = "http://localhost:8080"
    _, headers = request(
        backend + "/chats",
        method="OPTIONS",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-user-id",
        },
    )
    if headers.get("Access-Control-Allow-Origin") != origin:
        raise RuntimeError("Backend CORS does not permit the demo frontend")
    print("PASS localhost CORS; no model calls or data writes performed")


if __name__ == "__main__":
    main()
