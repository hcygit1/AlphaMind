import { Loader2, LineChart as LineChartIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  getStrategyRun,
  listStrategyRuns,
  listStrategyTemplates,
  runStrategyBacktest
} from "../../api/client";
import type {
  BacktestMetrics,
  BacktestPeriod,
  BacktestResponse,
  StrategyRunRecord,
  StrategyTemplate
} from "../../api/types";
import { LineChart } from "../../components/LineChart";
import { pct, returnClass } from "../../lib/format";

const NAV_COLORS = { strategy: "#0d3a6b", benchmark: "#a8b6c8" };

type RunView = {
  name: string;
  metrics: BacktestMetrics;
  navCurve: BacktestResponse["nav_curve"];
  periods: BacktestPeriod[];
};

export function StrategyLabPage() {
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [templateKey, setTemplateKey] = useState("");
  const [name, setName] = useState("");
  const [rulesText, setRulesText] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState<RunView | null>(null);
  const [runs, setRuns] = useState<StrategyRunRecord[]>([]);

  const loadRuns = useCallback(async () => {
    try {
      setRuns(await listStrategyRuns());
    } catch {
      // 历史列表失败不阻塞主流程
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    listStrategyTemplates()
      .then((list) => {
        if (!mounted || !list.length) {
          return;
        }
        setTemplates(list);
        applyTemplate(list[0]);
      })
      .catch((exc) => mounted && setError(exc instanceof Error ? exc.message : String(exc)));
    loadRuns();
    return () => {
      mounted = false;
    };
  }, [loadRuns]);

  function applyTemplate(t: StrategyTemplate) {
    setTemplateKey(t.key);
    setName(t.name);
    setRulesText(JSON.stringify(t.rules, null, 2));
  }

  async function run() {
    let rules: Record<string, unknown>;
    try {
      rules = JSON.parse(rulesText);
    } catch {
      setError("规则 JSON 格式有误，请检查后重试");
      return;
    }
    if (!name.trim()) {
      setError("请填写策略名称");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const res = await runStrategyBacktest({
        name: name.trim(),
        rules,
        start: start || null,
        end: end || null
      });
      setView({
        name: res.name,
        metrics: res.metrics,
        navCurve: res.nav_curve,
        periods: res.periods
      });
      loadRuns();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setRunning(false);
    }
  }

  async function openRun(id: string) {
    setError("");
    try {
      const run = await getStrategyRun(id);
      if (run.detail) {
        setView({
          name: run.name,
          metrics: {
            n_periods: run.n_periods,
            annual_return: run.annual_return,
            sharpe: run.sharpe,
            max_drawdown: run.max_drawdown,
            win_rate: run.win_rate ?? null,
            avg_turnover: run.avg_turnover ?? null,
            benchmark_annual_return: run.benchmark_annual_return,
            n_limit_up_blocked: run.detail.n_limit_up_blocked ?? null
          },
          navCurve: run.detail.nav_curve,
          periods: run.detail.periods
        });
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  const m = view?.metrics;
  const navLabels = view ? ["期初", ...view.navCurve.dates.map((d) => d.slice(0, 7))] : [];

  return (
    <section className="lab-workspace" aria-label="Strategy Lab">
      <div className="panel">
        <div className="panel-heading">
          <h2>
            <LineChartIcon size={18} aria-hidden="true" /> 策略回测
          </h2>
          <p>筛选 → 排序 → Top N 等权，月度调仓 + 双边佣金 + 涨停约束（主板 10% / 创业板科创板 20%）</p>
        </div>
        <div className="lab-form">
          <label>
            模板
            <select value={templateKey} onChange={(e) => {
              const t = templates.find((x) => x.key === e.target.value);
              if (t) applyTemplate(t);
            }}>
              {templates.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            策略名称
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            起始日期
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label>
            截止日期
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <button className="primary-action" onClick={run} disabled={running || !rulesText}>
            {running ? <Loader2 className="spin" size={16} aria-hidden="true" /> : "开始回测"}
          </button>
        </div>
        <details className="lab-rules">
          <summary>规则 JSON（可直接编辑自定义策略）</summary>
          <textarea
            value={rulesText}
            onChange={(e) => setRulesText(e.target.value)}
            rows={10}
            spellCheck={false}
          />
        </details>
        {error && <p className="form-error">{error}</p>}
      </div>

      {view && m && (
        <>
          <div className="metric-grid">
            {[
              { label: "策略年化", value: m.annual_return != null ? pct(m.annual_return) : "—", cls: returnClass(m.annual_return) },
              { label: "基准年化", value: m.benchmark_annual_return != null ? pct(m.benchmark_annual_return) : "—" },
              { label: "夏普", value: m.sharpe?.toFixed(2) ?? "—" },
              { label: "最大回撤", value: m.max_drawdown != null ? pct(m.max_drawdown) : "—" },
              { label: "月度胜率", value: m.win_rate != null ? pct(m.win_rate) : "—" },
              { label: "月均换手", value: m.avg_turnover != null ? pct(m.avg_turnover) : "—" },
              { label: "涨停拦截", value: m.n_limit_up_blocked != null ? `${m.n_limit_up_blocked} 次` : "—" }
            ].map((x) => (
              <div key={x.label} className="metric-card">
                <span>{x.label}</span>
                <strong className={x.cls}>{x.value}</strong>
              </div>
            ))}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>{view.name} · 净值曲线</h2>
              <p>费后净值 vs 全池等权基准（零成本口径）</p>
            </div>
            <LineChart
              labels={navLabels}
              refLine={1}
              series={[
                { name: "策略", color: NAV_COLORS.strategy, values: view.navCurve.nav },
                { name: "基准", color: NAV_COLORS.benchmark, values: view.navCurve.benchmark_nav }
              ]}
            />
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>逐期明细（{m.n_periods} 期）</h2>
              <p>月末调仓，收益为费后月度收益</p>
            </div>
            <div className="table-scroll">
              <table className="lab-table">
                <thead>
                  <tr>
                    <th>调仓日</th>
                    <th>持仓（{view.periods[0]?.holdings.length ?? 0} 只）</th>
                    <th>费后收益</th>
                    <th>换手率</th>
                    <th>成本</th>
                  </tr>
                </thead>
                <tbody>
                  {view.periods.map((p) => (
                    <tr key={p.date}>
                      <td className="mono">{p.date}</td>
                      <td className="mono holdings">{p.holdings.join(" ") || "空仓"}</td>
                      <td className={returnClass(p.ret)}>{pct(p.ret)}</td>
                      <td>{pct(p.turnover)}</td>
                      <td>{pct(p.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <div className="panel">
        <div className="panel-heading">
          <h2>历史回测记录</h2>
          <p>点击行查看该次回测的完整明细</p>
        </div>
        {runs.length ? (
          <div className="table-scroll">
            <table className="lab-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>区间</th>
                  <th>期数</th>
                  <th>年化</th>
                  <th>基准</th>
                  <th>夏普</th>
                  <th>回撤</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} className="clickable-row" onClick={() => openRun(r.id)}>
                    <td>{r.name}</td>
                    <td className="mono">
                      {r.start_date} ~ {r.end_date}
                    </td>
                    <td>{r.n_periods}</td>
                    <td className={returnClass(r.annual_return)}>
                      {r.annual_return != null ? pct(r.annual_return) : "—"}
                    </td>
                    <td className={returnClass(r.benchmark_annual_return)}>
                      {r.benchmark_annual_return != null ? pct(r.benchmark_annual_return) : "—"}
                    </td>
                    <td>{r.sharpe?.toFixed(2) ?? "—"}</td>
                    <td>{r.max_drawdown != null ? pct(r.max_drawdown) : "—"}</td>
                    <td className="muted">{r.created_at.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="lab-hint">暂无记录，先跑一次策略回测。</p>
        )}
      </div>
    </section>
  );
}
