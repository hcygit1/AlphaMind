import { FileSearch } from "lucide-react";

const columns = ["Ticker", "Trade Date", "Signal", "Generated", "Status"];

export function ReportsPage() {
  return (
    <section className="panel reports-panel" aria-label="Reports workspace">
      <div className="panel-heading">
        <div>
          <h2>Research Reports</h2>
          <p>历史报告列表和详情查看将在后续任务接入 Reports API。</p>
        </div>
        <button className="secondary-action" type="button" disabled>
          <FileSearch size={18} aria-hidden="true" />
          <span>筛选</span>
        </button>
      </div>
      <div className="table-shell" role="table" aria-label="Report list placeholder">
        <div className="table-row table-head" role="row">
          {columns.map((column) => (
            <span key={column} role="columnheader">
              {column}
            </span>
          ))}
        </div>
        <div className="empty-table" role="row">
          <FileSearch size={22} aria-hidden="true" />
          <span>暂无已加载报告。Task 9 会接入报告列表与详情。</span>
        </div>
      </div>
    </section>
  );
}
