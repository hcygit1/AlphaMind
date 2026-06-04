import { useEffect, useState } from "react";
import type { ReportDetailResponse } from "../../api/types";

export function ReportDetail({ detail }: { detail: ReportDetailResponse }) {
  const [activeTab, setActiveTab] = useState(detail.sections[0]?.id ?? "");
  const active = detail.sections.find((section) => section.id === activeTab) ?? detail.sections[0];

  useEffect(() => {
    setActiveTab(detail.sections[0]?.id ?? "");
  }, [detail.report.id, detail.sections]);

  return (
    <article className="panel report-detail">
      <header className="report-detail-header">
        <div>
          <h2>{detail.report.ticker}</h2>
          <span>
            {detail.report.trade_date} · {detail.report.signal}
          </span>
        </div>
        <p>{detail.report.summary}</p>
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
          <h3>{active.title}</h3>
          <p>{active.summary}</p>
          <details open={active.id === "final_decision"}>
            <summary>{active.id === "final_decision" ? "最终决策" : "查看原文"}</summary>
            <pre>{active.raw || "暂无原文"}</pre>
          </details>
          {active.id !== "final_decision" && (
            <details>
              <summary>最终决策</summary>
              <pre>
                {detail.sections.find((section) => section.id === "final_decision")?.raw ?? "暂无最终决策"}
              </pre>
            </details>
          )}
        </section>
      ) : (
        <p className="muted empty-detail">这份报告暂无可展示章节。</p>
      )}
    </article>
  );
}
