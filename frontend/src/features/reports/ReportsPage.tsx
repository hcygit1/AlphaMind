import { FileSearch, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { getReport, listReports } from "../../api/client";
import type { ReportDetailResponse, ReportSummary } from "../../api/types";
import { ReportDetail } from "./ReportDetail";

export function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [detail, setDetail] = useState<ReportDetailResponse | null>(null);
  const [selectedReportId, setSelectedReportId] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    async function loadReports() {
      setLoadingList(true);
      setError("");
      try {
        const loaded = await listReports();
        if (!mounted) {
          return;
        }
        setReports(loaded);
      } catch (exc) {
        if (mounted) {
          setError(exc instanceof Error ? exc.message : String(exc));
        }
      } finally {
        if (mounted) {
          setLoadingList(false);
        }
      }
    }

    loadReports();
    return () => {
      mounted = false;
    };
  }, []);

  async function openReport(report: ReportSummary) {
    setSelectedReportId(report.id);
    setLoadingDetail(true);
    setError("");
    try {
      const loaded = await getReport(report.id);
      setDetail(loaded);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoadingDetail(false);
    }
  }

  return (
    <section className="reports-workspace" aria-label="Reports workspace">
      <div className="panel reports-panel">
        <div className="panel-heading">
          <div>
            <h2>Research Reports</h2>
            <p>按股票、交易日期和研究信号查看历史深度投研报告。</p>
          </div>
          <span className="status-pill neutral">{loadingList ? "加载中" : `${reports.length} 份报告`}</span>
        </div>
        {error && <p className="list-error">{error}</p>}
        <div className="report-list" aria-label="报告列表">
          {loadingList && (
            <div className="empty-table">
              <Loader2 className="spin" size={22} aria-hidden="true" />
              <span>正在加载报告...</span>
            </div>
          )}
          {!loadingList &&
            reports.map((report) => (
              <button
                key={report.id}
                className={report.id === selectedReportId ? "active" : ""}
                onClick={() => openReport(report)}
                type="button"
                disabled={loadingDetail && report.id === selectedReportId}
              >
                <strong>{report.ticker}</strong>
                <span>{report.trade_date} · {report.signal}</span>
                <small>{report.summary}</small>
              </button>
            ))}
          {!loadingList && reports.length === 0 && (
            <div className="empty-table">
              <FileSearch size={22} aria-hidden="true" />
              <span>暂无报告。完成深度投研后，报告会显示在这里。</span>
            </div>
          )}
        </div>
      </div>
      <div className="report-detail-shell" aria-live="polite">
        {loadingDetail && (
          <div className="panel report-loading">
            <Loader2 className="spin" size={22} aria-hidden="true" />
            <span>正在打开报告...</span>
          </div>
        )}
        {!loadingDetail && detail && <ReportDetail detail={detail} />}
        {!loadingDetail && !detail && !loadingList && reports.length > 0 && (
          <div className="panel report-loading">
            <FileSearch size={22} aria-hidden="true" />
            <span>请选择一份报告查看详情。</span>
          </div>
        )}
      </div>
    </section>
  );
}
