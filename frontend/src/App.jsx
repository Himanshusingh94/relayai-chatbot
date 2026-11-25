import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8001";

function createSessionId() {
  return `s-${crypto.randomUUID()}`;
}

function App() {
  const [sessionId, setSessionId] = useState(createSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    checkBackend();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function checkBackend() {
    try {
      const response = await fetch(`${API_URL}/health`);
      setBackendOnline(response.ok);
    } catch {
      setBackendOnline(false);
    }
  }

  function newChat() {
    setSessionId(createSessionId());
    setMessages([]);
    setInput("");
    setSystemPrompt("");
  }

  async function sendMessage(customMessage) {
    const messageToSend =
      typeof customMessage === "string"
        ? customMessage
        : input;

    const trimmedMessage = messageToSend.trim();

    if (!trimmedMessage || loading) {
      return;
    }

    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: trimmedMessage,
      },
    ]);

    setInput("");
    setLoading(true);

    try {
      const body = {
        session_id: sessionId,
        message: trimmedMessage,
      };

      if (systemPrompt.trim()) {
        body.system_prompt = systemPrompt.trim();
      }

      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to complete the request."
        );
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.reply,
          metadata: data.metadata,
        },
      ]);

      setBackendOnline(true);
    } catch (error) {
      setBackendOnline(false);

      setMessages((current) => [
        ...current,
        {
          role: "error",
          content:
            error.message ||
            "Something went wrong. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  const suggestions = [
    "Explain how AI works simply",
    "Help me write Python code",
    "Give me a creative project idea",
    "Explain Docker in simple words",
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">✦</div>

          <div>
            <h1>RelayAI</h1>
            <p>Reliable AI with intelligent failover</p>
          </div>
        </div>

        <div className="header-actions">
          <div
            className={`connection ${
              backendOnline ? "online" : "offline"
            }`}
          >
            <span className="connection-dot" />
            {backendOnline
              ? "Connected"
              : "Backend unavailable"}
          </div>

          <button
            className="new-chat-button"
            onClick={newChat}
          >
            + New Chat
          </button>
        </div>
      </header>

      <main className="chat-container">
        <section className="system-bar">
          <span>System prompt</span>

          <input
            data-testid="system-prompt-input"
            value={systemPrompt}
            onChange={(event) =>
              setSystemPrompt(event.target.value)
            }
            placeholder="Optional instructions for the assistant"
          />
        </section>

        <section className="conversation">
          {messages.length === 0 && (
            <div className="hero">
              <div className="hero-icon">✦</div>

              <h2>What can I help with?</h2>

              <p>
                Ask anything. RelayAI automatically routes
                requests across AI providers for reliable
                responses.
              </p>

              <div className="suggestions">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() =>
                      sendMessage(suggestion)
                    }
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => {
            if (message.role === "user") {
              return (
                <div
                  className="message-row user-row"
                  key={index}
                >
                  <div className="user-bubble">
                    {message.content}
                  </div>
                </div>
              );
            }

            if (message.role === "error") {
              return (
                <div
                  className="error-card"
                  key={index}
                >
                  <strong>Request failed</strong>
                  <span>{message.content}</span>
                </div>
              );
            }

            const metadata = message.metadata;

            return (
              <article
                className="assistant-card"
                data-testid="assistant-message"
                key={index}
              >
                <div className="assistant-heading">
                  <div className="assistant-avatar">
                    ✦
                  </div>

                  <span>RelayAI</span>
                </div>

                <div className="assistant-content">
                  {message.content}
                </div>

                <div className="metadata">
                  <span
                    data-testid="meta-source"
                    className={`source-badge ${
                      metadata.resolution_source === "LLM_CACHE"
                        ? "cache"
                        : "live"
                    }`}
                  >
                    {metadata.resolution_source}
                  </span>

                  <span
                    data-testid="meta-model"
                    className="metadata-item"
                  >
                    {metadata.model}
                  </span>

                  <span
                    data-testid="meta-latency"
                    className="metadata-item"
                  >
                    {metadata.latency_ms} ms
                  </span>

                  <span
                    data-testid="meta-input-tokens"
                    className="metadata-item"
                  >
                    ↓ {metadata.input_tokens}
                  </span>

                  <span
                    data-testid="meta-output-tokens"
                    className="metadata-item"
                  >
                    ↑ {metadata.output_tokens}
                  </span>

                  {metadata.fallback_attempts > 0 && (
                    <span className="fallback-badge">
                      ↪ fallback
                    </span>
                  )}
                </div>
              </article>
            );
          })}

          {loading && (
            <div className="thinking-card">
              <div className="assistant-avatar">✦</div>

              <div className="thinking-content">
                <span />
                <span />
                <span />
              </div>

              <small>RelayAI is thinking</small>
            </div>
          )}

          <div ref={messagesEndRef} />
        </section>

        <section className="composer-area">
          <div className="composer">
            <textarea
              data-testid="chat-input"
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Message RelayAI..."
              maxLength={4000}
              rows={1}
            />

            <div className="composer-bottom">
              <span className="character-count">
                {input.length}/4000
              </span>

              <button
                data-testid="send-button"
                onClick={() => sendMessage()}
                disabled={loading || !input.trim()}
                aria-label="Send message"
              >
                {loading ? "•••" : "Send →"}
              </button>
            </div>
          </div>

          <p className="hint">
            Enter to send · Shift + Enter for new line
          </p>
        </section>
      </main>

      <footer>
        <span>RelayAI</span>
        <span>•</span>
        <span>
          Session {sessionId.slice(0, 13)}…
        </span>
      </footer>
    </div>
  );
}

export default App;