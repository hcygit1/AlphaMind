import { ClipboardList, Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getTradingAccount, listTradeDecisions } from "../../api/client";
import type { TradeDecision, TradingAccountResponse, TradingOrder } from "../../api/types";
import { CountUp } from "../../components/CountUp";
import { ORDER_STATUS_LABEL, money, statusPillClass } from "../../lib/format";

const ORDER_FILTERS = ["all", "pending", "filled", "rejected", "cancelled"] as const;
type OrderFilter = (typeof ORDER_FILTERS)[number];

const FILTER_LABEL: Record<OrderFilter, string> = {
  all: "全部",
  pending: "待成交",
  filled: "已成交",
  rejected: "已拒绝",
  cancelled: "已取消"
};

export function OrdersPositionsPage() {
  const [accountData, setAccountData] = useState<TradingAccountResponse | null>(null);
  const [decisions, setDecisions] = useState<TradeDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [orderFilter, setOrderFilter] = useState<OrderFilter>("all");

  const loadAll = useCallback(async () => {
    setError("");
    try {
      const [account, decisionList] = await Promise.all([getTradingAccount(), listTradeDecisions()]);
      setAccountData(account);
      setDecisions(decisionList);
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

  const positions = accountData?.positions ?? [];
  const orders = useMemo(() => {
    const list = [...(accountData?.orders ?? [])];
    list.sort((a, b) => (a.exec_date === b.exec_date ? b.created_at.localeCompare(a.created_at) : b.exec_date.localeCompare(a.exec_date)));
    return list;
  }, [accountData?.orders]);

  // 每只持仓的最新已执行决策（含止损/目标价，供风控参考）
  const planByTicker = useMemo(() => {
    const map = new Map<string, TradeDecision>();
    for (const decision of decisions) {
      if (decision.status === "executed" && (decision.stop_loss || decision.price_target)) {
        map.set(decision.ticker, decision);
      }
    }
    return map;
  }, [decisions]);

  const filteredOrders = orderFilter === "all" ? orders : orders.filter((o) => o.status === orderFilter);

  if (loading) {
    return (
      <section className="panel" aria-label="Orders and positions">
        <div className="empty-table">
          <Loader2 className="spin" size={22} aria-hidden="true" />
          <span>正在加载订单与持仓...</span>
        </div>
      </section>
    );
  }

  const totalPositionCost = positions.reduce((sum, p) => sum + p.cost_total, 0);
  const totalFee = orders.reduce((sum, o) => sum + (o.fee_amount ?? 0), 0);
  const filledCount = orders.filter((o) => o.status === "filled").length;
  const fillRate = orders.length > 0 ? filledCount / orders.length : null;

  return (
    <section className="trading-workspace" aria-label="Orders and positions workspace">
      {error && <p className="list-error">{error}</p>}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>订单与持仓</h2>
            <p>订单全历史与当前持仓明细，含成交费用与决策风控参考。</p>
          </div>
        </div>
        <div className="account-stats">
          <div className="account-stat">
            <span>持仓只数</span>
            <strong>{positions.length}</strong>
          </div>
          <div className="account-stat">
            <span>持仓成本合计</span>
            <strong>
              <CountUp value={totalPositionCost} format={money} />
            </strong>
          </div>
          <div className="account-stat">
            <span>累计手续费</span>
            <strong>
              <CountUp value={totalFee} format={money} />
            </strong>
          </div>
          <div className="account-stat">
            <span>订单成交率</span>
            <strong>{fillRate === null ? "—" : `${(fillRate * 100).toFixed(0)}%（${filledCount}/${orders.length}）`}</strong>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading compact">
          <h2>当前持仓</h2>
          <span className="status-pill neutral">{positions.length} 只</span>
        </div>
        {positions.length === 0 ? (
          <div className="empty-table">
            <ClipboardList size={22} aria-hidden="true" />
            <span>暂无持仓。在模拟交易页执行买入决策后，这里会展示持仓明细。</span>
          </div>
        ) : (
          <div className="table-shell">
            <div className="table-row table-head cols-7">
              <span>代码</span>
              <span>数量</span>
              <span>可卖（T+1）</span>
              <span>平均成本</span>
              <span>成本合计</span>
              <span>仓位占比</span>
              <span>风控参考（止损 → 目标）</span>
            </div>
            {positions.map((position) => {
              const plan = planByTicker.get(position.ticker);
              return (
                <div className="table-row cols-7" key={position.ticker}>
                  <strong>{position.ticker}</strong>
                  <span>{position.quantity.toLocaleString("zh-CN")}</span>
                  <span>{position.available.toLocaleString("zh-CN")}</span>
                  <span>{money(position.avg_cost)}</span>
                  <span>{money(position.cost_total)}</span>
                  <span>
                    {totalPositionCost > 0 ? `${((position.cost_total / totalPositionCost) * 100).toFixed(1)}%` : "—"}
                  </span>
                  <span className="muted">
                    {plan ? `${money(plan.stop_loss)} → ${money(plan.price_target)}` : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading compact">
          <h2>订单历史</h2>
          <span className="status-pill neutral">{orders.length} 笔</span>
        </div>
        <div className="tab-row" role="tablist" aria-label="订单状态筛选">
          {ORDER_FILTERS.map((filter) => {
            const count = filter === "all" ? orders.length : orders.filter((o) => o.status === filter).length;
            return (
              <button
                key={filter}
                type="button"
                role="tab"
                aria-selected={orderFilter === filter}
                className={orderFilter === filter ? "active" : ""}
                onClick={() => setOrderFilter(filter)}
              >
                {FILTER_LABEL[filter]}（{count}）
              </button>
            );
          })}
        </div>
        {filteredOrders.length === 0 ? (
          <div className="empty-table">
            {orders.length === 0 ? (
              <span>暂无订单。在模拟交易页执行决策后，订单会记录在这里。</span>
            ) : (
              <span>该状态下暂无订单。</span>
            )}
          </div>
        ) : (
          <div className="table-shell">
            <div className="table-row table-head cols-8">
              <span>执行日</span>
              <span>代码</span>
              <span>方向</span>
              <span>委托数量</span>
              <span>成交价</span>
              <span>成交量</span>
              <span>手续费</span>
              <span>状态</span>
            </div>
            {filteredOrders.map((order) => (
              <OrderRow key={order.id} order={order} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function OrderRow({ order }: { order: TradingOrder }) {
  const rejectNote = order.status === "rejected" && order.reject_reason ? `（${order.reject_reason}）` : "";
  return (
    <div className="table-row cols-8">
      <span>{order.exec_date}</span>
      <strong>{order.ticker}</strong>
      <span>{order.side === "buy" ? "买入" : "卖出"}</span>
      <span>{order.quantity.toLocaleString("zh-CN")}</span>
      <span>{order.fill_price != null ? money(order.fill_price) : "—"}</span>
      <span>{order.fill_quantity != null ? order.fill_quantity.toLocaleString("zh-CN") : "—"}</span>
      <span>{order.fee_amount != null ? money(order.fee_amount) : "—"}</span>
      <span className={statusPillClass(order.status)} title={order.reject_reason ?? undefined}>
        {ORDER_STATUS_LABEL[order.status] ?? order.status}
        {rejectNote && <small className="muted">{rejectNote}</small>}
      </span>
    </div>
  );
}
