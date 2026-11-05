import { useState } from "react";
import { Shell } from "./components/Shell";
import { ReviewAnalyticsPage } from "./features/analytics/ReviewAnalyticsPage";
import { FactorLabPage } from "./features/factor/FactorLabPage";
import { DeepResearchPage } from "./features/research/DeepResearchPage";
import { ReportsPage } from "./features/reports/ReportsPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { StrategyLabPage } from "./features/strategy/StrategyLabPage";
import { OrdersPositionsPage } from "./features/trading/OrdersPositionsPage";
import { PaperTradingPage } from "./features/trading/PaperTradingPage";

export type RouteKey =
  | "deep-research"
  | "reports"
  | "factor-lab"
  | "strategy-lab"
  | "paper-trading"
  | "orders-positions"
  | "review-analytics"
  | "settings";

export function App() {
  const [route, setRoute] = useState<RouteKey>("deep-research");

  return (
    <Shell route={route} onRouteChange={setRoute}>
      <div className="route-view" key={route}>
        {route === "deep-research" && <DeepResearchPage />}
        {route === "reports" && <ReportsPage />}
        {route === "factor-lab" && <FactorLabPage />}
        {route === "strategy-lab" && <StrategyLabPage />}
        {route === "paper-trading" && <PaperTradingPage />}
        {route === "orders-positions" && <OrdersPositionsPage />}
        {route === "review-analytics" && <ReviewAnalyticsPage />}
        {route === "settings" && <SettingsPage />}
      </div>
    </Shell>
  );
}
