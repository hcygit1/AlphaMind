import { Loader2, Plus, Timer, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  addWatchlistTicker,
  getAutomationSettings,
  listWatchlist,
  removeWatchlistTicker,
  updateAutomationSettings
} from "../../api/client";
import type { AutomationSettings, WatchlistItem } from "../../api/types";

export function AutomationPanel() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [settings, setSettings] = useState<AutomationSettings | null>(null);
  const [newTicker, setNewTicker] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const [items, config] = await Promise.all([listWatchlist(), getAutomationSettings()]);
      setWatchlist(items);
      setSettings(config);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    const ticker = newTicker.trim();
    if (!ticker) {
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await addWatchlistTicker(ticker);
      setNewTicker("");
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(ticker: string) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await removeWatchlistTicker(ticker);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleSettingsChange(patch: { enabled?: boolean; run_time?: string }) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await updateAutomationSettings(patch);
      setSettings(updated);
      setMessage(patch.enabled !== undefined ? (patch.enabled ? "自动化投研已开启" : "自动化投研已关闭") : "运行时间已更新");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  const enabled = settings ? settings.enabled === 1 : false;

  return (
    <div className="panel automation-panel">
      <div className="panel-heading">
        <div>
          <h2>
            <Timer size={18} aria-hidden="true" /> 自动化投研
          </h2>
          <p>维护自选股并设置每日定时任务：到点后自动对自选股逐个执行深度投研。</p>
        </div>
        <label className="toggle-row" title={enabled ? "点击关闭" : "点击开启"}>
          <input
            type="checkbox"
            checked={enabled}
            disabled={busy || !settings}
            onChange={(event) => void handleSettingsChange({ enabled: event.target.checked })}
          />
          <span>{enabled ? "已开启" : "已关闭"}</span>
        </label>
      </div>
      {error && <p className="form-error">{error}</p>}
      {message && <p className="trading-message">{message}</p>}
      <div className="automation-body">
        <div className="watchlist-manage">
          <form className="watchlist-add" onSubmit={handleAdd}>
            <input
              placeholder="输入股票代码，如 600519"
              value={newTicker}
              onChange={(event) => setNewTicker(event.target.value)}
              disabled={busy}
            />
            <button className="secondary-action" type="submit" disabled={busy || !newTicker.trim()}>
              {busy ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Plus size={16} aria-hidden="true" />}
              添加
            </button>
          </form>
          {watchlist.length === 0 ? (
            <p className="muted watchlist-empty">自选股为空。添加后才会执行每日自动投研。</p>
          ) : (
            <ul className="watchlist-items">
              {watchlist.map((item) => (
                <li key={item.id}>
                  <strong>{item.ticker}</strong>
                  <button
                    className="icon-action"
                    type="button"
                    aria-label={`移除 ${item.ticker}`}
                    disabled={busy}
                    onClick={() => void handleRemove(item.ticker)}
                  >
                    <X size={14} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="automation-config">
          <label>
            <span>每日运行时间</span>
            <input
              type="time"
              value={settings?.run_time ?? "16:30"}
              disabled={busy || !settings}
              onChange={(event) => void handleSettingsChange({ run_time: event.target.value })}
            />
          </label>
          <p className="muted">
            上次运行：{settings?.last_run_date ?? "从未运行"}
            <br />
            每天到点后对自选股逐个跑一轮深度投研（串行执行，同一时间只有一个任务在跑）。
          </p>
        </div>
      </div>
    </div>
  );
}
