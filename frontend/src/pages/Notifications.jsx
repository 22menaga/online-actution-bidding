import { Notifications as Api } from '../api.js';
import { EmptyState, Icon, Skeleton, useAsync } from '../ui.jsx';

const kindOf = (t = '') => /outbid/i.test(t) ? ['⚡', 'warn'] : /won|sold/i.test(t) ? ['🏆', 'ok'] : /payment/i.test(t) ? ['💳', 'ok'] : /bid/i.test(t) ? ['🔨', ''] : ['🔔', ''];

const ago = (iso) => {
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso)) / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
};

export default function Notifications() {
  const { loading, data, reload } = useAsync(Api.list, []);
  const changed = () => { window.dispatchEvent(new Event('notifications:changed')); return reload(); };
  const markRead = async (n) => { await Api.read(n.id); changed(); };
  const unread = data?.results.filter((n) => !n.read_at) ?? [];
  const markAll = async () => { await Promise.all(unread.map((n) => Api.read(n.id))); changed(); };

  return (
    <div className="wrap page" style={{ maxWidth: 760 }}>
      <div className="row between">
        <div><div className="eyebrow">Inbox</div><h1 style={{ margin: 0 }}>Alerts</h1></div>
        {unread.length > 0 && <button className="btn ghost sm" onClick={markAll}><Icon name="check" size={14} /> Mark all read ({unread.length})</button>}
      </div>
      <div className="stack" style={{ marginTop: 22 }}>
        {loading ? <Skeleton h={90} r={16} /> : data.results.length === 0 ? (
          <EmptyState icon="🔔" title="You're all caught up">Outbid alerts, wins and payment updates will appear here.</EmptyState>
        ) : data.results.map((n) => {
          const [emoji, tone] = kindOf(n.title);
          return (
            <div key={n.id} className="card pad row" style={{ flexWrap: 'nowrap', alignItems: 'flex-start', opacity: n.read_at ? 0.6 : 1, borderLeft: n.read_at ? undefined : '3px solid var(--gold2)' }}>
              <span style={{ fontSize: 26 }}>{emoji}</span>
              <div className="grow">
                <div className="row between"><b>{n.title}</b><span className="faint small">{ago(n.created_at)}</span></div>
                <p className="mute" style={{ margin: '4px 0 0' }}>{n.body}</p>
                {!n.read_at && <button className={`btn ghost sm ${tone}`} style={{ marginTop: 10 }} onClick={() => markRead(n)}>Mark read</button>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
