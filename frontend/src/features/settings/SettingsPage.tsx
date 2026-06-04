export function SettingsPage() {
  return (
    <section className="page-grid" aria-label="Settings workspace">
      <div className="panel">
        <div className="panel-heading compact">
          <h2>Workspace Identity</h2>
          <span className="status-pill neutral">Default</span>
        </div>
        <dl className="settings-list">
          <dt>User</dt>
          <dd>default_user</dd>
          <dt>Workspace</dt>
          <dd>default_workspace</dd>
          <dt>Session Mode</dt>
          <dd>Local MVP</dd>
        </dl>
      </div>
      <div className="panel">
        <div className="panel-heading compact">
          <h2>Runtime Configuration</h2>
          <span className="muted">Read-only shell</span>
        </div>
        <dl className="settings-list">
          <dt>LLM Provider</dt>
          <dd>Configured in backend environment</dd>
          <dt>Reports Directory</dt>
          <dd>results_dir / ticker logs</dd>
          <dt>Legacy UI</dt>
          <dd>web/ retained during Phase 1</dd>
        </dl>
      </div>
    </section>
  );
}
