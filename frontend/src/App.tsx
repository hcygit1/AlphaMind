import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import type { ComponentType } from "react";
import { Shell } from "./components/Shell";

// 按页分包：首屏只加载 Deep Research，其余页面首次进入时按需拉取
const DeepResearchPage = lazy(() => import("./features/research/DeepResearchPage").then(m => ({ default: m.DeepResearchPage })));
const ReportsPage = lazy(() => import("./features/reports/ReportsPage").then(m => ({ default: m.ReportsPage })));
const FactorLabPage = lazy(() => import("./features/factor/FactorLabPage").then(m => ({ default: m.FactorLabPage })));
const StrategyLabPage = lazy(() => import("./features/strategy/StrategyLabPage").then(m => ({ default: m.StrategyLabPage })));
const PaperTradingPage = lazy(() => import("./features/trading/PaperTradingPage").then(m => ({ default: m.PaperTradingPage })));
const OrdersPositionsPage = lazy(() => import("./features/trading/OrdersPositionsPage").then(m => ({ default: m.OrdersPositionsPage })));
const ReviewAnalyticsPage = lazy(() => import("./features/analytics/ReviewAnalyticsPage").then(m => ({ default: m.ReviewAnalyticsPage })));
const SettingsPage = lazy(() => import("./features/settings/SettingsPage").then(m => ({ default: m.SettingsPage })));

export type RouteKey =
  | "deep-research"
  | "reports"
  | "factor-lab"
  | "strategy-lab"
  | "paper-trading"
  | "orders-positions"
  | "review-analytics"
  | "settings";

const ROUTES: RouteKey[] = [
  "deep-research",
  "reports",
  "factor-lab",
  "strategy-lab",
  "paper-trading",
  "orders-positions",
  "review-analytics",
  "settings",
];

function routeFromHash(): RouteKey {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return (ROUTES as string[]).includes(hash) ? (hash as RouteKey) : "deep-research";
}

// 页面路由映射（React.lazy 需要 default 导出，这里用显式映射保持命名导出兼容）
const PAGES: Record<RouteKey, ComponentType> = {
  "deep-research": DeepResearchPage,
  reports: ReportsPage,
  "factor-lab": FactorLabPage,
  "strategy-lab": StrategyLabPage,
  "paper-trading": PaperTradingPage,
  "orders-positions": OrdersPositionsPage,
  "review-analytics": ReviewAnalyticsPage,
  settings: SettingsPage,
};

export function App() {
  const [route, setRoute] = useState<RouteKey>(routeFromHash);

  // hash ↔ route 双向同步：刷新/深链/浏览器后退均可用
  useEffect(() => {
    const onHashChange = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = useCallback((next: RouteKey) => {
    window.location.hash = `#/${next}`;
    setRoute(next);
  }, []);

  const Page = PAGES[route];

  return (
    <Shell route={route} onRouteChange={navigate}>
      <div className="route-view" key={route}>
        <Suspense
          fallback={
            <div className="route-loading" role="status" aria-live="polite">
              加载中…
            </div>
          }
        >
          <Page />
        </Suspense>
      </div>
    </Shell>
  );
}
