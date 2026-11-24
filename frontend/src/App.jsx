import { useState } from "react";
import "./App.css";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8001";

function createSessionId() {
  return `s-${crypto.randomUUID()}`;
}

function App() {
  const [sessionId] = useState(createSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [loading, setLoading] = useState(false);

  async function sendMessage() {
    const trimmedMessage = input.trim();

    if (!trimmedMessage || loading) {
      return;
    }

    const userMessage = {
      role: "user",
      content: trimmedMessage,
    };

    setMessages((current) => [
      ...current,
      userMessage,
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

      const response = await fetch(
        `${API_URL}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(body),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Request failed"
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
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "error",
          content:
            error.message ||
            "Something went wrong.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>RelayAI</h1>
          <p>
          Reliable AI with intelligent failover
          </p>
        </div>

        <div className="status">
          <span className="status-dot" />
          Backend connected
        </div>
      </header>

      <main className="chat-shell">
        <section className="system-section">
          <label htmlFor="system-prompt">
            System prompt
          </label>

          <input
            id="system-prompt"
            data-testid="system-prompt-input"
            type="text"
            placeholder="Optional: e.g. Answer concisely"
            value={systemPrompt}
            onChange={(event) =>
              setSystemPrompt(event.target.value)
            }
          />
        </section>

        <section className="messages">
          {messages.length === 0 && (
            <div className="welcome">
              <div className="welcome-icon">
                ✦
              </div>

              <h2>How can I help?</h2>

              <p>
                Start a conversation with your
reliable multi-provider AI assistant.
              </p>
            </div>
          )}

          {messages.map((message, index) => {
            if (message.role === "user") {
              return (
                <div
                  className="message-row user-row"
                  key={index}
                >
                  <div className="user-message">
                    {message.content}
                  </div>
                </div>
              );
            }

            if (message.role === "error") {
              return (
                <div
                  className="error-message"
                  key={index}
                >
                  {message.content}
                </div>
              );
            }

            return (
              <div
                className="assistant-message"
                data-testid="assistant-message"
                key={index}
              >
                <div className="assistant-label">
                  RELAYAI
                </div>

                <div className="assistant-text">
                  {message.content}
                </div>

                <div className="metadata">
                  <span
                    className="meta-pill"
                    data-testid="meta-source"
                  >
                    {
                      message.metadata
                        .resolution_source
                    }
                  </span>

                  <span
                    className="meta-pill"
                    data-testid="meta-model"
                  >
                    {message.metadata.model}
                  </span>

                  <span
                    className="meta-pill"
                    data-testid="meta-latency"
                  >
                    {message.metadata.latency_ms} ms
                  </span>

                  <span
                    className="meta-pill"
                    data-testid="meta-input-tokens"
                  >
                    Input{" "}
                    {message.metadata.input_tokens}
                  </span>

                  <span
                    className="meta-pill"
                    data-testid="meta-output-tokens"
                  >
                    Output{" "}
                    {message.metadata.output_tokens}
                  </span>
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="thinking">
              <span />
              <span />
              <span />
              Thinking
            </div>
          )}
        </section>

        <section className="composer">
          <textarea
            data-testid="chat-input"
            placeholder="Message RelayAI..."
            value={input}
            onChange={(event) =>
              setInput(event.target.value)
            }
            onKeyDown={handleKeyDown}
            rows="2"
            maxLength="4000"
          />

          <button
            data-testid="send-button"
            onClick={sendMessage}
            disabled={
              loading || !input.trim()
            }
          >
            {loading ? "..." : "Send"}
          </button>
        </section>
      </main>

      <footer>
        Session: {sessionId.slice(0, 18)}...
      </footer>
    </div>
  );
}

export default App;