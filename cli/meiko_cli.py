#!/usr/bin/env python3
"""
Meiko CLI — a powerful terminal client for the Meiko Agent backend.

Inspired by hermus-agent-free's (github.com/trmv2007-bot/hermus-agent-free)
command surface — mission tracking, verification, delegation, memory search,
skills, sandboxed code execution — reimplemented on top of Meiko's existing
agent modes, plan tracking, skills system, and tools, rather than duplicating
a second agent runtime. Every command below talks to a real Meiko backend
endpoint; nothing here is a mock.

Usage:
  # Chat / conversation
  meiko chat "What's the weather like in Tokyo?"
  meiko chat --mode research "Latest news on fusion energy"
  meiko repl                                # interactive chat loop
  meiko conversations                       # list your conversations
  meiko conversations search "kerala trip"

  # Mission mode — run a goal through Meiko's autonomous mode with live
  # plan-step tracking printed as it happens (hermus `mission start`)
  meiko mission "Research the top 3 open-source vector databases and write
                 a short comparison to comparison.md"

  # Verification — ask Meiko to sanity-check its own or existing work in a
  # specific domain by running it through Code/Research mode with a
  # verification-flavoured prompt (hermus `verify run --domain`)
  meiko verify python "Does this repo's test suite pass? Run pytest and report."
  meiko verify web "Is the site at https://example.com mobile responsive?"

  # Delegation — fan a goal out across N independent Meiko runs (different
  # modes/providers) and aggregate the results (hermus `delegate --aggregate`)
  meiko delegate "Summarize this week's AI news" --workers research,chat --aggregate synthesize

  # Memory — Meiko's long-term memory store, hybrid-searchable
  meiko memory list
  meiko memory search "favorite programming language"
  meiko memory add "Prefers concise answers"
  meiko memory forget <memory_id>

  # Skills — reusable markdown playbooks the agent can load on demand
  meiko skill list
  meiko skill show pdf-report

  # Connectors / plugins — keyless+keyed external API tools available to the agent
  meiko connectors

  # Providers / models
  meiko providers
  meiko models --provider nvidia
  meiko set-key nvidia nvapi-xxxxxxxxxxxxxxxx

  # Cross-device sync (pair this CLI session to your phone/web account)
  meiko sync pair
  meiko sync claim ABC123
  meiko sync status

  # Usage analytics
  meiko usage

  # Download a file Meiko generated during a session
  meiko download <session_id> <filename> -o out.zip

  # Vibe coding — rapid-prototype a working app/site from a plain idea, and
  # get back a live preview link (bolt.new/v0-style, no local dev server)
  meiko vibe "a pomodoro timer with a dark theme"
  meiko preview <session_id>                # list live preview links for that session

Works with zero install beyond `pip install httpx rich` (rich is optional,
falls back to plain text if not installed).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import uuid
from typing import Any, Optional

import httpx

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.table import Table
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


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if HAS_RICH:
        table = Table(show_header=True, header_style="bold cyan")
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*[str(c) for c in row])
        console.print(table)
    else:
        print(" | ".join(headers))
        for row in rows:
            print(" | ".join(str(c) for c in row))


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------
class MeikoClient:
    def __init__(self, server: str, user_id: str, api_key: Optional[str] = None):
        self.server = server.rstrip("/")
        self.user_id = user_id
        self.headers = {"X-API-Key": api_key} if api_key else {}

    def chat_stream(
        self,
        message: str,
        mode: str = "autonomous",
        conversation_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        payload = {
            "user_id": self.user_id,
            "message": message,
            "mode": mode,
            "conversation_id": conversation_id,
            "provider": provider,
            "model": model,
            "session_id": session_id,
        }
        with httpx.stream("POST", f"{self.server}/api/chat/stream", json=payload, headers=self.headers, timeout=300) as resp:
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if not data:
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue

    def chat_once(self, message: str, mode: str = "autonomous", provider: Optional[str] = None) -> dict[str, Any]:
        """Run a message to completion (no streaming to stdout) and return the
        final text + collected tool calls + citations. Used by mission/verify/
        delegate, which need the finished result rather than a live stream.

        Note: the backend's SSE events flatten AgentEvent.data into the
        top-level JSON object alongside "type" (see AgentEvent.to_sse in
        harness/agent.py) — so fields are read directly off `event`, not
        `event["data"]`.
        """
        final_text = ""
        tool_calls: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        plan: list[dict[str, Any]] = []
        error: Optional[str] = None
        conversation_id = None
        for event in self.chat_stream(message, mode=mode, provider=provider):
            etype = event.get("type")
            if etype == "token":
                final_text += event.get("text", "")
            elif etype == "final" and event.get("text"):
                final_text = event["text"]
            elif etype == "tool_call":
                tool_calls.append(event)
            elif etype == "citations":
                citations = event.get("sources", [])
            elif etype == "plan_update":
                plan = event.get("tasks", [])
            elif etype == "error":
                error = event.get("message")
            elif etype == "done":
                conversation_id = event.get("conversation_id")
        return {
            "text": final_text,
            "tool_calls": tool_calls,
            "citations": citations,
            "plan": plan,
            "error": error,
            "conversation_id": conversation_id,
        }

    def get(self, path: str, params: Optional[dict] = None):
        resp = httpx.get(f"{self.server}{path}", headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, payload: dict):
        resp = httpx.post(f"{self.server}{path}", json=payload, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def delete(self, path: str):
        resp = httpx.delete(f"{self.server}{path}", headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def download(self, session_id: str, filename: str, out_path: str):
        with httpx.stream("GET", f"{self.server}/api/download/{session_id}/{filename}", headers=self.headers, timeout=60) as resp:
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)


# --------------------------------------------------------------------------
# Chat / REPL
# --------------------------------------------------------------------------
def cmd_chat(client: MeikoClient, args) -> None:
    conv_id = args.conversation
    out(f"[bold cyan]You:[/] {args.message}" if HAS_RICH else f"You: {args.message}")
    out("[bold magenta]Meiko:[/]" if HAS_RICH else "Meiko:")
    for event in client.chat_stream(args.message, mode=args.mode, conversation_id=conv_id, provider=args.provider, model=args.model):
        etype = event.get("type")
        if etype == "token":
            print(event["text"], end="", flush=True)
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


def cmd_conversations(client: MeikoClient, args) -> None:
    if args.query:
        convs = client.get("/api/conversations/search", params={"user_id": client.user_id, "q": args.query})
    else:
        convs = client.get("/api/conversations", params={"user_id": client.user_id})
    rows = [[c["id"][:8], c.get("title") or "(untitled)", c.get("mode", ""), "📌" if c.get("pinned") else ""] for c in convs]
    print_table(["id", "title", "mode", "pinned"], rows)


# --------------------------------------------------------------------------
# Mission mode — hermus-style `mission start "<goal>"` with live plan tracking
# --------------------------------------------------------------------------
def cmd_mission(client: MeikoClient, args) -> None:
    out(f"[bold]🎯 Mission:[/] {args.goal}" if HAS_RICH else f"Mission: {args.goal}")
    out(f"[dim]mode={args.mode} provider={args.provider or 'default'}[/]" if HAS_RICH else f"(mode={args.mode})")
    print()
    seen_steps = 0
    conv_id = None
    for event in client.chat_stream(args.goal, mode=args.mode, provider=args.provider):
        etype = event.get("type")
        if etype == "step":
            out(f"[dim]— step {event['step']}/{event['max_steps']} —[/dim]" if HAS_RICH else f"-- step {event['step']} --")
        elif etype == "plan_update":
            tasks = event.get("tasks", [])
            if len(tasks) != seen_steps:
                seen_steps = len(tasks)
                out("[bold]Plan:[/bold]" if HAS_RICH else "Plan:")
                for t in tasks:
                    mark = {"done": "✅", "in_progress": "🔄", "pending": "⬜"}.get(t.get("status", "pending"), "⬜")
                    out(f"  {mark} {t.get('title', t)}")
        elif etype == "tool_call":
            out(f"  🔧 {event['name']}({json.dumps(event.get('arguments', {}))[:150]})", style="yellow")
        elif etype == "token":
            print(event["text"], end="", flush=True)
        elif etype == "provider_switch":
            out(f"\n  ⚠ provider {event['from']} failed, switching to {event['to']}", style="yellow")
        elif etype == "citations":
            sources = event.get("sources", [])
            if sources:
                out("\n[bold]Sources:[/bold]" if HAS_RICH else "\nSources:")
                for s in sources:
                    out(f"  - {s['url']} (via {s['via']})")
        elif etype == "error":
            out(f"\n[Mission failed] {event.get('message')}", style="red")
        elif etype == "done":
            conv_id = event.get("conversation_id")
    print()
    out(f"[dim]Mission complete. conversation_id={conv_id}[/dim]" if HAS_RICH else f"Done. conversation_id={conv_id}")


# --------------------------------------------------------------------------
# Verify — hermus-style `verify run --domain <domain>`. There's no separate
# verification engine in Meiko; this runs the check through Code or Research
# mode (whichever fits the domain) with a prompt that explicitly asks the
# model to verify/test/critique rather than just answer, and to be explicit
# about what passed/failed.
# --------------------------------------------------------------------------
_VERIFY_DOMAIN_MODE = {
    "python": "code",
    "code": "code",
    "web": "research",
    "git": "code",
    "linux": "code",
    "research": "research",
}


def cmd_verify(client: MeikoClient, args) -> None:
    mode = _VERIFY_DOMAIN_MODE.get(args.domain, "autonomous")
    prompt = (
        f"You are running in VERIFICATION mode for the '{args.domain}' domain. "
        f"Task to verify: {args.task}\n\n"
        "Actually check this (run tests/commands/fetch pages as needed — don't just assume). "
        "Then give a clear verdict as the FIRST line of your reply: either 'VERDICT: PASS' or "
        "'VERDICT: FAIL', followed by the evidence and reasoning."
    )
    out(f"[bold]🔍 Verifying[/] ({args.domain}): {args.task}" if HAS_RICH else f"Verifying ({args.domain}): {args.task}")
    result = client.chat_once(prompt, mode=mode, provider=args.provider)
    print()
    if result["error"]:
        out(f"[Verification error] {result['error']}", style="red")
        sys.exit(1)
    print_markdown(result["text"])
    verdict_line = next((line for line in result["text"].splitlines() if "VERDICT" in line.upper()), "")
    if "PASS" in verdict_line.upper():
        out("\n✅ PASS", style="green")
    elif "FAIL" in verdict_line.upper():
        out("\n❌ FAIL", style="red")
        sys.exit(1)


# --------------------------------------------------------------------------
# Delegate — hermus-style `delegate "<goal>" --task ... --aggregate`. Fans
# the same goal out to N independent Meiko runs (in parallel, real
# concurrent HTTP requests — not simulated) across different modes/providers,
# then aggregates with one of concat/vote/best/synthesize, mirroring hermus's
# aggregation strategies but implemented directly against Meiko's own
# multi-provider fallback system rather than a separate subagent runtime.
# --------------------------------------------------------------------------
def _run_worker(server: str, user_id: str, api_key: Optional[str], goal: str, mode: str, provider: Optional[str]) -> dict:
    worker_client = MeikoClient(server, user_id, api_key)
    result = worker_client.chat_once(goal, mode=mode, provider=provider)
    result["mode"] = mode
    result["provider"] = provider
    return result


def cmd_delegate(client: MeikoClient, args) -> None:
    workers = [w.strip() for w in args.workers.split(",") if w.strip()]
    if not workers:
        workers = ["autonomous"]
    out(f"[bold]🧑‍🤝‍🧑 Delegating[/] to {len(workers)} worker(s): {', '.join(workers)}" if HAS_RICH else f"Delegating to: {workers}")

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(workers), 6)) as pool:
        futures = [
            pool.submit(_run_worker, client.server, client.user_id, client.headers.get("X-API-Key"), args.goal, w, args.provider)
            for w in workers
        ]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    if all(r["error"] for r in results):
        out("\n[All workers failed]", style="red")
        for r in results:
            out(f"  - {r['mode']}: {r['error']}", style="red")
        sys.exit(1)

    if args.aggregate == "concat":
        out("\n[bold]All worker results:[/bold]" if HAS_RICH else "\nAll worker results:")
        for r in results:
            out(f"\n--- {r['mode']} ---")
            if r["error"]:
                out(f"  [Error] {r['error']}", style="red")
            else:
                print_markdown(r["text"])
    elif args.aggregate == "best":
        ok_results = [r for r in results if not r["error"]] or results
        best = max(ok_results, key=lambda r: len(r["text"]))
        out(f"\n[bold]Best result[/bold] (from {best['mode']}, longest/most detailed):" if HAS_RICH else f"\nBest result (from {best['mode']}):")
        print_markdown(best["text"]) if not best["error"] else out(f"  [Error] {best['error']}", style="red")
    elif args.aggregate == "vote":
        # Simple majority-by-similarity heuristic: pick the result whose
        # opening line matches the most other results' opening line.
        from collections import Counter

        usable = [r for r in results if not r["error"]] or results
        openers = [r["text"].strip().splitlines()[0] if r["text"].strip() else "" for r in usable]
        winner_opener, _ = Counter(openers).most_common(1)[0]
        winner = next(r for r, o in zip(usable, openers) if o == winner_opener)
        out(f"\n[bold]Consensus result[/bold] (from {winner['mode']}):" if HAS_RICH else f"\nConsensus result (from {winner['mode']}):")
        print_markdown(winner["text"]) if not winner["error"] else out(f"  [Error] {winner['error']}", style="red")
    else:  # synthesize — ask Meiko itself to merge the worker outputs
        usable = [r for r in results if not r["error"]]
        if not usable:
            out("\n[No worker produced usable output to synthesize]", style="red")
            sys.exit(1)
        combined = "\n\n".join(f"### Worker ({r['mode']})\n{r['text']}" for r in usable)
        synth_prompt = (
            f"The following are independent answers from {len(results)} worker agents to the same goal: "
            f"'{args.goal}'.\n\n{combined}\n\nSynthesize these into one single best answer, resolving any "
            "contradictions and keeping only the most useful, well-supported content."
        )
        out("\n[bold]Synthesizing final answer...[/bold]" if HAS_RICH else "\nSynthesizing...")
        final = client.chat_once(synth_prompt, mode="chat", provider=args.provider)
        print_markdown(final["text"])


# --------------------------------------------------------------------------
# Memory
# --------------------------------------------------------------------------
def cmd_memory(client: MeikoClient, args) -> None:
    if args.memory_command == "list":
        memories = client.get("/api/memories", params={"user_id": client.user_id})
        rows = [[m["id"][:8], m["fact"]] for m in memories]
        print_table(["id", "fact"], rows) if rows else out("No memories stored yet.")
    elif args.memory_command == "search":
        memories = client.get("/api/memories", params={"user_id": client.user_id, "q": args.query})
        rows = [[m["id"][:8], m["fact"]] for m in memories]
        print_table(["id", "fact"], rows) if rows else out("No matching memories.")
    elif args.memory_command == "add":
        result = client.post("/api/memories", {"user_id": client.user_id, "fact": args.fact})
        out(f"Remembered ({result['id'][:8]}): {args.fact}")
    elif args.memory_command == "forget":
        client.delete(f"/api/memories/{args.memory_id}")
        out(f"Forgot memory {args.memory_id}")
    elif args.memory_command == "clear":
        client.delete(f"/api/memories?user_id={client.user_id}")
        out("All memories cleared.")


# --------------------------------------------------------------------------
# Skills
# --------------------------------------------------------------------------
def cmd_skill(client: MeikoClient, args) -> None:
    if args.skill_command == "list":
        skills = client.get("/api/skills")
        rows = [[s["id"], s["description"][:80]] for s in skills]
        print_table(["id", "description"], rows) if rows else out("No skills installed.")
    elif args.skill_command == "show":
        skill = client.get(f"/api/skills/{args.skill_id}")
        out(f"[bold]{skill['name']}[/bold]" if HAS_RICH else skill["name"])
        out(f"[dim]triggers: {', '.join(skill.get('triggers', []))}[/dim]")
        print()
        print_markdown(skill["body"])


# --------------------------------------------------------------------------
# Connectors / providers / models
# --------------------------------------------------------------------------
def cmd_connectors(client: MeikoClient, args) -> None:
    connectors = client.get("/api/connectors")
    rows = [[c["id"], c["name"], "yes" if c["enabled"] else "no", "yes" if c["requires_key"] else "no", ", ".join(c["actions"])] for c in connectors]
    print_table(["id", "name", "enabled", "needs key", "actions"], rows)


def cmd_providers(client: MeikoClient, args) -> None:
    providers = client.get("/api/providers")
    rows = [[p["id"], p["display_name"], "free" if p.get("free_tier") else "paid", "yes" if p["requires_key"] else "no"] for p in providers]
    print_table(["id", "name", "tier", "needs key"], rows)


def cmd_models(client: MeikoClient, args) -> None:
    models = client.get("/api/models", params={"provider": args.provider})
    rows = [
        [m["id"], m["display_name"], m.get("context_window", ""), ", ".join(m.get("good_for", []))]
        for m in models
    ]
    print_table(["id", "name", "context", "good_for"], rows)


def cmd_modes(client: MeikoClient, args) -> None:
    for m in client.get("/api/modes"):
        out(f"- {m['id']}: {m['name']} — {m['description']}")


def cmd_set_key(client: MeikoClient, args) -> None:
    resp = client.post("/api/settings", {"user_id": client.user_id, "api_keys": {args.provider: args.key}})
    out(f"Saved key for {args.provider}: {resp}")


# --------------------------------------------------------------------------
# Sync
# --------------------------------------------------------------------------
def cmd_sync(client: MeikoClient, args) -> None:
    if args.sync_command == "pair":
        result = client.post("/api/sync/pair", {"user_id": client.user_id})
        out(f"Pairing code: [bold]{result['code']}[/bold] (expires in {result['expires_in'] // 60} minutes)" if HAS_RICH else f"Pairing code: {result['code']}")
        out("Enter this on your other device (web Settings > Sync, or `meiko sync claim <code>`) to link accounts.")
    elif args.sync_command == "claim":
        result = client.post("/api/sync/claim", {"code": args.code})
        out(f"Linked! This CLI session now uses user_id={result['user_id']}")
        out("Pass --user " + result["user_id"] + " (or set MEIKO_USER) to use it on future runs.")
    elif args.sync_command == "status":
        result = client.get("/api/sync/status", params={"user_id": client.user_id})
        out(f"Connected devices for {client.user_id}: {result['connected_devices']}")


# --------------------------------------------------------------------------
# Usage / download
# --------------------------------------------------------------------------
def cmd_usage(client: MeikoClient, args) -> None:
    summary = client.get("/api/usage", params={"user_id": client.user_id, "days": args.days})
    out(f"Usage over the last {summary['window_days']} days:")
    rows = [[r["provider"], r["mode"], r["n"], r.get("tool_calls") or 0, round(r.get("elapsed") or 0, 1), r.get("errors") or 0] for r in summary["by_provider_mode"]]
    print_table(["provider", "mode", "runs", "tool_calls", "elapsed_s", "errors"], rows)
    totals = summary["totals"]
    out(f"\nTotal: {totals.get('total', 0)} runs, {totals.get('tool_calls', 0) or 0} tool calls, {totals.get('errors', 0) or 0} errors")


def cmd_download(client: MeikoClient, args) -> None:
    client.download(args.session_id, args.filename, args.output or args.filename)
    out(f"Downloaded to {args.output or args.filename}")


# --------------------------------------------------------------------------
# Vibe coding — rapid-prototype command (bolt.new/v0-style, live preview link)
# --------------------------------------------------------------------------
def cmd_vibe(client: MeikoClient, args) -> None:
    session_id = args.session or f"vibe-{uuid.uuid4().hex[:8]}"
    out(f"[bold]✨ Vibe coding:[/] {args.idea}" if HAS_RICH else f"Vibe coding: {args.idea}")
    out(f"[dim]session={session_id}[/]" if HAS_RICH else f"(session={session_id})")
    print()
    for event in client.chat_stream(args.idea, mode="vibe", provider=args.provider, session_id=session_id):
        etype = event.get("type")
        if etype == "token":
            print(event["text"], end="", flush=True)
        elif etype == "tool_call":
            print()
            out(f"  🔧 {event['name']}({json.dumps(event.get('arguments', {}))[:120]})", style="yellow")
        elif etype == "error":
            out(f"\n[Error] {event.get('message')}", style="red")
        elif etype == "final":
            print()
    print()
    try:
        files = client.get(f"/api/workspace/{session_id}/files")
    except Exception:
        files = []
    previews = [f for f in files if f.get("preview_url")]
    if previews:
        out("🔗 Live preview:", style="green")
        for f in previews:
            out(f"  {client.server}{f['preview_url']}  ({f['name']})")
    else:
        out(f"No previewable file yet — run `meiko preview {session_id}` later, or keep chatting in this session.", style="dim")


def cmd_preview(client: MeikoClient, args) -> None:
    files = client.get(f"/api/workspace/{args.session_id}/files")
    previews = [f for f in files if f.get("preview_url")]
    if not previews:
        out("No previewable HTML files in this session yet.")
        return
    for f in previews:
        out(f"{client.server}{f['preview_url']}  ({f['name']})")


# --------------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Meiko Agent CLI — a powerful terminal client with mission/verify/delegate/memory/skills, Hermus-agent-free inspired.")
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

    p_conv = sub.add_parser("conversations", help="List / search your conversations")
    p_conv.add_argument("query", nargs="?", default=None)
    p_conv.set_defaults(func=cmd_conversations)

    p_mission = sub.add_parser("mission", help="Run a goal in autonomous mode with live plan-step tracking (hermus-style)")
    p_mission.add_argument("goal")
    p_mission.add_argument("--mode", default="autonomous")
    p_mission.add_argument("--provider", default=None)
    p_mission.set_defaults(func=cmd_mission)

    p_verify = sub.add_parser("verify", help="Verify a claim/task in a given domain and get a PASS/FAIL verdict")
    p_verify.add_argument("domain", choices=sorted(set(_VERIFY_DOMAIN_MODE.keys()) | {"autonomous"}))
    p_verify.add_argument("task")
    p_verify.add_argument("--provider", default=None)
    p_verify.set_defaults(func=cmd_verify)

    p_delegate = sub.add_parser("delegate", help="Fan a goal out to multiple parallel worker runs and aggregate results")
    p_delegate.add_argument("goal")
    p_delegate.add_argument("--workers", default="autonomous,research", help="Comma-separated list of modes to run in parallel, e.g. 'research,code,chat'")
    p_delegate.add_argument("--aggregate", choices=["concat", "vote", "best", "synthesize"], default="synthesize")
    p_delegate.add_argument("--provider", default=None)
    p_delegate.set_defaults(func=cmd_delegate)

    p_memory = sub.add_parser("memory", help="Manage Meiko's long-term memory about you")
    memory_sub = p_memory.add_subparsers(dest="memory_command", required=True)
    memory_sub.add_parser("list")
    p_mem_search = memory_sub.add_parser("search")
    p_mem_search.add_argument("query")
    p_mem_add = memory_sub.add_parser("add")
    p_mem_add.add_argument("fact")
    p_mem_forget = memory_sub.add_parser("forget")
    p_mem_forget.add_argument("memory_id")
    memory_sub.add_parser("clear")
    p_memory.set_defaults(func=cmd_memory)

    p_skill = sub.add_parser("skill", help="Browse Meiko's reusable Skill playbooks")
    skill_sub = p_skill.add_subparsers(dest="skill_command", required=True)
    skill_sub.add_parser("list")
    p_skill_show = skill_sub.add_parser("show")
    p_skill_show.add_argument("skill_id")
    p_skill.set_defaults(func=cmd_skill)

    p_connectors = sub.add_parser("connectors", help="List available connector/plugin tools")
    p_connectors.set_defaults(func=cmd_connectors)

    p_providers = sub.add_parser("providers", help="List model providers")
    p_providers.set_defaults(func=cmd_providers)

    p_models = sub.add_parser("models", help="List models for a provider")
    p_models.add_argument("--provider", default="nvidia")
    p_models.set_defaults(func=cmd_models)

    p_modes = sub.add_parser("modes", help="List agent modes")
    p_modes.set_defaults(func=cmd_modes)

    p_setkey = sub.add_parser("set-key", help="Store a provider API key server-side")
    p_setkey.add_argument("provider")
    p_setkey.add_argument("key")
    p_setkey.set_defaults(func=cmd_set_key)

    p_sync = sub.add_parser("sync", help="Cross-device pairing (link this CLI to your web/mobile account)")
    sync_sub = p_sync.add_subparsers(dest="sync_command", required=True)
    sync_sub.add_parser("pair")
    p_sync_claim = sync_sub.add_parser("claim")
    p_sync_claim.add_argument("code")
    sync_sub.add_parser("status")
    p_sync.set_defaults(func=cmd_sync)

    p_usage = sub.add_parser("usage", help="Show usage analytics")
    p_usage.add_argument("--days", type=int, default=30)
    p_usage.set_defaults(func=cmd_usage)

    p_download = sub.add_parser("download", help="Download a generated file")
    p_download.add_argument("session_id")
    p_download.add_argument("filename")
    p_download.add_argument("-o", "--output", default=None)
    p_download.set_defaults(func=cmd_download)

    p_vibe = sub.add_parser("vibe", help="Vibe coding — rapid-prototype a working app/site from a plain idea, with a live preview link")
    p_vibe.add_argument("idea")
    p_vibe.add_argument("--session", default=None, help="Reuse an existing session id to keep iterating on the same files")
    p_vibe.add_argument("--provider", default=None)
    p_vibe.set_defaults(func=cmd_vibe)

    p_preview = sub.add_parser("preview", help="List live preview links for a session's generated HTML files")
    p_preview.add_argument("session_id")
    p_preview.set_defaults(func=cmd_preview)

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
