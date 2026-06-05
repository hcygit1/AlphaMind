import { useState } from "react";
import { Shell } from "./components/Shell";
import { DeepResearchPage } from "./features/research/DeepResearchPage";
import { ReportsPage } from "./features/reports/ReportsPage";
import { SettingsPage } from "./features/settings/SettingsPage";

export type RouteKey = "deep-research" | "reports" | "settings";

export function App() {
  const [route, setRoute] = useState<RouteKey>("deep-research");

  return (
    <Shell route={route} onRouteChange={setRoute}>
      {route === "deep-research" && <DeepResearchPage />}
      {route === "reports" && <ReportsPage />}
      {route === "settings" && <SettingsPage />}
    </Shell>
  );
}
