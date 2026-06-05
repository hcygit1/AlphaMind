import { Bot, SendHorizonal, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import {
  createAgentSession,
  currentAgentSessionId,
  persistAgentSessionId,
  requestCurrentPageContextSync,
  sendAgentMessage
} from "../api/client";
import type { AgentToolCard } from "../api/types";

type AgentMessage = {
  role: "user" | "assistant";
  content: string;
  toolCards?: AgentToolCard[];
};

export function AgentDrawer() {
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<AgentMessage[]>([
    {
      role: "assistant",
      content: "我可以帮你总结当前报告，或启动深度投研任务。"
    }
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  useEffect(() => {
    const existing = currentAgentSessionId();
    if (existing) {
      setSessionId(existing);
      return;
    }

    let mounted = true;
    createAgentSession()
      .then((session) => {
        if (!mounted) {
          return;
        }
        setSessionId(session.id);
        persistAgentSessionId(session.id);
      })
      .catch((exc) => {
        if (mounted) {
          setError(exc instanceof Error ? exc.message : String(exc));
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = input.trim();
    if (!content || !sessionId || busy) {
      return;
    }

    setMessages((current) => [...current, { role: "user", content }]);
    setInput("");
    setError("");
    setBusy(true);

    try {
      const response = await sendWithSession(sessionId, content);
      appendAssistantResponse(response.content, response.tool_cards);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function sendWithSession(activeSessionId: string, content: string) {
    await requestCurrentPageContextSync(activeSessionId);

    try {
      return await sendAgentMessage(activeSessionId, content);
    } catch (exc) {
      if (!(exc instanceof Error) || !exc.message.includes("Agent session not found")) {
        throw exc;
      }

      const session = await createAgentSession();
      setSessionId(session.id);
      persistAgentSessionId(session.id);
      await requestCurrentPageContextSync(session.id);
      return sendAgentMessage(session.id, content);
    }
  }

  function appendAssistantResponse(content: string, toolCards: AgentToolCard[]) {
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        content,
        toolCards
      }
    ]);
  }

  return (
    <>
      <button
        className="agent-orb"
        onClick={() => setOpen(true)}
        type="button"
        aria-label="打开 AlphaMind Agent"
        aria-expanded={open}
        aria-controls="agent-drawer"
        hidden={open}
        tabIndex={open ? -1 : undefined}
      >
        <Bot size={24} aria-hidden="true" />
      </button>
      {open && (
        <aside id="agent-drawer" className="agent-drawer" aria-label="AlphaMind Agent">
          <header className="agent-header">
            <div>
              <strong>AlphaMind Agent</strong>
              <span>{sessionId ? "协助梳理研究问题、总结报告和启动深度投研。" : "正在准备会话..."}</span>
            </div>
            <button className="icon-button" onClick={() => setOpen(false)} type="button" aria-label="关闭 Agent">
              <X size={18} aria-hidden="true" />
            </button>
          </header>
          <div className="agent-context">
            <span>Context</span>
            <strong>当前页面 / 默认工作区</strong>
          </div>
          <div className="agent-messages">
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={message.role === "assistant" ? "assistant-message" : "user-message"}
              >
                <p>{message.content}</p>
                {message.toolCards?.map((card) => (
                  <div className="tool-card" key={`${card.type}-${card.status ?? "pending"}-${index}`}>
                    <span>{card.type}</span>
                    <strong>{card.status ?? "completed"}</strong>
                  </div>
                ))}
              </div>
            ))}
            {error && <p className="agent-error">{error}</p>}
          </div>
          <form className="agent-input" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="agent-message">
              Agent message
            </label>
            <input
              id="agent-message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="输入问题..."
              disabled={!sessionId || busy}
            />
            <button type="submit" aria-label="发送消息" disabled={!sessionId || busy || !input.trim()}>
              <SendHorizonal size={18} aria-hidden="true" />
              <span>{busy ? "发送中" : "发送"}</span>
            </button>
          </form>
        </aside>
      )}
    </>
  );
}
