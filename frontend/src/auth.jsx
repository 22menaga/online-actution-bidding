import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Auth, tokens } from './api.js';

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

/** Where each kind of profile lands after signing in. */
export const homeFor = (role) => (role === 'SELLER' ? '/sell' : role === 'ADMIN' ? '/admin' : '/auctions');

export const ROLE_LABEL = { BUYER: 'Bidder', SELLER: 'Seller studio', ADMIN: 'Admin' };

/**
 * Multi-profile auth. Every signed-in profile is kept on the device; each browser TAB remembers which one it is using,
 * so one tab can be a seller while another is a bidder at the same time.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(!tokens.access);
  const [profiles, setProfiles] = useState(() => tokens.list());

  const syncProfiles = useCallback(() => setProfiles(tokens.list()), []);

  const loadMe = useCallback(async () => {
    if (!tokens.access) { setUser(null); setReady(true); return null; }
    try { const me = await Auth.me(); setUser(me); setReady(true); return me; } catch { setUser(null); setReady(true); return null; } // a 401 signs out via 'auth:expired'; a network blip must not
  }, [syncProfiles]);

  useEffect(() => { if (tokens.access) loadMe(); }, [loadMe]);

  useEffect(() => { // role colours for the whole UI
    document.documentElement.dataset.role = user?.role ?? 'GUEST';
  }, [user?.role]);

  useEffect(() => {
    const expired = () => { tokens.clear(); syncProfiles(); setUser(null); setReady(true); };
    // another tab added/removed a profile: keep the list fresh (this tab's own active profile is unaffected)
    const storage = (e) => { if (e.key === null || e.key === 'accounts') { syncProfiles(); if (tokens.active == null) { setUser(null); setReady(true); } } };
    window.addEventListener('auth:expired', expired);
    window.addEventListener('storage', storage);
    return () => { window.removeEventListener('auth:expired', expired); window.removeEventListener('storage', storage); };
  }, [syncProfiles]);

  const value = useMemo(() => ({
    user,
    ready,
    profiles,
    activeId: user?.id ?? null,
    reload: loadMe,
    /** Sign in and make this profile active in THIS tab, keeping other profiles signed in. */
    login: async (username, password) => {
      const me = await Auth.login(username, password);
      syncProfiles(); setUser(me); setReady(true);
      return me;
    },
    /** Switch this tab to another signed-in profile instantly. */
    switchTo: async (id) => {
      tokens.switch(id); syncProfiles(); setReady(false);
      return loadMe();
    },
    /** Sign out of the profile this tab is using (other profiles stay signed in). */
    logout: () => { Auth.revoke(tokens.refresh); tokens.clear(); syncProfiles(); setUser(null); setReady(true); },
    removeProfile: (id) => {
      const wasActive = String(id) === String(tokens.active);
      Auth.revoke(tokens.list().find((p) => String(p.id) === String(id))?.refresh);
      tokens.remove(id); syncProfiles();
      if (wasActive) { setUser(null); if (tokens.access) loadMe(); else setReady(true); }
    },
  }), [user, ready, profiles, loadMe, syncProfiles]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
