#!/usr/bin/env python3
"""
Meiko CLI — talk to your Meiko agent server from the terminal.

Usage:
  python meiko_cli.py chat "What's the weather like in Tokyo?"
  python meiko_cli.py chat --mode research "Latest news on fusion energy"
  python meiko_cli.py --server http://localhost:8000 --user alice chat "hi"
  python meiko_cli.py repl                     # interactive chat loop
  python meiko_cli.py providers                # list available model providers
  python meiko_cli.py modes                    # list agent modes
  python meiko_cli.py set-key nvidia sk-xxxx    # store an API key server-side
  python meiko_cli.py download <session_id> <filename> -o out.zip

Works with zero install beyond `pip install httpx rich` (rich is optional,
falls back to plain text if not installed).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

try:
    from rich.console import Console
    from rich.markdown import Markdown
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None


def out(text: str, style: str = "") -> None:
    if HAS_RICH:
        console.print(text, style=style or None)
    else:
        print(text)


def print_markdown(text: str) -> None:
    if HAS_RICH:
        console.print(Markdown(text))
    else:
        print(text)


class MeikoClient:
    def __init__(self, server: str, user_id: str, api_key: str | None = None):
        self.server = server.rstrip("/")
        self.user_id = user_id
        self.headers = {"X-API-Key": api_key} if api_key else {}

    def chat_stream(self, message: str, mode: str = "autonomous", conversation_id: str | None = None, provider: str | None = None, model: str | None = None):
        payload = {
            "user_id": self.user_id,
            "message": message,
            "mode": mode,
            "conversation_id": conversation_id,
            "provider": provider,
            "model": model,
        }
        with httpx.stream("POST", f"{self.server}/api/chat/stream", json=payload, headers=self.headers, timeout=180) as resp:
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if not data:
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue

    def get(self, path: str):
        resp = httpx.get(f"{self.server}{path}", headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, payload: dict):
        resp = httpx.post(f"{self.server}{path}", json=payload, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def download(self, session_id: str, filename: str, out_path: str):
        with httpx.stream("GET", f"{self.server}/api/download/{session_id}/{filename}", headers=self.headers, timeout=60) as resp:
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)


def cmd_chat(client: MeikoClient, args) -> None:
    conv_id = args.conversation
    out(f"[bold cyan]You:[/] {args.message}" if HAS_RICH else f"You: {args.message}")
    out("[bold magenta]Meiko:[/]" if HAS_RICH else "Meiko:")
    buffer = ""
    for event in client.chat_stream(args.message, mode=args.mode, conversation_id=conv_id, provider=args.provider, model=args.model):
        etype = event.get("type")
        if etype == "token":
            print(event["text"], end="", flush=True)
            buffer += event["text"]
        elif etype == "tool_call":
            print()
            out(f"  🔧 calling tool: {event['name']}({json.dumps(event.get('arguments', {}))})", style="yellow")
        elif etype == "tool_result":
            preview = event.get("result", "")[:200]
            out(f"  ↳ result: {preview}", style="green")
        elif etype == "error":
            out(f"\n[Error] {event.get('message')}", style="red")
        elif etype == "final":
            print()
        elif etype == "done":
            if not conv_id:
                out(f"\n(conversation_id: {event.get('conversation_id')})", style="dim")


def cmd_repl(client: MeikoClient, args) -> None:
    out("Meiko CLI REPL — type 'exit' to quit, '/mode <name>' to switch modes.\n")
    mode = args.mode
    conv_id = None
    while True:
        try:
            msg = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not msg:
            continue
        if msg.lower() in ("exit", "quit"):
            break
        if msg.startswith("/mode "):
            mode = msg.split(" ", 1)[1].strip()
            out(f"Switched to mode: {mode}")
            continue
        print("meiko> ", end="")
        for event in client.chat_stream(msg, mode=mode, conversation_id=conv_id):
            if event.get("type") == "token":
                print(event["text"], end="", flush=True)
            elif event.get("type") == "tool_call":
                out(f"\n  🔧 {event['name']}(...)", style="yellow")
            elif event.get("type") == "done":
                conv_id = event.get("conversation_id")
        print("\n")


def cmd_providers(client: MeikoClient, args) -> None:
    for p in client.get("/api/providers"):
        tag = " (free)" if p.get("free_tier") else ""
        out(f"- {p['id']}: {p['display_name']}{tag} — {p['description']}")


def cmd_modes(client: MeikoClient, args) -> None:
    for m in client.get("/api/modes"):
        out(f"- {m['id']}: {m['name']} — {m['description']}")


def cmd_set_key(client: MeikoClient, args) -> None:
    resp = client.post("/api/settings", {"user_id": client.user_id, "api_keys": {args.provider: args.key}})
    out(f"Saved key for {args.provider}: {resp}")


def cmd_download(client: MeikoClient, args) -> None:
    client.download(args.session_id, args.filename, args.output or args.filename)
    out(f"Downloaded to {args.output or args.filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Meiko Agent CLI")
    parser.add_argument("--server", default=os.environ.get("MEIKO_SERVER", "http://localhost:8000"))
    parser.add_argument("--user", default=os.environ.get("MEIKO_USER", "cli-user"))
    parser.add_argument("--api-key", default=os.environ.get("MEIKO_API_KEY"))

    sub = parser.add_subparsers(dest="command", required=True)

    p_chat = sub.add_parser("chat", help="Send a single message")
    p_chat.add_argument("message")
    p_chat.add_argument("--mode", default="autonomous")
    p_chat.add_argument("--conversation", default=None)
    p_chat.add_argument("--provider", default=None)
    p_chat.add_argument("--model", default=None)
    p_chat.set_defaults(func=cmd_chat)

    p_repl = sub.add_parser("repl", help="Interactive chat loop")
    p_repl.add_argument("--mode", default="autonomous")
    p_repl.set_defaults(func=cmd_repl)

    p_providers = sub.add_parser("providers", help="List model providers")
    p_providers.set_defaults(func=cmd_providers)

    p_modes = sub.add_parser("modes", help="List agent modes")
    p_modes.set_defaults(func=cmd_modes)

    p_setkey = sub.add_parser("set-key", help="Store a provider API key server-side")
    p_setkey.add_argument("provider")
    p_setkey.add_argument("key")
    p_setkey.set_defaults(func=cmd_set_key)

    p_download = sub.add_parser("download", help="Download a generated file")
    p_download.add_argument("session_id")
    p_download.add_argument("filename")
    p_download.add_argument("-o", "--output", default=None)
    p_download.set_defaults(func=cmd_download)

    args = parser.parse_args()
    client = MeikoClient(args.server, args.user, args.api_key)
    try:
        args.func(client, args)
    except httpx.HTTPStatusError as e:
        out(f"HTTP error: {e.response.status_code} {e.response.text[:300]}", style="red")
        sys.exit(1)
    except httpx.ConnectError:
        out(f"Could not connect to Meiko server at {args.server}. Is it running?", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
