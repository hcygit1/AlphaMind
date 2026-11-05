import { Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  getTradingAccount,
  listEquitySnapshots,
  listTradeDecisions,
  listTradeSettlements
} from "../../api/client";
import type {
  EquitySnapshot,
  TradeDecision,
  TradeSettlement,
  TradingAccountResponse
} from "../../api/types";
import { CountUp } from "../../components/CountUp";
import { money, outcomePillClass, pct, returnClass } from "../../lib/format";

function compactMoney(value: number) {
  if (Math.abs(value) >= 10000) {
    return `${(value / 10000).toFixed(1)} 万`;
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export function ReviewAnalyticsPage() {
  const [accountData, setAccountData] = useState<TradingAccountResponse | null>(null);
  const [decisions, setDecisions] = useState<TradeDecision[]>([]);
  const [settlements, setSettlements] = useState<TradeSettlement[]>([]);
  const [equitySnapshots, setEquitySnapshots] = useState<EquitySnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadAll = useCallback(async () => {
    setError("");
    try {
      const [account, decisionList, settlementList, equityList] = await Promise.all([
        getTradingAccount(),
        listTradeDecisions(),
        listTradeSettlements(),
        listEquitySnapshots()
      ]);
      setAccountData(account);
      setDecisions(decisionList);
      setSettlements(settlementList);
      setEquitySnapshots(equityList);
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

  async function handleReload() {
    setRefreshing(true);
    try {
      await loadAll();
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) {
    return (
      <section className="panel" aria-label="Review and analytics">
        <div className="empty-table">
          <Loader2 className="spin" size={22} aria-hidden="true" />
          <span>正在加载复盘数据...</span>
        </div>
      </section>
    );
  }

  const sortedSettlements = [...settlements].sort((a, b) => a.settle_date.localeCompare(b.settle_date));
  const settledCount = sortedSettlements.length;
  const wins = sortedSettlements.filter((s) => s.decision_return > 0).length;
  const winRate = settledCount > 0 ? wins / settledCount : null;
  const avgReturn =
    settledCount > 0
      ? sortedSettlements.reduce((sum, s) => sum + s.decision_return, 0) / settledCount
      : null;
  const excessSettlements = sortedSettlements.filter(
    (s) => s.excess_return !== null && s.excess_return !== undefined
  );
  const avgExcess =
    excessSettlements.length > 0
      ? excessSettlements.reduce((sum, s) => sum + (s.excess_return ?? 0), 0) / excessSettlements.length
      : null;

  const decisionById = new Map(decisions.map((d) => [d.id, d]));
  // 不依赖后端返回顺序，显式排序后取最新（曲线同样按此顺序渲染）
  const sortedEquity = [...equitySnapshots].sort((a, b) => a.date.localeCompare(b.date));
  const latestEquity = sortedEquity.length > 0 ? sortedEquity[sortedEquity.length - 1] : null;
  const initialCash = accountData?.account.initial_cash ?? null;
  const totalReturn =
    latestEquity && initialCash && initialCash > 0 ? latestEquity.total_equity / initialCash - 1 : null;

  return (
    <section className="trading-workspace" aria-label="Review and analytics workspace">
      {error && <p className="list-error">{error}</p>}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>交易复盘</h2>
            <p>已结算决策的胜率与收益表现（基准：沪深 300），以及账户权益走势。</p>
          </div>
          <button className="secondary-action" type="button" onClick={handleReload} disabled={refreshing}>
            {refreshing ? (
              <Loader2 className="spin" size={16} aria-hidden="true" />
            ) : (
              <RefreshCw size={16} aria-hidden="true" />
            )}
            刷新数据
          </button>
        </div>
        <div className="account-stats">
          <div className="account-stat">
            <span>已结算决策</span>
            <strong>{settledCount} 笔</strong>
          </div>
          <div className="account-stat">
            <span>胜率（收益 &gt; 0）</span>
            <strong>{winRate === null ? "—" : <CountUp value={winRate} format={pct} />}</strong>
          </div>
          <div className="account-stat">
            <span>平均决策收益</span>
            <strong className={returnClass(avgReturn)}>
              {avgReturn === null ? "—" : <CountUp value={avgReturn} format={pct} />}
            </strong>
          </div>
          <div className="account-stat">
            <span>平均超额收益</span>
            <strong className={returnClass(avgExcess)}>
              {avgExcess === null ? "—" : <CountUp value={avgExcess} format={pct} />}
            </strong>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading compact">
          <h2>账户权益曲线</h2>
          <div className="equity-heading-meta">
            <span>
              最新净值 <strong>{latestEquity ? money(latestEquity.total_equity) : "—"}</strong>
            </span>
            <span>
              累计收益 <strong className={returnClass(totalReturn)}>{pct(totalReturn)}</strong>
            </span>
          </div>
        </div>
        {equitySnapshots.length === 0 ? (
          <div className="empty-table">
            <span>暂无净值快照。在模拟交易页点击「刷新账户」即可生成。</span>
          </div>
        ) : (
          <EquityCurve snapshots={sortedEquity} initialCash={initialCash} />
        )}
      </div>

      <div className="panel">
        <div className="panel-heading compact">
          <h2>结算明细</h2>
          <span className="status-pill neutral">{settledCount} 条</span>
        </div>
        {settledCount === 0 ? (
          <div className="empty-table">
            <span>暂无结算记录。决策到期后，在模拟交易页点击「刷新账户」完成结算。</span>
          </div>
        ) : (
          <div className="table-shell">
            <div className="table-row table-head cols-7">
              <span>决策日期</span>
              <span>结算日</span>
              <span>代码</span>
              <span>参考 → 结算价</span>
              <span>决策收益</span>
              <span>基准 / 超额</span>
              <span>结果</span>
            </div>
            {sortedSettlements.map((settlement) => {
              const decision = decisionById.get(settlement.decision_id);
              return (
                <div className="table-row cols-7" key={settlement.id}>
                  <span>{decision?.trade_date ?? "—"}</span>
                  <span>{settlement.settle_date}</span>
                  <strong>{decision?.ticker ?? settlement.decision_id}</strong>
                  <span>
                    {money(settlement.ref_price)} → {money(settlement.settle_price)}
                  </span>
                  <span className={returnClass(settlement.decision_return)}>
                    {pct(settlement.decision_return)}
                  </span>
                  <span>
                    {pct(settlement.benchmark_return)}
                    {settlement.excess_return !== null && settlement.excess_return !== undefined && (
                      <small className={returnClass(settlement.excess_return)}>
                        （超额 {pct(settlement.excess_return)}）
                      </small>
                    )}
                  </span>
                  <span className={outcomePillClass(settlement.outcome)}>{settlement.outcome}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

function EquityCurve({
  snapshots,
  initialCash
}: {
  snapshots: EquitySnapshot[];
  initialCash: number | null;
}) {
  const width = 720;
  const height = 260;
  const padLeft = 64;
  const padRight = 18;
  const padTop = 18;
  const padBottom = 30;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;

  const domain = snapshots.map((s) => s.total_equity);
  if (initialCash !== null) {
    domain.push(initialCash);
  }
  let min = Math.min(...domain);
  let max = Math.max(...domain);
  if (max - min < 1e-9) {
    const offset = Math.max(Math.abs(max) * 0.002, 1);
    min -= offset;
    max += offset;
  }
  const padding = (max - min) * 0.1;
  min -= padding;
  max += padding;

  const xAt = (index: number) =>
    snapshots.length === 1 ? padLeft + plotWidth / 2 : padLeft + (index / (snapshots.length - 1)) * plotWidth;
  const yAt = (value: number) => padTop + (1 - (value - min) / (max - min)) * plotHeight;

  const points = snapshots.map((snapshot, index) => ({
    x: xAt(index),
    y: yAt(snapshot.total_equity),
    snapshot
  }));
  const linePoints = points.map((p) => `${p.x},${p.y}`).join(" ");
  const areaPath = `M ${points[0].x},${padTop + plotHeight} L ${points
    .map((p) => `${p.x},${p.y}`)
    .join(" L ")} L ${points[points.length - 1].x},${padTop + plotHeight} Z`;

  const gridValues = [max, (max + min) / 2, min];
  const baselineY =
    initialCash !== null && initialCash >= min && initialCash <= max ? yAt(initialCash) : null;
  const first = points[0];
  const last = points[points.length - 1];

  return (
    <div className="equity-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="账户权益曲线">
        {gridValues.map((value) => (
          <g key={value}>
            <line x1={padLeft} x2={width - padRight} y1={yAt(value)} y2={yAt(value)} className="equity-grid" />
            <text x={padLeft - 8} y={yAt(value) + 4} className="equity-axis-label" textAnchor="end">
              {compactMoney(value)}
            </text>
          </g>
        ))}
        {baselineY !== null && (
          <line x1={padLeft} x2={width - padRight} y1={baselineY} y2={baselineY} className="equity-baseline" />
        )}
        <path d={areaPath} className="equity-area" />
        <polyline points={linePoints} className="equity-line" />
        {points.map((p) => (
          <circle key={p.snapshot.id} cx={p.x} cy={p.y} r={3.5} className="equity-dot" />
        ))}
        <text
          x={first.x}
          y={height - 8}
          className="equity-axis-label"
          textAnchor={snapshots.length === 1 ? "middle" : "start"}
        >
          {first.snapshot.date}
        </text>
        <text
          x={last.x}
          y={height - 8}
          className="equity-axis-label"
          textAnchor={snapshots.length === 1 ? "middle" : "end"}
        >
          {last.snapshot.date}
        </text>
      </svg>
    </div>
  );
}
