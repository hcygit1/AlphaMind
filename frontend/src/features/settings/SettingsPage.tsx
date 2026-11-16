export function SettingsPage() {
  return (
    <section className="page-grid" aria-label="Settings workspace">
      <div className="panel">
        <div className="panel-heading compact">
          <h2>工作区身份</h2>
          <span className="status-pill neutral">默认</span>
        </div>
        <dl className="settings-list">
          <dt>用户</dt>
          <dd>default_user</dd>
          <dt>工作区</dt>
          <dd>default_workspace</dd>
          <dt>会话模式</dt>
          <dd>本地工作区</dd>
        </dl>
      </div>
      <div className="panel">
        <div className="panel-heading compact">
          <h2>运行时配置</h2>
          <span className="muted">只读</span>
        </div>
        <dl className="settings-list">
          <dt>模型提供方</dt>
          <dd>默认模型配置</dd>
          <dt>报告目录</dt>
          <dd>本地报告存储</dd>
          <dt>投研服务</dt>
          <dd>未就绪</dd>
        </dl>
      </div>
    </section>
  );
}
