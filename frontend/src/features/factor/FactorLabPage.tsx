import { Loader2, FlaskConical } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { evaluateFactor, listFactorEvals, listFactors } from "../../api/client";
import type { FactorEvalRecord, FactorEvalResponse, FactorMeta } from "../../api/types";
import { LineChart } from "../../components/LineChart";
import { pct, returnClass } from "../../lib/format";

// Q1（因子值最低）→ Q5（最高）浅到深
const Q_COLORS = ["#a8b6c8", "#7d9cc4", "#4f7fc0", "#2c5da3", "#0d3a6b"];
const LS_COLOR = "#10b7c7";
const IC_COLOR = "#2c5da3";

export function FactorLabPage() {
  const [factors, setFactors] = useState<FactorMeta[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [params, setParams] = useState<Record<string, number>>({});
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<FactorEvalResponse | null>(null);
  const [evals, setEvals] = useState<FactorEvalRecord[]>([]);

  const loadEvals = useCallback(async () => {
    try {
      setEvals(await listFactorEvals());
    } catch {
      // 历史列表失败不阻塞主流程
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    listFactors()
      .then((list) => {
        if (!mounted || !list.length) {
          return;
        }
        setFactors(list);
        setSelected(list[0].key);
        setParams({ ...list[0].default_params });
      })
      .catch((exc) => mounted && setError(exc instanceof Error ? exc.message : String(exc)));
    loadEvals();
    return () => {
      mounted = false;
    };
  }, [loadEvals]);

  const current = factors.find((f) => f.key === selected);

  function pickFactor(key: string) {
    setSelected(key);
    const meta = factors.find((f) => f.key === key);
    setParams(meta ? { ...meta.default_params } : {});
  }

  async function run() {
    if (!selected) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      const res = await evaluateFactor({
        factor: selected,
        params: Object.keys(params).length ? params : null,
        start: start || null,
        end: end || null
      });
      setResult(res);
      loadEvals();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setRunning(false);
    }
  }

  const s = result?.summary;
  const icLabels = result?.ic_series.map((p) => p.date.slice(0, 7)) ?? [];
  const navLabels = result?.quantile ? ["期初", ...result.quantile.dates.map((d) => d.slice(0, 7))] : [];

  return (
    <section className="lab-workspace" aria-label="Factor Lab">
      <div className="panel">
        <div className="panel-heading">
          <h2>
            <FlaskConical size={18} aria-hidden="true" /> 因子评价
          </h2>
          <p>价量因子 → 月度 IC / 分层 / 多空检验（数据即算即评，结论自动留档）</p>
        </div>
        <div className="lab-form">
          <label>
            因子
            <select value={selected} onChange={(e) => pickFactor(e.target.value)}>
              {factors.map((f) => (
                <option key={f.key} value={f.key}>
                  {f.key}
                </option>
              ))}
            </select>
          </label>
          {Object.entries(params).map(([key, value]) => (
            <label key={key}>
              {key}
              <input
                type="number"
                min={2}
                value={value}
                onChange={(e) =>
                  setParams((prev) => ({ ...prev, [key]: Number(e.target.value) }))
                }
              />
            </label>
          ))}
          <label>
            起始日期
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label>
            截止日期
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <button className="primary-action" onClick={run} disabled={running || !selected}>
            {running ? <Loader2 className="spin" size={16} aria-hidden="true" /> : "开始评价"}
          </button>
        </div>
        {current && <p className="lab-hint">{current.description}</p>}
        {error && <p className="form-error">{error}</p>}
      </div>

      {result && s && (
        <>
          <div className="metric-grid">
            {[
              { label: "样本期数", value: String(s.n_periods) },
              { label: "IC 均值", value: s.ic_mean?.toFixed(4) ?? "—", cls: returnClass(s.ic_mean) },
              { label: "ICIR", value: s.icir?.toFixed(3) ?? "—", cls: returnClass(s.icir) },
              { label: "IC 胜率", value: s.win_rate != null ? pct(s.win_rate) : "—" },
              {
                label: "多空年化",
                value: s.long_short_annual != null ? pct(s.long_short_annual) : "—",
                cls: returnClass(s.long_short_annual)
              }
            ].map((m) => (
              <div key={m.label} className="metric-card">
                <span>{m.label}</span>
                <strong className={m.cls}>{m.value}</strong>
              </div>
            ))}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>IC 序列（月度秩相关）</h2>
              <p>因子值与下期收益的秩相关系数，持续同号为可用信号</p>
            </div>
            <LineChart
              labels={icLabels}
              refLine={0}
              yFormat={(v) => v.toFixed(2)}
              series={[
                {
                  name: "IC",
                  color: IC_COLOR,
                  values: result.ic_series.map((p) => p.ic ?? Number.NaN)
                }
              ]}
            />
          </div>

          {result.quantile && result.long_short_nav && (
            <div className="panel">
              <div className="panel-heading">
                <h2>分层净值与多空组合</h2>
                <p>Q1 为因子值最低 20%，Q5 为最高 20%；多空 = Q5 − Q1</p>
              </div>
              <LineChart
                labels={navLabels}
                refLine={1}
                series={[
                  ...Object.entries(result.quantile.navs).map(([name, values], i) => ({
                    name,
                    color: Q_COLORS[i % Q_COLORS.length],
                    values
                  })),
                  { name: "多空", color: LS_COLOR, values: result.long_short_nav ?? [] }
                ]}
              />
              {s.quantile_annuals && (
                <table className="lab-table">
                  <thead>
                    <tr>
                      <th>分组年化</th>
                      {Object.keys(s.quantile_annuals).map((q) => (
                        <th key={q}>{q}</th>
                      ))}
                      <th>多空</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>年化收益</td>
                      {Object.values(s.quantile_annuals).map((v, i) => (
                        <td key={i} className={returnClass(v)}>
                          {v != null ? pct(v) : "—"}
                        </td>
                      ))}
                      <td className={returnClass(s.long_short_annual)}>
                        {s.long_short_annual != null ? pct(s.long_short_annual) : "—"}
                      </td>
                    </tr>
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}

      <div className="panel">
        <div className="panel-heading">
          <h2>历史评价记录</h2>
          <p>最近 50 次评价结论（按时间倒序）</p>
        </div>
        {evals.length ? (
          <div className="table-scroll">
            <table className="lab-table">
              <thead>
                <tr>
                  <th>因子</th>
                  <th>参数</th>
                  <th>区间</th>
                  <th>IC 均值</th>
                  <th>ICIR</th>
                  <th>IC 胜率</th>
                  <th>多空年化</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {evals.map((e) => (
                  <tr key={e.id}>
                    <td>{e.factor_key}</td>
                    <td className="mono">{e.params}</td>
                    <td className="mono">
                      {e.start_date} ~ {e.end_date}
                    </td>
                    <td className={returnClass(e.ic_mean)}>{e.ic_mean?.toFixed(4) ?? "—"}</td>
                    <td className={returnClass(e.icir)}>{e.icir?.toFixed(3) ?? "—"}</td>
                    <td>{e.win_rate != null ? pct(e.win_rate) : "—"}</td>
                    <td className={returnClass(e.long_short_annual)}>
                      {e.long_short_annual != null ? pct(e.long_short_annual) : "—"}
                    </td>
                    <td className="muted">{e.created_at.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="lab-hint">暂无记录，先跑一次因子评价。</p>
        )}
      </div>
    </section>
  );
}
