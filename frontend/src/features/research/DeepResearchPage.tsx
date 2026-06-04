import { CalendarDays, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { createResearchTask, researchEventsUrl } from "../../api/client";
import type { ResearchProgressEvent, ResearchTask } from "../../api/types";

const defaultTradeDate = new Date().toISOString().slice(0, 10);

const statusLabels: Record<ResearchTask["status"], string> = {
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  failed: "失败"
};

export function DeepResearchPage() {
  const [ticker, setTicker] = useState("300750");
  const [tradeDate, setTradeDate] = useState(defaultTradeDate);
  const [task, setTask] = useState<ResearchTask | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const streamRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => streamRef.current?.close();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    streamRef.current?.close();
    setError("");
    setEvents([]);
    setSubmitting(true);

    try {
      const created = await createResearchTask(ticker.trim(), tradeDate);
      setTask(created);
      openProgressStream(created.id);
    } catch (exc) {
      setTask(null);
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSubmitting(false);
    }
  }

  function openProgressStream(taskId: string) {
    const stream = new EventSource(researchEventsUrl(taskId));
    streamRef.current = stream;

    stream.addEventListener("research_progress", (message) => {
      const payload = JSON.parse((message as MessageEvent<string>).data) as ResearchProgressEvent;
      setEvents((current) => [...current, payload.message]);
      setTask((current) =>
        current
          ? {
              ...current,
              status: payload.status,
              progress_stage: payload.stage ?? current.progress_stage,
              report_id: payload.payload?.report_id ?? current.report_id,
              error_message: payload.status === "failed" ? payload.message : current.error_message
            }
          : current
      );

      if (payload.status === "completed" || payload.status === "failed") {
        stream.close();
        streamRef.current = null;
      }
    });

    stream.onerror = () => {
      setError("进度连接中断，请稍后刷新查看任务状态。");
      stream.close();
      streamRef.current = null;
    };
  }

  return (
    <section className="page-grid" aria-label="Deep research workspace">
      <div className="panel research-panel">
        <div className="panel-heading">
          <div>
            <h2>Launch Research</h2>
            <p>输入股票与交易日期，创建一份完整的深度投研报告。</p>
          </div>
          <span className={"status-pill " + (task?.status === "failed" ? "danger" : "neutral")}>
            {task ? statusLabels[task.status] : "可启动"}
          </span>
        </div>
        <form className="research-form" onSubmit={handleSubmit}>
          <label>
            <span>股票代码 / 名称</span>
            <div className="field-with-icon">
              <Search size={18} aria-hidden="true" />
              <input
                placeholder="例如 300750 或 宁德时代"
                value={ticker}
                onChange={(event) => setTicker(event.target.value)}
                disabled={submitting}
                required
              />
            </div>
          </label>
          <label>
            <span>分析日期</span>
            <div className="field-with-icon">
              <CalendarDays size={18} aria-hidden="true" />
              <input
                type="date"
                value={tradeDate}
                onChange={(event) => setTradeDate(event.target.value)}
                disabled={submitting}
                required
              />
            </div>
          </label>
          <label>
            <span>模型配置</span>
            <div className="field-with-icon">
              <SlidersHorizontal size={18} aria-hidden="true" />
              <select defaultValue="default" disabled={submitting}>
                <option value="default">默认研究配置</option>
              </select>
            </div>
          </label>
          {error && <p className="form-error">{error}</p>}
          <button className="primary-action" type="submit" disabled={submitting}>
            {submitting ? "正在创建..." : "启动深度投研"}
          </button>
        </form>
      </div>
      <div className="panel progress-panel">
        <div className="panel-heading compact">
          <h2>Research Queue</h2>
          <span className="muted">{task ? statusLabels[task.status] : "No active task"}</span>
        </div>
        {task ? (
          <div className="task-status">
            <dl>
              <div>
                <dt>任务</dt>
                <dd>{task.ticker}</dd>
              </div>
              <div>
                <dt>日期</dt>
                <dd>{task.trade_date}</dd>
              </div>
              <div>
                <dt>当前阶段</dt>
                <dd>{task.progress_stage ?? "等待更新"}</dd>
              </div>
              {task.report_id && (
                <div>
                  <dt>报告</dt>
                  <dd>{task.report_id}</dd>
                </div>
              )}
            </dl>
            {task.error_message && <p className="form-error">{task.error_message}</p>}
          </div>
        ) : null}
        <ol className="timeline progress-events">
          {(events.length ? events : ["提交后，研究任务将在队列中等待执行。"]).map((item, index) => (
            <li key={`${item}-${index}`}>
              <span />
              <div>
                <strong>{events.length ? `进度 ${index + 1}` : "创建研究任务"}</strong>
                <p>{item}</p>
              </div>
            </li>
          ))}
          {!events.length && (
            <>
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
                  <p>任务完成后，可在报告页打开生成的投研报告。</p>
                </div>
              </li>
            </>
          )}
        </ol>
      </div>
    </section>
  );
}
