import { Bot, SendHorizonal, X } from "lucide-react";
import { FormEvent, useState } from "react";

export function AgentDrawer() {
  const [open, setOpen] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  return (
    <>
      <button className="agent-orb" onClick={() => setOpen(true)} type="button" aria-label="打开 AlphaMind Agent">
        <Bot size={24} aria-hidden="true" />
      </button>
      {open && (
        <aside className="agent-drawer" aria-label="AlphaMind Agent">
          <header className="agent-header">
            <div>
              <strong>AlphaMind Agent</strong>
              <span>当前版本将支持报告总结和深度投研工具。</span>
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
              我可以帮你总结当前报告，或启动深度投研任务。前端 API 接入会在后续任务完成。
            </div>
            <div className="tool-card">
              <span>Tool availability</span>
              <strong>Report Summary, Deep Research</strong>
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
