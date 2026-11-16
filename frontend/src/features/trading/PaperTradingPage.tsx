import { BellRing, Loader2, PieChart, RefreshCw, WalletCards } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ackTradeAlert,
  executeTradeDecision,
  getTradingAccount,
  listEquitySnapshots,
  listTradeAlerts,
  listTradeDecisions,
  listTradeSettlements,
  refreshTrading
} from "../../api/client";
import type {
  EquitySnapshot,
  ExecuteDecisionResponse,
  TradeAlert,
  TradeDecision,
  TradeSettlement,
  TradingAccountResponse
} from "../../api/types";
import { CountUp } from "../../components/CountUp";
import {
  DECISION_STATUS_LABEL,
  ORDER_STATUS_LABEL,
  money,
  outcomePillClass,
  pct,
  returnClass,
  statusPillClass
} from "../../lib/format";

export function PaperTradingPage() {
  const [accountData, setAccountData] = useState<TradingAccountResponse | null>(null);
  const [decisions, setDecisions] = useState<TradeDecision[]>([]);
  const [settlements, setSettlements] = useState<TradeSettlement[]>([]);
  const [equitySnapshots, setEquitySnapshots] = useState<EquitySnapshot[]>([]);
  const [alerts, setAlerts] = useState<TradeAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const aliveRef = useRef(true);

  useEffect(
    () => () => {
      aliveRef.current = false;
    },
    []
  );

  const loadAll = useCallback(async () => {
    setError("");
    try {
      const [account, decisionList, settlementList, equityList, alertList] = await Promise.all([
        getTradingAccount(),
        listTradeDecisions(),
        listTradeSettlements(),
        listEquitySnapshots(),
        listTradeAlerts()
      ]);
      setAccountData(account);
      setDecisions(decisionList);
      setSettlements(settlementList);
      setEquitySnapshots(equityList);
      setAlerts(alertList);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    loadAll().finally(() => {
      if (mounted) {
        setLoading(false);
      }
    });
    return () => {
      mounted = false;
    };
  }, [loadAll]);

  async function handleExecute(decisionId: string) {
    setBusy(decisionId);
    setMessage("");
    setError("");
    try {
      const result = await executeTradeDecision(decisionId);
      if (result.status === "executing") {
        // 异步执行：Judge 校验 + 下单在后台线程，轮询决策状态到终态后自动刷新
        setMessage("已提交执行：正在校验决策，完成后自动更新…");
        await pollDecisionTerminal(decisionId);
      } else {
        setMessage(describeExecuteResult(result));
        await loadAll();
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  /** 轮询决策状态直至离开 executing（上限约 60 秒），终态后刷新页面数据并提示结果。 */
  async function pollDecisionTerminal(decisionId: string, timeoutMs = 60000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline && aliveRef.current) {
      await new Promise((resolve) => setTimeout(resolve, 2500));
      if (!aliveRef.current) return;
      try {
        const list = await listTradeDecisions();
        const current = list.find((d) => d.id === decisionId);
        if (current && current.status !== "executing") {
          setDecisions(list);
          await loadAll();
          setMessage(describeDecisionOutcome(current));
          return;
        }
      } catch {
        // 单次轮询失败不中断，继续等下一轮
      }
    }
    if (aliveRef.current) {
      setMessage("决策仍在后台执行中，稍后刷新页面查看结果。");
    }
  }

  async function handleAckAlert(alertId: string) {
    setBusy(alertId);
    setMessage("");
    setError("");
    try {
      await ackTradeAlert(alertId);
      await loadAll();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function handleRefresh() {
    setBusy("refresh");
    setMessage("");
    setError("");
    try {
      const result = await refreshTrading();
      const { filled, rejected, postponed, cancelled } = result.orders;
      const alertNote = result.alerts.length > 0 ? `，触发告警 ${result.alerts.length} 条` : "";
      setMessage(
        `刷新完成：成交 ${filled}、拒单 ${rejected}、顺延 ${postponed}、取消 ${cancelled}，结算 ${result.settlements.length} 条，最新净值 ${money(result.equity.total_equity)}${alertNote}`
      );
      await loadAll();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <section className="trading-workspace paper-trading" aria-label="Paper trading">
        <div className="paper-loading">
          <Loader2 className="spin" size={22} aria-hidden="true" />
          <span>正在加载模拟账户...</span>
        </div>
      </section>
    );
  }

  const account = accountData?.account;
  const sortedEquity = [...equitySnapshots].sort((a, b) => a.date.localeCompare(b.date));
  const latestEquity = sortedEquity.length > 0 ? sortedEquity[sortedEquity.length - 1] : null;
  const previousEquity = sortedEquity.length > 1 ? sortedEquity[sortedEquity.length - 2] : null;
  const tickerByDecision = new Map(decisions.map((d) => [d.id, d.ticker]));
  const sortedSettlements = [...settlements].sort((a, b) => a.settle_date.localeCompare(b.settle_date));
  const pendingDecisions = decisions.filter((d) => d.status === "draft");
  const openAlerts = alerts.filter((a) => a.status === "open");

  const totalEquity = latestEquity?.total_equity ?? account?.cash ?? null;
  const marketValue = latestEquity?.market_value ?? null;
  const cash = account?.cash ?? latestEquity?.cash ?? null;
  const initialCash = account?.initial_cash ?? null;
  const cumulativeReturn =
    initialCash != null && totalEquity != null && initialCash !== 0
      ? (totalEquity - initialCash) / initialCash
      : null;
  const dailyChange = latestEquity && previousEquity ? latestEquity.total_equity - previousEquity.total_equity : null;
  const dailyChangePercent =
    previousEquity && previousEquity.total_equity !== 0 && dailyChange != null
      ? dailyChange / previousEquity.total_equity
      : null;
  const marketShare =
    totalEquity != null && totalEquity !== 0 && latestEquity ? latestEquity.market_value / totalEquity : null;
  const cashShare =
    totalEquity != null && totalEquity !== 0 && latestEquity ? latestEquity.cash / totalEquity : null;

  return (
    <section className="trading-workspace paper-trading" aria-label="Paper trading workspace">
      <div className="paper-topbar">
        <p>半自动交易闭环：投研决策 → 模拟下单 → T+N 结算复盘（T+1 开盘价撮合）。</p>
        <button className="paper-btn" type="button" onClick={handleRefresh} disabled={busy !== null}>
          {busy === "refresh" ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
          刷新账户
        </button>
      </div>

      {error && <p className="paper-error">{error}</p>}
      {message && <p className="paper-message" role="status">{message}</p>}

      {openAlerts.length > 0 && (
        <div className="paper-notice" role="alert">
          <div className="paper-notice-icon" aria-hidden="true">!</div>
          <div className="paper-notice-body">
            <strong>持仓告警</strong>
            <div className="paper-alert-list">
              {openAlerts.map((alert) => (
                <p key={alert.id}>
                  <span className="paper-alert-ticker">{alert.ticker}</span>
                  {alert.message.startsWith(alert.ticker)
                    ? alert.message.slice(alert.ticker.length).trimStart()
                    : alert.message}
                  <small>（{alert.kind === "stop_loss_hit" ? "止损" : "目标价"}）</small>
                </p>
              ))}
            </div>
          </div>
          {openAlerts.map((alert) => (
            <button
              className="paper-btn ghost"
              key={alert.id}
              type="button"
              onClick={() => handleAckAlert(alert.id)}
              disabled={busy !== null}
            >
              {busy === alert.id && <Loader2 className="spin" size={14} aria-hidden="true" />}
              已知悉
            </button>
          ))}
        </div>
      )}

      <div className="paper-grid">
        <section className="paper-card paper-equity" aria-label="账户净值">
          <div className="paper-equity-head">
            <div>
              <span className="paper-label">账户总净值</span>
              <strong className="paper-total">
                {totalEquity != null ? <CountUp value={totalEquity} format={money} /> : "—"}
              </strong>
              <div className="paper-equity-meta">
                <span className={returnClass(cumulativeReturn)}>累计 {signedPct(cumulativeReturn)}</span>
                {dailyChange != null && (
                  <span className={returnClass(dailyChange)}>今日 {signedMoney(dailyChange)}</span>
                )}
                {latestEquity && <span>截至 {latestEquity.date}</span>}
              </div>
            </div>
          </div>
          {sortedEquity.length > 0 ? (
            <EquityChart snapshots={sortedEquity} initialCash={initialCash} />
          ) : (
            <div className="paper-empty compact">
              <WalletCards size={20} aria-hidden="true" />
              <span>暂无净值快照。完成一次「刷新账户」后会自动记录。</span>
            </div>
          )}
          <div className="paper-metrics">
            <div>
              <span>现金</span>
              <strong>{cash != null ? <CountUp value={cash} format={money} /> : "—"}</strong>
            </div>
            <div>
              <span>持仓市值</span>
              <strong>{marketValue != null ? <CountUp value={marketValue} format={money} /> : "—"}</strong>
            </div>
            <div>
              <span>初始资金</span>
              <strong>{initialCash != null ? <CountUp value={initialCash} format={money} /> : "—"}</strong>
            </div>
          </div>
        </section>

        <section className="paper-card paper-allocation" aria-label="资金分布">
          <div className="paper-card-head">
            <h2>
              <PieChart size={18} aria-hidden="true" />
              资金分布
            </h2>
            <span className="paper-chip">{accountData?.positions.length ?? 0} 只持仓</span>
          </div>
          {totalEquity != null && totalEquity > 0 ? (
            <div className="paper-allocation-body">
              <div
                className="paper-donut"
                style={{
                  background: `conic-gradient(var(--paper-accent) 0 ${(marketShare ?? 0) * 100}%, #c8d9d0 ${(marketShare ?? 0) * 100}% 100%)`
                }}
                aria-hidden="true"
              />
              <div className="paper-legend">
                <div className="paper-legend-item">
                  <i className="paper-dot" aria-hidden="true" />
                  <div>
                    <span>持仓市值</span>
                    <strong>{marketValue != null ? money(marketValue) : "—"}</strong>
                  </div>
                </div>
                <div className="paper-legend-item">
                  <i className="paper-dot muted" aria-hidden="true" />
                  <div>
                    <span>可用现金</span>
                    <strong>{cash != null ? money(cash) : "—"}</strong>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="paper-empty compact">
              <span>暂无资金分布数据。</span>
            </div>
          )}
          <div className="paper-account-meta">
            <div>
              <span>当前仓位</span>
              <strong>{marketShare != null ? pct(marketShare) : "—"}</strong>
            </div>
            <div>
              <span>待执行决策</span>
              <strong>{pendingDecisions.length} 条</strong>
            </div>
          </div>
        </section>

        <section className="paper-card paper-decisions" aria-label="交易决策">
          <div className="paper-card-head">
            <h2>交易决策</h2>
            <span className="paper-chip accent">{pendingDecisions.length} 条待执行</span>
          </div>
          {decisions.length === 0 ? (
            <div className="paper-empty">
              <WalletCards size={22} aria-hidden="true" />
              <span>暂无决策。完成深度投研后，到报告页点击「执行交易决策」。</span>
            </div>
          ) : (
            <div className="paper-decision-list">
              {decisions.map((decision) => (
                <article className="paper-decision" key={decision.id}>
                  <div>
                    <strong>{decision.ticker}</strong>
                    <small>
                      {decision.trade_date} · {decision.rating ?? "—"} / {decision.action ?? "—"}
                    </small>
                  </div>
                  <div>
                    <span>入场 → 目标</span>
                    <strong>
                      {decision.entry_price ?? "—"} → {decision.price_target ?? "—"}
                    </strong>
                  </div>
                  <div>
                    <span>结算窗口</span>
                    <strong>T+{decision.settlement_days} 交易日</strong>
                  </div>
                  <div className="paper-decision-action">
                    {decision.status === "draft" ? (
                      <button
                        className="paper-btn primary"
                        type="button"
                        onClick={() => handleExecute(decision.id)}
                        disabled={busy !== null}
                      >
                        {busy === decision.id && <Loader2 className="spin" size={14} aria-hidden="true" />}
                        执行决策
                      </button>
                    ) : (
                      <span className={statusPillClass(decision.status)}>
                        {DECISION_STATUS_LABEL[decision.status] ?? decision.status}
                      </span>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="paper-card paper-positions" aria-label="当前持仓">
          <div className="paper-card-head">
            <h2>当前持仓</h2>
            <span className="paper-chip">{accountData?.positions.length ?? 0} 只</span>
          </div>
          {(accountData?.positions.length ?? 0) === 0 ? (
            <div className="paper-empty compact">
              <span>暂无持仓。</span>
            </div>
          ) : (
            <div className="paper-table-wrap">
              <table className="paper-table">
                <thead>
                  <tr>
                    <th>代码</th>
                    <th className="num">数量</th>
                    <th className="num">可卖 T+1</th>
                    <th className="num">平均成本</th>
                    <th className="num">成本合计</th>
                  </tr>
                </thead>
                <tbody>
                  {accountData?.positions.map((position) => (
                    <tr key={position.ticker}>
                      <td>
                        <strong>{position.ticker}</strong>
                      </td>
                      <td className="num">{position.quantity.toLocaleString("zh-CN")}</td>
                      <td className="num">{position.available.toLocaleString("zh-CN")}</td>
                      <td className="num">{money(position.avg_cost)}</td>
                      <td className="num">{money(position.cost_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="paper-card paper-orders" aria-label="订单记录">
          <div className="paper-card-head">
            <h2>订单记录</h2>
            <span className="paper-chip">{accountData?.orders.length ?? 0} 笔</span>
          </div>
          {(accountData?.orders.length ?? 0) === 0 ? (
            <div className="paper-empty compact">
              <span>暂无订单。</span>
            </div>
          ) : (
            <div className="paper-table-wrap">
              <table className="paper-table">
                <thead>
                  <tr>
                    <th>执行日 / 代码</th>
                    <th>方向</th>
                    <th className="num">数量</th>
                    <th>状态</th>
                    <th className="num">成交价 / 费用</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {accountData?.orders.map((order) => (
                    <tr key={order.id}>
                      <td>
                        <strong>{order.exec_date}</strong>
                        <small>{order.ticker}</small>
                      </td>
                      <td>{order.side === "buy" ? "买入" : "卖出"}</td>
                      <td className="num">{order.quantity.toLocaleString("zh-CN")}</td>
                      <td>
                        <span className={statusPillClass(order.status)}>
                          {ORDER_STATUS_LABEL[order.status] ?? order.status}
                        </span>
                      </td>
                      <td className="num">
                        {order.fill_price != null ? money(order.fill_price) : "—"} /{" "}
                        {order.fee_amount != null ? money(order.fee_amount) : "—"}
                      </td>
                      <td>{order.reject_reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="paper-card paper-settlements" aria-label="结算复盘">
          <div className="paper-card-head">
            <h2>结算复盘</h2>
            <span className="paper-chip">{settlements.length} 条</span>
          </div>
          {settlements.length === 0 ? (
            <div className="paper-empty compact">
              <span>暂无结算。到期后点击「刷新账户」完成 T+N 结算。</span>
            </div>
          ) : (
            <div className="paper-table-wrap">
              <table className="paper-table">
                <thead>
                  <tr>
                    <th>结算日 / 代码</th>
                    <th className="num">决策收益</th>
                    <th className="num">基准</th>
                    <th className="num">结果</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedSettlements.map((settlement) => (
                    <tr key={settlement.id}>
                      <td>
                        <strong>{settlement.settle_date}</strong>
                        <small>{tickerByDecision.get(settlement.decision_id) ?? settlement.decision_id}</small>
                      </td>
                      <td className={`num ${returnClass(settlement.decision_return)}`}>
                        {pct(settlement.decision_return)}
                      </td>
                      <td className="num">
                        {pct(settlement.benchmark_return)}
                        {settlement.excess_return != null && (
                          <small>超额 {pct(settlement.excess_return)}</small>
                        )}
                      </td>
                      <td className="num">
                        <span className={outcomePillClass(settlement.outcome)}>{settlement.outcome}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function EquityChart({ snapshots, initialCash }: { snapshots: EquitySnapshot[]; initialCash: number | null }) {
  const values = snapshots.map((item) => item.total_equity);
  const bounds = [...values];
  if (initialCash != null) {
    bounds.push(initialCash);
  }
  const minValue = Math.min(...bounds);
  const maxValue = Math.max(...bounds);
  const valueSpan = Math.max(maxValue - minValue, 1);
  const toX = (index: number) => 38 + index * (672 / Math.max(snapshots.length - 1, 1));
  const toY = (value: number) => 24 + ((maxValue - value) / valueSpan) * 126;
  const linePoints =
    snapshots.length > 1
      ? snapshots.map((item, index) => `${toX(index)},${toY(item.total_equity)}`).join(" ")
      : `38,${toY(values[0])} 710,${toY(values[0])}`;
  const areaPoints = `${linePoints} 710,150 38,150`;
  const labelIndexes =
    snapshots.length === 1
      ? [0]
      : snapshots.length === 2
        ? [0, 1]
        : [0, Math.floor((snapshots.length - 1) / 2), snapshots.length - 1];

  return (
    <svg className="paper-chart" viewBox="0 0 720 170" preserveAspectRatio="none" role="img" aria-label="账户净值走势">
      <defs>
        <linearGradient id="paper-equity-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#147d6f" stopOpacity="0.18" />
          <stop offset="1" stopColor="#147d6f" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g className="paper-chart-grid">
        <line x1="38" y1="24" x2="710" y2="24" />
        <line x1="38" y1="66" x2="710" y2="66" />
        <line x1="38" y1="108" x2="710" y2="108" />
        <line x1="38" y1="150" x2="710" y2="150" />
      </g>
      {initialCash != null && <line className="paper-chart-baseline" x1="38" y1={toY(initialCash)} x2="710" y2={toY(initialCash)} />}
      <polygon className="paper-chart-area" points={areaPoints} />
      <polyline className="paper-chart-line" points={linePoints} />
      {snapshots.length > 1 && (
        <circle className="paper-chart-dot" cx={toX(snapshots.length - 1)} cy={toY(values[values.length - 1])} r="4" />
      )}
      {labelIndexes.map((index) => (
        <text className="paper-chart-label" key={`${snapshots[index].date}-${index}`} x={toX(index)} y="167" textAnchor={index === 0 ? "start" : index === snapshots.length - 1 ? "end" : "middle"}>
          {shortDate(snapshots[index].date)}
        </text>
      ))}
    </svg>
  );
}

function shortDate(value: string) {
  return value.slice(5).replace("-", "/");
}

function signedMoney(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${value > 0 ? "+" : ""}${money(value)}`;
}

function signedPct(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

/** 异步执行轮询到终态后，用决策状态给出结果说明。 */
function describeDecisionOutcome(decision: TradeDecision) {
  let rejectReason = "";
  if (decision.judge_json) {
    try {
      rejectReason = String(JSON.parse(decision.judge_json)?.reject_reason ?? "");
    } catch {
      rejectReason = "";
    }
  }
  switch (decision.status) {
    case "executed":
      return "执行完成：订单已生成，等待 T+1 撮合。";
    case "rejected":
      return `已拒绝：${rejectReason || "未通过下单前校验"}`;
    case "blocked":
      return "Judge 拦截：决策未通过风控校验。";
    case "skipped":
      return "已跳过：Hold 或方向未知，未下单。";
    case "failed":
      return "执行失败：后台执行出错，请稍后重试。";
    default:
      return `决策状态已更新为${DECISION_STATUS_LABEL[decision.status] ?? decision.status}。`;
  }
}

function describeExecuteResult(result: ExecuteDecisionResponse) {
  switch (result.status) {
    case "executed": {
      const order = result.order ?? result.orders?.[result.orders.length - 1];
      if (order) {
        return `已下单：${order.ticker} ${order.side === "buy" ? "买入" : "卖出"} ${order.quantity} 股，执行日 ${order.exec_date}（待撮合）。`;
      }
      return "决策已执行。";
    }
    case "skipped":
      return `已跳过：${result.reason ?? "无需下单"}`;
    case "blocked":
      return `Judge 拦截：${result.reason ?? "决策未通过风控校验"}`;
    default:
      return `未成交：${result.reason ?? "订单被拒绝"}`;
  }
}
