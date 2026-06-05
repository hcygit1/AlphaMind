import {
  BarChart3,
  Bot,
  ClipboardList,
  FileText,
  FlaskConical,
  LineChart,
  Settings,
  WalletCards
} from "lucide-react";
import type { RouteKey } from "../App";

const logoIconUrl = new URL("../assets/alphamind-logo-icon.png", import.meta.url).href;

type Item =
  | { label: string; route: RouteKey; disabled?: false; icon: JSX.Element }
  | { label: string; disabled: true; icon: JSX.Element };

const items: Item[] = [
  { label: "Deep Research", route: "deep-research", icon: <Bot size={18} aria-hidden="true" /> },
  { label: "Reports", route: "reports", icon: <FileText size={18} aria-hidden="true" /> },
  { label: "Factor Lab", disabled: true, icon: <FlaskConical size={18} aria-hidden="true" /> },
  { label: "Strategy Lab", disabled: true, icon: <LineChart size={18} aria-hidden="true" /> },
  { label: "Paper Trading", disabled: true, icon: <WalletCards size={18} aria-hidden="true" /> },
  { label: "Orders & Positions", disabled: true, icon: <ClipboardList size={18} aria-hidden="true" /> },
  { label: "Review & Analytics", disabled: true, icon: <BarChart3 size={18} aria-hidden="true" /> },
  { label: "Settings", route: "settings", icon: <Settings size={18} aria-hidden="true" /> }
];

export function Sidebar({
  route,
  onRouteChange
}: {
  route: RouteKey;
  onRouteChange: (route: RouteKey) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <img className="brand-icon" src={logoIconUrl} alt="" aria-hidden="true" />
        <div className="brand-copy">
          <strong>AlphaMind</strong>
          <span>Investment Workbench</span>
        </div>
      </div>
      <nav className="nav-list" aria-label="Workbench modules">
        {items.map((item) => (
          <button
            key={item.label}
            className={"nav-item " + (!item.disabled && item.route === route ? "active" : "")}
            disabled={item.disabled}
            onClick={() => !item.disabled && onRouteChange(item.route)}
            title={item.disabled ? `${item.label} Coming Soon` : item.label}
            type="button"
          >
            {item.icon}
            <span>{item.label}</span>
            {item.disabled && <small>Soon</small>}
          </button>
        ))}
      </nav>
    </aside>
  );
}
