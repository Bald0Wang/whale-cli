(() => {
  if (window.__WHALE_VIZ_FOUNDATION__) return;
  window.__WHALE_VIZ_FOUNDATION__ = true;

  const root = document.documentElement;
  const body = document.body;
  const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

  function channel(value) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : 255;
  }

  function detectTone() {
    const color = getComputedStyle(body).backgroundColor;
    const match = color.match(/[\d.]+/g);
    if (!match || match.length < 3) return 'light';
    const [r, g, b] = match.map(channel);
    const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    return luminance < 0.42 ? 'dark' : 'light';
  }

  function syncMotionPreference() {
    root.dataset.vizReducedMotion = reduceQuery.matches ? 'true' : 'false';
  }

  function isSelected(control) {
    return control.matches('.active, .selected, .current, [data-active="true"]');
  }

  function enhanceControls() {
    document.querySelectorAll('button').forEach((button) => {
      if (!button.hasAttribute('type')) button.type = 'button';
      if (!button.hasAttribute('aria-label') && !button.textContent.trim() && button.title) {
        button.setAttribute('aria-label', button.title);
      }

      const siblings = button.parentElement
        ? [...button.parentElement.children].filter((item) => item.tagName === 'BUTTON')
        : [];
      if (siblings.length > 1 && siblings.some(isSelected)) {
        button.setAttribute('aria-pressed', isSelected(button) ? 'true' : 'false');
      }
    });

    document.querySelectorAll('[onclick]:not(button):not(a):not(input):not(select)').forEach((control) => {
      if (!control.hasAttribute('role')) control.setAttribute('role', 'button');
      if (!control.hasAttribute('tabindex')) control.tabIndex = 0;
      if (control.dataset.vizKeyboardBound === 'true') return;
      control.dataset.vizKeyboardBound = 'true';
      control.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          control.click();
        }
      });
    });
  }

  function enhanceLiveRegions() {
    const selectors = ['.status', '.result', '.summary', '.counter', '.insight', '[data-viz-status]'];
    document.querySelectorAll(selectors.join(',')).forEach((region) => {
      if (!region.hasAttribute('aria-live')) region.setAttribute('aria-live', 'polite');
    });
  }

  body.dataset.vizTone = detectTone();
  root.classList.add('viz-foundation-ready');
  syncMotionPreference();
  enhanceControls();
  enhanceLiveRegions();

  const observer = new MutationObserver(() => {
    enhanceControls();
    enhanceLiveRegions();
  });
  observer.observe(body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'data-active'] });

  reduceQuery.addEventListener?.('change', syncMotionPreference);

  window.VizLab = Object.freeze({
    prefersReducedMotion: () => reduceQuery.matches,
    announce(message) {
      let announcer = document.getElementById('viz-foundation-announcer');
      if (!announcer) {
        announcer = document.createElement('div');
        announcer.id = 'viz-foundation-announcer';
        announcer.setAttribute('aria-live', 'polite');
        announcer.style.cssText = 'position:fixed;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap';
        body.appendChild(announcer);
      }
      announcer.textContent = '';
      requestAnimationFrame(() => { announcer.textContent = message; });
    },
  });
})();
