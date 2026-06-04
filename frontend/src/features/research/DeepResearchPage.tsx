import { CalendarDays, Search, SlidersHorizontal } from "lucide-react";

export function DeepResearchPage() {
  return (
    <section className="page-grid" aria-label="Deep research workspace">
      <div className="panel research-panel">
        <div className="panel-heading">
          <div>
            <h2>Launch Research</h2>
            <p>输入股票与交易日期，后续任务将接入深度投研 API 和 SSE 进度。</p>
          </div>
          <span className="status-pill">Shell Ready</span>
        </div>
        <form className="research-form">
          <label>
            <span>股票代码 / 名称</span>
            <div className="field-with-icon">
              <Search size={18} aria-hidden="true" />
              <input placeholder="例如 300750 或 宁德时代" />
            </div>
          </label>
          <label>
            <span>分析日期</span>
            <div className="field-with-icon">
              <CalendarDays size={18} aria-hidden="true" />
              <input type="date" />
            </div>
          </label>
          <label>
            <span>模型配置</span>
            <div className="field-with-icon">
              <SlidersHorizontal size={18} aria-hidden="true" />
              <select defaultValue="default">
                <option value="default">默认研究配置</option>
              </select>
            </div>
          </label>
          <button className="primary-action" type="button" disabled>
            等待 API 接入
          </button>
        </form>
      </div>
      <div className="panel progress-panel">
        <div className="panel-heading compact">
          <h2>Research Queue</h2>
          <span className="muted">No active task</span>
        </div>
        <ol className="timeline">
          <li>
            <span />
            <div>
              <strong>Task creation</strong>
              <p>Task 9 will create research jobs through FastAPI.</p>
            </div>
          </li>
          <li>
            <span />
            <div>
              <strong>SSE progress</strong>
              <p>Progress events will appear here after API wiring.</p>
            </div>
          </li>
          <li>
            <span />
            <div>
              <strong>Report handoff</strong>
              <p>Completed tasks will open the generated report.</p>
            </div>
          </li>
        </ol>
      </div>
    </section>
  );
}
