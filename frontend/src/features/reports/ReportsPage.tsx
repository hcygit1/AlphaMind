import { FileSearch } from "lucide-react";

const columns = ["Ticker", "Trade Date", "Signal", "Generated", "Status"];

export function ReportsPage() {
  return (
    <section className="panel reports-panel" aria-label="Reports workspace">
      <div className="panel-heading">
        <div>
          <h2>Research Reports</h2>
          <p>按股票、交易日期和研究信号查看历史深度投研报告。</p>
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
          <span>暂无报告。完成深度投研后，报告会显示在这里。</span>
        </div>
      </div>
    </section>
  );
}
