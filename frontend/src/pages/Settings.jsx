import { startTransition, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Auth } from '../api.js';
import { ROLE_LABEL, homeFor, useAuth } from '../auth.jsx';
import { Badge, Field, Icon, Skeleton, initials, useAsync, useToast } from '../ui.jsx';

/** Each profile type has its own settings: sellers run a business profile, bidders keep contact/delivery details. */
function ProfileForm({ role, data, onSaved }) {
  const toast = useToast();
  const seller = role === 'SELLER';
  const [f, setF] = useState({ business_name: data.business_name ?? '', phone: data.phone ?? '', address: data.address ?? '' });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (e) => {
    e.preventDefault(); setBusy(true);
    try { onSaved(await Auth.updateProfile(seller ? f : { phone: f.phone, address: f.address })); toast('Profile saved', 'ok'); } catch (x) { toast(x.message, 'err'); } finally { setBusy(false); }
  };
  return (
    <form className="card pad" onSubmit={save}>
      <h3>{seller ? 'Business profile' : 'Contact & delivery'}</h3>
      <p className="faint small" style={{ margin: 0 }}>{seller ? 'Shown to buyers on your listings and used for payouts and handover.' : 'Used by sellers to arrange delivery of items you win.'}</p>
      {seller && <Field label="BUSINESS / SHOP NAME"><input value={f.business_name} maxLength={200} onChange={set('business_name')} placeholder="e.g. Heritage Antiques" /></Field>}
      <Field label="PHONE"><input value={f.phone} maxLength={30} onChange={set('phone')} placeholder="+91 …" autoComplete="tel" /></Field>
      <Field label={seller ? 'PICKUP / BUSINESS ADDRESS' : 'DELIVERY ADDRESS'}><textarea rows={3} value={f.address} maxLength={1000} onChange={set('address')} autoComplete="street-address" /></Field>
      <p><button className="btn gold" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button></p>
    </form>
  );
}

export default function Settings() {
  const { user, profiles, switchTo, removeProfile, logout } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const { loading, data, reload } = useAsync(Auth.profile, [user?.id]);
  const [profile, setProfile] = useState(null);
  useEffect(() => { if (data) setProfile(data); }, [data]);

  const go = async (id) => { const me = await switchTo(id); if (me) { toast(`Switched to ${me.username}`, 'ok'); nav(homeFor(me.role)); } };

  return (
    <div className="wrap page" style={{ maxWidth: 900 }}>
      <div className="eyebrow">{ROLE_LABEL[user.role]}</div>
      <h1>Profile &amp; settings</h1>

      <div className="card pad row" style={{ gap: 18, marginBottom: 22 }}>
        <span className="avatar" style={{ width: 56, height: 56, fontSize: 20 }}>{initials(user.username)}</span>
        <div className="grow">
          <div style={{ font: '600 22px var(--display)' }}>{user.username}</div>
          <div className="mute small">{user.email}</div>
        </div>
        <div className="row">
          <span className={`rolechip ${user.role}`}>{ROLE_LABEL[user.role]}</span>
          <Badge status={user.email_verified ? 'ok' : 'warn'}>{user.email_verified ? 'Email verified' : 'Email not verified'}</Badge>
        </div>
      </div>

      <div className="split" style={{ alignItems: 'start' }}>
        <div className="stack">
          {loading && !profile ? <Skeleton h={300} r={16} /> : profile && user.role !== 'ADMIN' && <ProfileForm key={user.id} role={user.role} data={profile} onSaved={setProfile} />}
          {user.role === 'ADMIN' && <div className="card pad"><h3>Administrator</h3><p className="mute small">Admin accounts have no personal profile to edit. Manage the marketplace from the control room.</p><Link to="/admin" className="btn gold sm">Open control room</Link></div>}
          {profile && user.role === 'SELLER' && (
            <div className="card pad">
              <h3>Seller verification</h3>
              {profile.approved
                ? <p style={{ margin: 0 }}><Badge status="ok">Verified seller</Badge> <span className="mute small">You can list items and request auctions.</span></p>
                : <><p className="mute small">An admin must verify your identity before you can create auctions.{profile.rejection_reason && <> Last note: <b>{profile.rejection_reason}</b></>}</p><Link to="/sell" className="btn sm">Submit documents in your studio</Link></>}
            </div>
          )}
        </div>

        <div className="stack">
          <div className="card pad">
            <h3>Profiles on this device</h3>
            <p className="faint small" style={{ margin: 0 }}>Be a seller in one tab and a bidder in another. Each tab remembers its own profile.</p>
            <div style={{ marginTop: 10 }}>
              {profiles.map((p) => {
                const active = String(p.id) === String(user.id);
                return (
                  <div key={p.id} className="row" style={{ flexWrap: 'nowrap', padding: '10px 0', borderBottom: '1px solid var(--line)' }}>
                    <span className="avatar sm">{initials(p.username)}</span>
                    <div className="grow"><b>{p.username}</b> <span className={`rolechip ${p.role}`}>{ROLE_LABEL[p.role]}</span></div>
                    {active ? <Badge status="ok">This tab</Badge> : <button className="btn ghost sm" onClick={() => go(p.id)}>Switch</button>}
                    <button className="btn ghost sm" aria-label={`Sign out ${p.username}`} onClick={() => (active ? startTransition(() => { nav('/'); logout(); }) : removeProfile(p.id))}>Sign out</button>
                  </div>
                );
              })}
            </div>
            <div className="row" style={{ marginTop: 14 }}>
              <Link to="/register?add=1&role=SELLER" className="btn ghost sm"><Icon name="gavel" size={15} /> Create a seller profile</Link>
              <Link to="/register?add=1&role=BUYER" className="btn ghost sm"><Icon name="bolt" size={15} /> Create a bidder profile</Link>
              <Link to="/login?add=1" className="btn ghost sm">Sign in to another</Link>
            </div>
          </div>

          <div className="card pad">
            <h3>{user.role === 'SELLER' ? 'Seller shortcuts' : user.role === 'BUYER' ? 'Bidder shortcuts' : 'Shortcuts'}</h3>
            <div className="row">
              {user.role === 'SELLER' && <><Link to="/sell" className="btn sm">Seller studio</Link><Link to="/notifications" className="btn ghost sm">Alerts</Link></>}
              {user.role === 'BUYER' && <><Link to="/my-bids" className="btn sm">My bids</Link><Link to="/watchlist" className="btn ghost sm">Watchlist</Link><Link to="/payments" className="btn ghost sm">Payments</Link></>}
              {user.role === 'ADMIN' && <Link to="/admin" className="btn sm">Control room</Link>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
