import { CalendarDays, CircleStop, LoaderCircle, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  AGENT_CONTEXT_SYNC_EVENT,
  AGENT_SESSION_READY_EVENT,
  cancelResearchTask,
  createResearchTask,
  currentAgentSessionId,
  getActiveResearchTask,
  getResearchTask,
  researchEventsUrl,
  savePageContext,
  type AgentContextSyncDetail
} from "../../api/client";
import type { ResearchProgressEvent, ResearchTask } from "../../api/types";
import { AutomationPanel } from "./AutomationPanel";

function todayLocalISO() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

const defaultTradeDate = todayLocalISO();

const statusLabels: Record<ResearchTask["status"], string> = {
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已中断"
};

export function DeepResearchPage() {
  const [ticker, setTicker] = useState("300750");
  const [tradeDate, setTradeDate] = useState(defaultTradeDate);
  const [task, setTask] = useState<ResearchTask | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [loadingActiveTask, setLoadingActiveTask] = useState(true);
  const streamRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  // 镜像最新 task 到 ref：SSE 重连等异步回调里读取，避免 setState updater 内调副作用
  const taskRef = useRef<ResearchTask | null>(null);
  taskRef.current = task;
  const isTaskActive = task?.status === "pending" || task?.status === "running";
  const isBusy = submitting || isTaskActive || cancelling;
  const primaryActionLabel = submitting ? "正在创建..." : isTaskActive ? "执行中..." : "启动深度投研";
  const showPrimarySpinner = submitting || isTaskActive;
  const statusClass =
    task?.status === "failed" ? "danger" : task?.status === "cancelled" ? "warning" : "neutral";

  useEffect(() => {
    return () => {
      streamRef.current?.close();
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let mounted = true;

    async function restoreActiveTask() {
      setLoadingActiveTask(true);
      try {
        const activeTask = await getActiveResearchTask();
        if (!mounted) {
          return;
        }
        if (activeTask) {
          setTask(activeTask);
          setEvents(["已恢复正在运行的深度投研任务。"]);
          openProgressStream(activeTask.id);
        }
      } catch (exc) {
        if (mounted) {
          setError(exc instanceof Error ? exc.message : String(exc));
        }
      } finally {
        if (mounted) {
          setLoadingActiveTask(false);
        }
      }
    }

    void restoreActiveTask();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    function saveCurrentPageContext(sessionId: string) {
      return savePageContext(sessionId, "deep_research", {
        ticker,
        trade_date: tradeDate,
        task_id: task?.id,
        report_id: task?.report_id,
        status: task?.status
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

    // 逐字输入时防抖，避免每敲一个字符就 PUT 一次页面上下文
    const timer = window.setTimeout(syncPageContext, 600);
    window.addEventListener(AGENT_SESSION_READY_EVENT, syncPageContext);
    window.addEventListener(AGENT_CONTEXT_SYNC_EVENT, handleContextSync);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(AGENT_SESSION_READY_EVENT, syncPageContext);
      window.removeEventListener(AGENT_CONTEXT_SYNC_EVENT, handleContextSync);
    };
  }, [ticker, tradeDate, task?.id, task?.report_id, task?.status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isBusy) {
      return;
    }
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

  async function handleCancel() {
    if (!task || !isTaskActive) {
      return;
    }
    setError("");
    setCancelling(true);
    try {
      const cancelled = await cancelResearchTask(task.id);
      setTask(cancelled);
      setEvents((current) =>
        current[current.length - 1] === "任务已中断" ? current : [...current, "任务已中断"]
      );
      streamRef.current?.close();
      streamRef.current = null;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setCancelling(false);
    }
  }

  function openProgressStream(taskId: string) {
    streamRef.current?.close();
    const stream = new EventSource(researchEventsUrl(taskId));
    streamRef.current = stream;

    stream.addEventListener("research_progress", (message) => {
      let payload: ResearchProgressEvent;
      try {
        payload = JSON.parse((message as MessageEvent<string>).data) as ResearchProgressEvent;
      } catch {
        // 心跳或脏数据：跳过本条，避免中断后续事件处理
        return;
      }
      setEvents((current) => [...current, payload.message]);
      setTask((current) =>
        current
          ? {
              ...current,
              status: payload.status,
              progress_stage: payload.stage ?? current.progress_stage,
              report_id: payload.payload?.report_id ?? current.report_id,
              error_message:
                payload.status === "failed" || payload.status === "cancelled"
                  ? payload.message
                  : current.error_message
            }
          : current
      );

      if (payload.status === "completed" || payload.status === "failed" || payload.status === "cancelled") {
        stream.close();
        streamRef.current = null;
        // 终态后重新拉取任务，补齐 token 用量等字段；若用户已切换到新任务则丢弃旧响应
        if (payload.status === "completed") {
          void getResearchTask(taskId)
            .then((finalTask) =>
              setTask((current) => (current?.id === finalTask.id ? finalTask : current))
            )
            .catch(() => undefined);
        }
      }
    });

    stream.onerror = () => {
      // 网络抖动/服务重启时不放弃：延迟后自动重连（重连期间事件会从
      // _events 缓冲补发）。任务已终态时 EventSource 自身也不会再触发。
      stream.close();
      streamRef.current = null;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        const current = taskRef.current;
        if (current?.id === taskId && (current.status === "pending" || current.status === "running")) {
          openProgressStream(taskId);
        }
      }, 3000);
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
          <span className={"status-pill " + statusClass}>
            {loadingActiveTask ? "同步中" : task ? statusLabels[task.status] : "可启动"}
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
                disabled={isBusy || loadingActiveTask}
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
                disabled={isBusy || loadingActiveTask}
                required
              />
            </div>
          </label>
          <label>
            <span>模型配置</span>
            <div className="field-with-icon">
              <SlidersHorizontal size={18} aria-hidden="true" />
              <select defaultValue="default" disabled={isBusy || loadingActiveTask}>
                <option value="default">默认研究配置</option>
              </select>
            </div>
          </label>
          {error && <p className="form-error">{error}</p>}
          <div className="form-actions">
            <button className="primary-action" type="submit" disabled={isBusy || loadingActiveTask}>
              {showPrimarySpinner && <LoaderCircle className="button-spinner" size={16} aria-hidden="true" />}
              {primaryActionLabel}
            </button>
            {isTaskActive && (
              <button
                className="secondary-action cancel-action"
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
              >
                {cancelling ? (
                  <LoaderCircle className="button-spinner" size={16} aria-hidden="true" />
                ) : (
                  <CircleStop size={16} aria-hidden="true" />
                )}
                {cancelling ? "正在中断..." : "中断"}
              </button>
            )}
          </div>
        </form>
      </div>
      <div className="panel progress-panel">
        <div className="panel-heading compact">
          <h2>Research Queue</h2>
          <span className="muted">{task ? statusLabels[task.status] : "No active task"}</span>
        </div>
        {task ? (
          <div className="task-status">
            <div className="task-state-banner">
              <div>
                <span className="workspace-kicker">CURRENT RUN</span>
                <strong>{task.ticker} · {task.trade_date}</strong>
              </div>
              <span className={"status-pill " + statusClass}>{statusLabels[task.status]}</span>
            </div>
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
              {task.total_tokens != null && task.total_tokens > 0 && (
                <div>
                  <dt>Token 用量</dt>
                  <dd>
                    共 {task.total_tokens.toLocaleString("zh-CN")}（输入 {task.prompt_tokens?.toLocaleString("zh-CN") ?? 0} / 输出{" "}
                    {task.completion_tokens?.toLocaleString("zh-CN") ?? 0}）
                  </dd>
                </div>
              )}
            </dl>
            <div className="research-steps" aria-label="任务阶段">
              {buildTaskSteps(task).map((step) => (
                <div className={"research-step " + step.status} key={step.label}>
                  <span />
                  <div>
                    <strong>{step.label}</strong>
                    <p>{step.description}</p>
                  </div>
                </div>
              ))}
            </div>
            {isTaskActive && (
              <p className="task-note">
                后台正在执行深度投研。切换页面不会丢失任务，返回后会自动恢复进度连接。
              </p>
            )}
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
      <AutomationPanel />
    </section>
  );
}

function buildTaskSteps(task: ResearchTask) {
  const runningOrDone = ["running", "completed", "failed", "cancelled"].includes(task.status);
  const terminal = ["completed", "failed", "cancelled"].includes(task.status);
  return [
    {
      label: "任务创建",
      description: "任务已进入研究队列。",
      status: "done"
    },
    {
      label: "开始运行",
      description: runningOrDone ? "后端已开始执行工作流。" : "等待后端调度。",
      status: runningOrDone ? "done" : "active"
    },
    {
      label: "当前阶段",
      description: task.progress_stage ?? "等待阶段更新。",
      status: task.status === "running" ? "active" : terminal ? "done" : "pending"
    },
    {
      label: "任务结果",
      description:
        task.status === "completed"
          ? "报告已生成，可前往报告页查看。"
          : task.status === "failed"
            ? "任务失败，请查看错误信息。"
            : task.status === "cancelled"
              ? "任务已中断，不会生成报告。"
              : "等待最终决策。",
      status: terminal ? (task.status === "completed" ? "done" : "stopped") : "pending"
    }
  ];
}
