import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AGENT_CONTEXT_SYNC_EVENT,
  AGENT_SESSION_READY_EVENT,
  currentAgentSessionId,
  savePageContext,
  type AgentContextSyncDetail
} from "../../api/client";
import type { ReportDetailResponse } from "../../api/types";

export function ReportDetail({ detail }: { detail: ReportDetailResponse }) {
  const [activeTab, setActiveTab] = useState(detail.sections[0]?.id ?? "");
  const active = detail.sections.find((section) => section.id === activeTab) ?? detail.sections[0];
  const finalDecision = detail.sections.find((section) => section.id === "final_decision");

  useEffect(() => {
    setActiveTab(detail.sections[0]?.id ?? "");
  }, [detail.report.id, detail.sections]);

  useEffect(() => {
    function saveCurrentPageContext(sessionId: string) {
      return savePageContext(sessionId, "report_detail", {
        active_report_id: detail.report.id,
        active_tab: activeTab,
        ticker: detail.report.ticker,
        trade_date: detail.report.trade_date,
        signal: detail.report.signal
      });
    }

    function syncPageContext() {
      const sessionId = currentAgentSessionId();
      if (!sessionId) {
        return;
      }
      void saveCurrentPageContext(sessionId);
    }

    function handleContextSync(event: Event) {
      const detail = (event as CustomEvent<AgentContextSyncDetail>).detail;
      if (!detail?.sessionId) {
        return;
      }
      detail.tasks.push(saveCurrentPageContext(detail.sessionId));
    }

    syncPageContext();
    window.addEventListener(AGENT_SESSION_READY_EVENT, syncPageContext);
    window.addEventListener(AGENT_CONTEXT_SYNC_EVENT, handleContextSync);
    return () => {
      window.removeEventListener(AGENT_SESSION_READY_EVENT, syncPageContext);
      window.removeEventListener(AGENT_CONTEXT_SYNC_EVENT, handleContextSync);
    };
  }, [activeTab, detail.report.id, detail.report.signal, detail.report.ticker, detail.report.trade_date]);

  return (
    <article className="panel report-detail">
      <header className="report-detail-header">
        <div className="report-title-row">
          <div>
            <span className="workspace-kicker">RESEARCH REPORT</span>
            <h2>{detail.report.ticker}</h2>
            <span>
              {detail.report.trade_date} · {detail.report.signal}
            </span>
          </div>
          <span className="status-pill neutral">{detail.report.signal}</span>
        </div>
        <div className="report-summary-card">
          <strong>决策摘要</strong>
          <p>{detail.report.summary}</p>
        </div>
        {finalDecision?.summary && finalDecision.id !== active?.id && (
          <button className="summary-link" type="button" onClick={() => setActiveTab(finalDecision.id)}>
            查看最终决策
          </button>
        )}
      </header>
      <div className="tab-row" role="tablist" aria-label="报告章节">
        {detail.sections.map((section) => (
          <button
            key={section.id}
            className={section.id === activeTab ? "active" : ""}
            onClick={() => setActiveTab(section.id)}
            type="button"
            role="tab"
            aria-selected={section.id === activeTab}
          >
            {section.title}
          </button>
        ))}
      </div>
      {active ? (
        <section className="report-section">
          <div className="report-section-heading">
            <span className="workspace-kicker">SECTION</span>
            <h3>{active.title}</h3>
          </div>
          <div className="section-summary-box">
            <strong>快速摘要</strong>
            <p>{active.summary || "暂无摘要"}</p>
          </div>
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{active.raw || active.summary || "暂无正文"}</ReactMarkdown>
          </div>
          <details className="raw-report-block">
            <summary>查看原始文本</summary>
            <pre>{active.raw || "暂无原始文本"}</pre>
          </details>
        </section>
      ) : (
        <p className="muted empty-detail">这份报告暂无可展示章节。</p>
      )}
    </article>
  );
}
