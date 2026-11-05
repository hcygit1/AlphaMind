import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AGENT_CONTEXT_SYNC_EVENT,
  AGENT_SESSION_READY_EVENT,
  currentAgentSessionId,
  executeTradeDecision,
  listTradeDecisions,
  savePageContext,
  type AgentContextSyncDetail
} from "../../api/client";
import type { ReportDetailResponse, TradeDecision } from "../../api/types";
import { DECISION_STATUS_LABEL } from "../../lib/format";

export function ReportDetail({ detail }: { detail: ReportDetailResponse }) {
  const [activeTab, setActiveTab] = useState(detail.sections[0]?.id ?? "");
  const active = detail.sections.find((section) => section.id === activeTab) ?? detail.sections[0];
  const finalDecision = detail.sections.find((section) => section.id === "final_decision");

  const [decision, setDecision] = useState<TradeDecision | null>(null);
  const [executing, setExecuting] = useState(false);
  const [executeMessage, setExecuteMessage] = useState("");
  const [executeError, setExecuteError] = useState("");

  useEffect(() => {
    let mounted = true;
    setDecision(null);
    setExecuteMessage("");
    setExecuteError("");
    listTradeDecisions()
      .then((decisions) => {
        if (mounted) {
          setDecision(decisions.find((d) => d.report_id === detail.report.id) ?? null);
        }
      })
      .catch(() => {
        // 决策加载失败不阻塞报告阅读
      });
    return () => {
      mounted = false;
    };
  }, [detail.report.id]);

  async function handleExecute() {
    if (!decision) {
      return;
    }
    setExecuting(true);
    setExecuteMessage("");
    setExecuteError("");
    try {
      const result = await executeTradeDecision(decision.id);
      if (result.status === "executing") {
        setExecuteMessage("决策已提交后台执行（Judge 评审中），状态稍后自动更新。");
      } else if (result.status === "executed") {
        const order = result.order ?? result.orders?.[result.orders.length - 1];
        setExecuteMessage(
          order
            ? `已下单：${order.ticker} ${order.side === "buy" ? "买入" : "卖出"} ${order.quantity} 股，执行日 ${order.exec_date}。`
            : "决策已执行。"
        );
      } else {
        setExecuteMessage(`${result.status === "blocked" ? "Judge 拦截" : "未下单"}：${result.reason ?? ""}`);
      }
      const decisions = await listTradeDecisions();
      setDecision(decisions.find((d) => d.id === decision.id) ?? decision);
    } catch (exc) {
      setExecuteError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setExecuting(false);
    }
  }

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
        {decision && (
          <div className="decision-card">
            <div className="decision-card-head">
              <strong>交易决策</strong>
              <span className={decision.status === "draft" ? "status-pill warning" : "status-pill neutral"}>
                {DECISION_STATUS_LABEL[decision.status] ?? decision.status}
              </span>
            </div>
            <div className="decision-card-body">
              <span>评级 {decision.rating ?? "—"}</span>
              <span>动作 {decision.action ?? "—"}</span>
              <span>入场 {decision.entry_price ?? "—"}</span>
              <span>止损 {decision.stop_loss ?? "—"}</span>
              <span>目标 {decision.price_target ?? "—"}</span>
              <span>结算 T+{decision.settlement_days} 交易日</span>
            </div>
            {decision.status === "draft" && (
              <button className="primary-action" type="button" onClick={handleExecute} disabled={executing}>
                {executing ? "执行中..." : "执行交易决策"}
              </button>
            )}
            {executeMessage && <p className="trading-message">{executeMessage}</p>}
            {executeError && <p className="form-error">{executeError}</p>}
          </div>
        )}
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
            id={`report-tab-${section.id}`}
            className={section.id === activeTab ? "active" : ""}
            onClick={() => setActiveTab(section.id)}
            type="button"
            role="tab"
            aria-selected={section.id === activeTab}
            aria-controls={`report-panel-${section.id}`}
          >
            {section.title}
          </button>
        ))}
      </div>
      {active ? (
        <section
          className="report-section"
          role="tabpanel"
          id={`report-panel-${active.id}`}
          aria-labelledby={`report-tab-${active.id}`}
        >
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
