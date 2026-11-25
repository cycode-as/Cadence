/**
 * CADENCE Scroll Position Cache
 * Saves and restores scroll position on back navigation
 */
(function () {
  const SCROLL_CACHE_KEY = 'cadence-scroll-cache';
  
  function saveScrollPosition() {
    const scrollData = {
      path: window.location.pathname,
      position: window.scrollY,
      timestamp: Date.now()
    };
    sessionStorage.setItem(SCROLL_CACHE_KEY, JSON.stringify(scrollData));
  }
  
  function restoreScrollPosition() {
    const cached = sessionStorage.getItem(SCROLL_CACHE_KEY);
    if (!cached) return;
    
    const data = JSON.parse(cached);
    if (data.path === window.location.pathname && Date.now() - data.timestamp < 60000) {
      window.scrollTo(0, data.position);
      sessionStorage.removeItem(SCROLL_CACHE_KEY);
    }
  }
  
  window.addEventListener('beforeunload', saveScrollPosition);
  window.addEventListener('DOMContentLoaded', restoreScrollPosition);
})();
