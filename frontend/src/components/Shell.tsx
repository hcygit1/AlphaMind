import type { PropsWithChildren } from "react";
import type { RouteKey } from "../App";
import { AgentDrawer } from "./AgentDrawer";
import { Sidebar } from "./Sidebar";

type ShellProps = PropsWithChildren<{
  route: RouteKey;
  onRouteChange: (route: RouteKey) => void;
}>;

const routeTitles: Record<RouteKey, string> = {
  "deep-research": "Deep Research",
  reports: "Reports",
  settings: "Settings"
};

export function Shell({ children, route, onRouteChange }: ShellProps) {
  return (
    <div className="app-shell">
      <Sidebar route={route} onRouteChange={onRouteChange} />
      <main className="workspace" aria-labelledby="workspace-title">
        <div className="workspace-header">
          <div>
            <span className="workspace-kicker">Investment Workbench</span>
            <h1 id="workspace-title">{routeTitles[route]}</h1>
          </div>
          <div className="market-strip" aria-label="Market status">
            <span>CN Equity</span>
            <strong>Research Mode</strong>
          </div>
        </div>
        {children}
      </main>
      <AgentDrawer />
    </div>
  );
}
