(() => {
  async function api(path, options = {}, retry = true) {
    const headers = new Headers(options.headers || {});
    const access = localStorage.getItem('access');
    if (access) headers.set('Authorization', `Bearer ${access}`);
    if (options.body && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }
    let response = await fetch(path, { ...options, headers });
    if (response.status === 401 && retry && access) {
      const refresh = localStorage.getItem('refresh');
      if (refresh) {
        const refreshResponse = await fetch('/api/auth/token/refresh/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        });
        if (refreshResponse.ok) {
          const tokens = await refreshResponse.json();
          localStorage.setItem('access', tokens.access);
          return api(path, options, false);
        }
      }
      localStorage.removeItem('access');
      localStorage.removeItem('refresh');
      return api(path, options, false);
    }
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json()
      : await response.text();
    if (!response.ok) {
      const detail = data && typeof data === 'object'
        ? data.detail || Object.entries(data).map(([field, messages]) =>
          `${field}: ${Array.isArray(messages) ? messages.join(', ') : messages}`
        ).join(' · ')
        : data;
      throw new Error(detail || `Request failed (${response.status}).`);
    }
    return data;
  }

  window.marketplace = {
    api,
    items: (data) => Array.isArray(data) ? data : (data && data.results) || [],
    money: (value) => new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: 'USD',
    }).format(Number(value || 0)),
  };
})();
