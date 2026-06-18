"""Chat-driven trading: user sends a natural-language instruction, Claude
reads live portfolio data via tools, decides on trades, and executes them.
Each call is a single independent turn — no conversation history is kept."""

import json
import os
import re

import anthropic

from market.finnhub import FinnhubClient
from storage.blobs import read_parquet
from trading import apply_trade, TradeError
from agent.prompts import mandate_with_override, chat_user_prompt
from agent.tools import DEEPDIVE_TOOLS, run_tool

CONTAINER = "papertrading"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_TOOL_ROUNDS = 5


def _read_portfolio() -> tuple[list[dict], float]:
    try:
        positions = read_parquet(CONTAINER, "portfolio.parquet").to_dicts()
        cash_ledger = read_parquet(CONTAINER, "cash_ledger.parquet")
        cash = float(cash_ledger.row(-1, named=True)["amount"]) if len(cash_ledger) > 0 else 0.0
    except Exception:
        positions, cash = [], 0.0
    return positions, cash


def _extract_trades(text: str) -> list[dict]:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        candidate = brace.group(0) if brace else None
    if candidate is None:
        return []
    try:
        return json.loads(candidate).get("trades", [])
    except Exception:
        return []


def _strip_json_block(text: str) -> str:
    return re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, count=1, flags=re.DOTALL).strip()


def run_chat(message: str, system_override: str | None = None) -> dict:
    """Execute one user instruction. Returns {reply, trades_executed, trades_skipped}."""
    fc = FinnhubClient()
    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

    positions, cash = _read_portfolio()
    system = mandate_with_override(system_override)
    user = chat_user_prompt(message, positions, cash)

    # Tool-use conversation loop — mirrors _converse() in loop.py.
    messages = [{"role": "user", "content": user}]
    raw_reply = ""
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=DEEPDIVE_TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            raw_reply = "".join(b.text for b in resp.content if b.type == "text")
            break
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                try:
                    out = run_tool(fc, block.name, block.input)
                except Exception as e:
                    out = {"error": str(e)}
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out, default=str)}
                )
        messages.append({"role": "user", "content": tool_results})

    trades = _extract_trades(raw_reply)
    reply = _strip_json_block(raw_reply) or raw_reply

    executed, skipped = [], []
    for t in trades:
        try:
            sym = str(t.get("symbol", "")).upper()
            price = fc.get_quote(sym).get("price")
            result = apply_trade(sym, t.get("shares"), price, t.get("side"))
            result["reasoning"] = t.get("reasoning")
            executed.append(result)
        except (TradeError, Exception) as e:
            skipped.append({"trade": t, "error": str(e)})

    return {"reply": reply, "trades_executed": executed, "trades_skipped": skipped}
