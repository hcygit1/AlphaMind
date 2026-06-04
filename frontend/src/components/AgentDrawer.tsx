import { Bot, SendHorizonal, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

export function AgentDrawer() {
  const [open, setOpen] = useState(false);

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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
              <span>协助梳理研究问题、总结报告和启动深度投研。</span>
            </div>
            <button className="icon-button" onClick={() => setOpen(false)} type="button" aria-label="关闭 Agent">
              <X size={18} aria-hidden="true" />
            </button>
          </header>
          <div className="agent-context">
            <span>Context</span>
            <strong>Deep Research / 默认工作区</strong>
          </div>
          <div className="agent-messages">
            <div className="assistant-message">
              我可以帮你总结当前报告，或启动深度投研任务。当前研究服务未就绪。
            </div>
            <div className="tool-card">
              <span>可用能力</span>
              <strong>报告总结、深度投研</strong>
            </div>
          </div>
          <form className="agent-input" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="agent-message">
              Agent message
            </label>
            <input id="agent-message" placeholder="输入问题..." />
            <button type="submit" aria-label="发送消息">
              <SendHorizonal size={18} aria-hidden="true" />
              <span>发送</span>
            </button>
          </form>
        </aside>
      )}
    </>
  );
}
