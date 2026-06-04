import { CalendarDays, Search, SlidersHorizontal } from "lucide-react";
import type { FormEvent } from "react";

export function DeepResearchPage() {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  return (
    <section className="page-grid" aria-label="Deep research workspace">
      <div className="panel research-panel">
        <div className="panel-heading">
          <div>
            <h2>Launch Research</h2>
            <p>输入股票与交易日期，创建一份完整的深度投研报告。</p>
          </div>
          <span className="status-pill neutral">服务未就绪</span>
        </div>
        <form className="research-form" onSubmit={handleSubmit}>
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
          <button className="primary-action" type="submit" disabled>
            研究服务未就绪
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
              <strong>创建研究任务</strong>
              <p>提交后，研究任务将在队列中等待执行。</p>
            </div>
          </li>
          <li>
            <span />
            <div>
              <strong>跟踪研究进度</strong>
              <p>任务运行时，这里会展示当前阶段和最新状态。</p>
            </div>
          </li>
          <li>
            <span />
            <div>
              <strong>查看研究报告</strong>
              <p>任务完成后，可直接打开生成的投研报告。</p>
            </div>
          </li>
        </ol>
      </div>
    </section>
  );
}
