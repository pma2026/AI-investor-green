import { useState, useRef, useEffect } from "react";
import { sendChat } from "../api.js";
import { usd } from "../components/format.js";

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [systemOverride, setSystemOverride] = useState("");
  const [showOverride, setShowOverride] = useState(false);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send() {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const res = await sendChat(msg, systemOverride.trim() || null);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          trades_executed: res.trades_executed ?? [],
          trades_skipped: res.trades_skipped ?? [],
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${e.message}`, trades_executed: [], trades_skipped: [] },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="panel chat-panel">
      <h2>Chat</h2>

      <div className="chat-override-section">
        <button className="chat-override-toggle" onClick={() => setShowOverride((v) => !v)}>
          {showOverride ? "▲" : "▼"} Override rules
        </button>
        {showOverride && (
          <textarea
            className="chat-override"
            placeholder='Ad hoc rules that take precedence over the system prompt for this session — e.g. "Do not buy energy stocks today" or "Ignore the 10% cash floor, go fully invested."'
            value={systemOverride}
            onChange={(e) => setSystemOverride(e.target.value)}
            rows={3}
          />
        )}
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="chat-empty">
            Give a trading instruction — e.g. "Sell half of AAPL and rotate into bonds" or "Find a
            defensive hedge for the tech exposure."
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg--${m.role}`}>
            <div className="chat-bubble">{m.content}</div>
            {m.trades_executed?.length > 0 && (
              <div className="chat-trades">
                <span className="chat-trades-label">Executed</span>
                <ul>
                  {m.trades_executed.map((t, j) => (
                    <li key={j}>
                      <span className={t.side === "BUY" ? "pos" : "neg"}>{t.side}</span>{" "}
                      {t.shares} {t.symbol} @ {usd(t.price)}
                      {t.reasoning && <span className="chat-reasoning"> — {t.reasoning}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {m.trades_skipped?.length > 0 && (
              <div className="chat-trades chat-trades--skipped">
                <span className="chat-trades-label">Skipped</span>
                <ul>
                  {m.trades_skipped.map((t, j) => (
                    <li key={j}>
                      {t.trade?.symbol ?? "?"}: {t.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-msg chat-msg--assistant">
            <div className="chat-bubble chat-loading">Thinking…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          className="chat-input"
          placeholder="Type a trading instruction… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          rows={2}
          disabled={loading}
        />
        <button className="chat-send" onClick={send} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
