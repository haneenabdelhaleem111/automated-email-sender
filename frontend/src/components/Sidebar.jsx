import { Activity, Clock3, LayoutDashboard, Mail, Send, X } from "lucide-react";

const items = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "compose", label: "Compose email", icon: Mail },
  { id: "history", label: "Email history", icon: Clock3 },
];

export function BrandMark({ compact = false }) {
  return (
    <span className={`brand-lockup${compact ? " brand-lockup-compact" : ""}`}>
      <span className="brand-mark" aria-hidden="true"><Send size={17} strokeWidth={2.4} /></span>
      {!compact && <span className="brand-name">mail<span>flow</span></span>}
    </span>
  );
}

export function Sidebar({ activeView, onNavigate, mobileOpen, onClose }) {
  return (
    <>
      <button
        className={`sidebar-scrim${mobileOpen ? " is-visible" : ""}`}
        type="button"
        aria-label="Close navigation menu"
        onClick={onClose}
        tabIndex={mobileOpen ? 0 : -1}
      />
      <aside className={`sidebar${mobileOpen ? " sidebar-open" : ""}`} aria-label="Main navigation">
        <div className="sidebar-brand-row">
          <BrandMark />
          <button className="icon-button sidebar-close" type="button" onClick={onClose} aria-label="Close menu">
            <X size={19} />
          </button>
        </div>

        <div className="workspace-switcher">
          <span className="workspace-avatar" aria-hidden="true">M</span>
          <span className="workspace-copy"><strong>MailFlow</strong><small>Email workspace</small></span>
          <span className="workspace-caret" aria-hidden="true">⌄</span>
        </div>

        <p className="nav-label">WORKSPACE</p>
        <nav className="primary-nav">
          {items.map(({ id, label, icon: Icon }) => (
            <button
              className={`nav-item${activeView === id ? " nav-item-active" : ""}`}
              type="button"
              key={id}
              onClick={() => { onNavigate(id); onClose(); }}
              aria-current={activeView === id ? "page" : undefined}
              title={label}
            >
              <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
              <span>{label}</span>
              {id === "history" && <span className="nav-item-arrow" aria-hidden="true">›</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-spacer" />
        <div className="sidebar-status">
          <span className="sidebar-status-icon"><Activity size={17} /></span>
          <div><strong>Built for thoughtful sending</strong><p>Every request, clearly tracked.</p></div>
        </div>
        <div className="sidebar-footer"><span className="status-dot" /> SMTP delivery powered by your API</div>
      </aside>
    </>
  );
}
