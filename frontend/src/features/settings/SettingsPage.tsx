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
          <dd>本地工作区</dd>
        </dl>
      </div>
      <div className="panel">
        <div className="panel-heading compact">
          <h2>Runtime Configuration</h2>
          <span className="muted">只读</span>
        </div>
        <dl className="settings-list">
          <dt>LLM Provider</dt>
          <dd>默认模型配置</dd>
          <dt>Reports Directory</dt>
          <dd>本地报告存储</dd>
          <dt>Research Service</dt>
          <dd>未就绪</dd>
        </dl>
      </div>
    </section>
  );
}
