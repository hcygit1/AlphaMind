import { BellRing, Loader2, RefreshCw, WalletCards } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
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
      setMessage(describeExecuteResult(result));
      await loadAll();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
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
      <section className="panel" aria-label="Paper trading">
        <div className="empty-table">
          <Loader2 className="spin" size={22} aria-hidden="true" />
          <span>正在加载模拟账户...</span>
        </div>
      </section>
    );
  }

  const account = accountData?.account;
  // 不依赖后端返回顺序，显式排序后取最新
  const sortedEquity = [...equitySnapshots].sort((a, b) => a.date.localeCompare(b.date));
  const latestEquity = sortedEquity.length > 0 ? sortedEquity[sortedEquity.length - 1] : null;
  const tickerByDecision = new Map(decisions.map((d) => [d.id, d.ticker]));
  const sortedSettlements = [...settlements].sort((a, b) => a.settle_date.localeCompare(b.settle_date));
  const pendingDecisions = decisions.filter((d) => d.status === "draft");
  const openAlerts = alerts.filter((a) => a.status === "open");

  return (
    <section className="trading-workspace" aria-label="Paper trading workspace">
      {error && <p className="list-error">{error}</p>}
      {message && <p className="trading-message">{message}</p>}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>模拟账户</h2>
            <p>半自动交易闭环：投研决策 → 模拟下单 → T+N 结算复盘（T+1 开盘价撮合）。</p>
          </div>
          <button className="secondary-action" type="button" onClick={handleRefresh} disabled={busy !== null}>
            {busy === "refresh" ? (
              <Loader2 className="spin" size={16} aria-hidden="true" />
            ) : (
              <RefreshCw size={16} aria-hidden="true" />
            )}
            刷新账户
          </button>
        </div>
        <div className="account-stats">
          <div className="account-stat">
            <span>现金</span>
            <strong>{account ? <CountUp value={account.cash} format={money} /> : "—"}</strong>
          </div>
          <div className="account-stat">
            <span>持仓市值</span>
            <strong>{latestEquity ? <CountUp value={latestEquity.market_value} format={money} /> : "—"}</strong>
          </div>
          <div className="account-stat">
            <span>总净值</span>
            <strong>
              {latestEquity ? (
                <CountUp value={latestEquity.total_equity} format={money} />
              ) : account ? (
                <CountUp value={account.cash} format={money} />
              ) : (
                "—"
              )}
            </strong>
          </div>
          <div className="account-stat">
            <span>初始资金</span>
            <strong>{account ? <CountUp value={account.initial_cash} format={money} /> : "—"}</strong>
          </div>
        </div>
      </div>

      {openAlerts.length > 0 && (
        <div className="panel alert-panel" role="alert">
          <div className="panel-heading compact">
            <h2>
              <BellRing size={18} aria-hidden="true" /> 持仓告警
            </h2>
            <span className="status-pill danger">{openAlerts.length} 条待确认</span>
          </div>
          <div className="table-shell">
            {openAlerts.map((alert) => (
              <div className="table-row cols-3" key={alert.id}>
                <strong>{alert.ticker}</strong>
                <span className="alert-message">
                  {alert.message}
                  <small className="muted">（{alert.kind === "stop_loss_hit" ? "止损" : "目标价"}）</small>
                </span>
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() => handleAckAlert(alert.id)}
                  disabled={busy !== null}
                >
                  {busy === alert.id && <Loader2 className="spin" size={14} aria-hidden="true" />}
                  已知悉
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-heading compact">
          <h2>交易决策</h2>
          <span className="status-pill neutral">{pendingDecisions.length} 条待执行</span>
        </div>
        {decisions.length === 0 ? (
          <div className="empty-table">
            <WalletCards size={22} aria-hidden="true" />
            <span>暂无决策。完成深度投研后，到报告页点击「执行交易决策」。</span>
          </div>
        ) : (
          <div className="table-shell">
            <div className="table-row table-head cols-7">
              <span>决策日期</span>
              <span>代码</span>
              <span>评级 / 动作</span>
              <span>入场 / 目标</span>
              <span>结算窗口</span>
              <span>状态</span>
              <span>操作</span>
            </div>
            {decisions.map((decision) => (
              <div className="table-row cols-7" key={decision.id}>
                <span>{decision.trade_date}</span>
                <strong>{decision.ticker}</strong>
                <span>
                  {decision.rating ?? "—"} / {decision.action ?? "—"}
                </span>
                <span>
                  {decision.entry_price ?? "—"} → {decision.price_target ?? "—"}
                </span>
                <span>T+{decision.settlement_days} 交易日</span>
                <span className={statusPillClass(decision.status)}>
                  {DECISION_STATUS_LABEL[decision.status] ?? decision.status}
                </span>
                {decision.status === "draft" ? (
                  <button
                    className="primary-action"
                    type="button"
                    onClick={() => handleExecute(decision.id)}
                    disabled={busy !== null}
                  >
                    {busy === decision.id && <Loader2 className="spin" size={14} aria-hidden="true" />}
                    执行决策
                  </button>
                ) : (
                  <span className="muted">—</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading compact">
          <h2>当前持仓</h2>
          <span className="status-pill neutral">{accountData?.positions.length ?? 0} 只</span>
        </div>
        {(accountData?.positions.length ?? 0) === 0 ? (
          <div className="empty-table">
            <span>暂无持仓。</span>
          </div>
        ) : (
          <div className="table-shell">
            <div className="table-row table-head">
              <span>代码</span>
              <span>数量</span>
              <span>可卖（T+1）</span>
              <span>平均成本</span>
              <span>成本合计</span>
            </div>
            {accountData?.positions.map((position) => (
              <div className="table-row" key={position.ticker}>
                <strong>{position.ticker}</strong>
                <span>{position.quantity.toLocaleString("zh-CN")}</span>
                <span>{position.available.toLocaleString("zh-CN")}</span>
                <span>{money(position.avg_cost)}</span>
                <span>{money(position.cost_total)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading compact">
          <h2>订单记录</h2>
          <span className="status-pill neutral">{accountData?.orders.length ?? 0} 笔</span>
        </div>
        {(accountData?.orders.length ?? 0) === 0 ? (
          <div className="empty-table">
            <span>暂无订单。</span>
          </div>
        ) : (
          <div className="table-shell">
            <div className="table-row table-head cols-7">
              <span>执行日</span>
              <span>代码</span>
              <span>方向</span>
              <span>数量</span>
              <span>状态</span>
              <span>成交价 / 费用</span>
              <span>说明</span>
            </div>
            {accountData?.orders.map((order) => (
              <div className="table-row cols-7" key={order.id}>
                <span>{order.exec_date}</span>
                <strong>{order.ticker}</strong>
                <span>{order.side === "buy" ? "买入" : "卖出"}</span>
                <span>{order.quantity.toLocaleString("zh-CN")}</span>
                <span className={statusPillClass(order.status)}>
                  {ORDER_STATUS_LABEL[order.status] ?? order.status}
                </span>
                <span>
                  {order.fill_price != null ? money(order.fill_price) : "—"} / {order.fee_amount != null ? money(order.fee_amount) : "—"}
                </span>
                <span className="muted">{order.reject_reason ?? "—"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading compact">
          <h2>结算复盘</h2>
          <span className="status-pill neutral">{settlements.length} 条</span>
        </div>
        {settlements.length === 0 ? (
          <div className="empty-table">
            <span>暂无结算。到期后点击「刷新账户」完成 T+N 结算。</span>
          </div>
        ) : (
          <div className="table-shell">
            <div className="table-row table-head cols-6">
              <span>结算日</span>
              <span>代码</span>
              <span>参考 / 结算价</span>
              <span>决策收益</span>
              <span>基准（沪深300）</span>
              <span>结果</span>
            </div>
            {sortedSettlements.map((settlement) => (
              <div className="table-row cols-6" key={settlement.id}>
                <span>{settlement.settle_date}</span>
                <strong>{tickerByDecision.get(settlement.decision_id) ?? settlement.decision_id}</strong>
                <span>
                  {money(settlement.ref_price)} → {money(settlement.settle_price)}
                </span>
                <span>{pct(settlement.decision_return)}</span>
                <span>
                  {pct(settlement.benchmark_return)}
                  {settlement.excess_return !== null && settlement.excess_return !== undefined && (
                    <small className="muted">（超额 {pct(settlement.excess_return)}）</small>
                  )}
                </span>
                <span className={outcomePillClass(settlement.outcome)}>
                  {settlement.outcome}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
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
