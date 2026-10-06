/* Install only after owner approval; integrate with the shop's actual CMP.
 * No cookies/storage/events until setConsent(true). No purchase events from browser.
 * config: window.KlimanwavesConfig = {endpoint: 'https://YOUR-HOST/api/track'};
 */
(() => {
  'use strict';
  let consent = false;
  let session = null;
  let attribution = null;
  const keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];
  window.Klimanwaves = {
    setConsent(granted) {
      consent = granted === true;
      if (!consent) {
        session = null; attribution = null;
        sessionStorage.removeItem('kw_session');
        sessionStorage.removeItem('kw_attribution');
        return;
      }
      session = sessionStorage.getItem('kw_session') || crypto.randomUUID();
      sessionStorage.setItem('kw_session', session);
      const params = new URLSearchParams(location.search);
      try { attribution = JSON.parse(sessionStorage.getItem('kw_attribution') || 'null'); } catch { attribution = null; }
      if (!attribution || keys.some(k => params.has(k))) {
        attribution = Object.fromEntries(keys.map(k => [k, (params.get(k) || '').slice(0, 200)]));
        sessionStorage.setItem('kw_attribution', JSON.stringify(attribution));
      }
      this.track('landing_page');
    },
    async track(name) {
      if (!consent || !session) return {skipped: true};
      if (!['landing_page', 'product_view', 'add_to_cart', 'checkout'].includes(name)) throw new Error('Nepodporovaná událost');
      const endpoint = window.KlimanwavesConfig?.endpoint;
      if (!endpoint || !endpoint.startsWith('https://')) throw new Error('Nastavte HTTPS tracking endpoint');
      const response = await fetch(endpoint, {
        method: 'POST', credentials: 'omit', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: crypto.randomUUID(), name, session_id: session, consent: true,
          creative_id: attribution?.utm_content || null, attribution})
      });
      if (!response.ok) throw new Error('Měření nebylo potvrzeno');
      return response.json();
    }
  };
})();
