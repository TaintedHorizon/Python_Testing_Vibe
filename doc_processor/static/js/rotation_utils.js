/* Shared rotation & scaling utilities for PDF/image iframes.
 * Centralizes logic so analysis + manipulation views stay in sync.
 */
(function(global){
  const state = new WeakMap(); // element -> { fitMode, lastScale, hadNonZero }
  const FIT_MODES = { AUTO:'auto', WIDTH:'width', HEIGHT:'height' };

  function computeScale(el, angle, mode){
    const container = el.parentElement;
    if(!container) return 1;
    const cw = container.clientWidth || 1;
    const ch = container.clientHeight || 1;
    // Approximate intrinsic size (fallback to container if unknown)
    const iw = el.dataset.intrinsicWidth ? parseFloat(el.dataset.intrinsicWidth) : cw;
    const ih = el.dataset.intrinsicHeight ? parseFloat(el.dataset.intrinsicHeight) : ch;
    const rotatedSwap = angle % 180 !== 0;
    const rw = rotatedSwap ? ih : iw;
    const rh = rotatedSwap ? iw : ih;

    if(mode === FIT_MODES.WIDTH){ return cw / rw; }
    if(mode === FIT_MODES.HEIGHT){ return ch / rh; }
    // AUTO: choose the smaller scale that fits both dimensions
    return Math.min(cw / rw, ch / rh);
  }

  function ensureBadge(el){
    let badge = el.parentElement.querySelector('.rotation-badge');
    if(!badge){
      badge = document.createElement('div');
      badge.className = 'rotation-badge';
      badge.style.cssText = 'position:absolute;top:6px;right:8px;background:rgba(0,0,0,0.55);color:#fff;font-size:12px;padding:2px 6px;border-radius:12px;font-family:system-ui,Arial,sans-serif;pointer-events:none;z-index:5;transition:opacity .25s;';
      el.parentElement.style.position = 'relative';
      el.parentElement.appendChild(badge);
    }
    return badge;
  }

  const RotationUtils = {
    async fetchRotation(docId){
      try {
        const r = await fetch(`/api/rotation/${docId}`);
        const j = await r.json();
        if(!j.success) return 0;
        return (j.data && j.data.rotation) || 0;
      } catch(e){
        console.warn('[RotationUtils] fetchRotation failed', e); return 0;
      }
    },
    async saveRotation(docId, angle){
      try {
        const r = await fetch(`/api/rotation/${docId}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ rotation: angle })});
        const j = await r.json();
        if(!j.success) throw new Error(j.error || 'save failed');
        return true;
      } catch(e){ console.error('[RotationUtils] saveRotation failed', e); return false; }
    },
    setFitMode(el, mode){
      if(!el) return;
      const rec = state.get(el) || { fitMode: FIT_MODES.AUTO };
      rec.fitMode = mode in FIT_MODES ? mode : mode; // accept passed string if custom
      state.set(el, rec);
    },
    cycleFitMode(el){
      if(!el) return 'auto';
      const order = [FIT_MODES.AUTO, FIT_MODES.WIDTH, FIT_MODES.HEIGHT];
      const rec = state.get(el) || { fitMode: FIT_MODES.AUTO };
      const idx = order.indexOf(rec.fitMode);
      rec.fitMode = order[(idx + 1) % order.length];
      state.set(el, rec);
      return rec.fitMode;
    },
    applyScaledRotation(el, angle){
      if(!el){ return; }
      if(!Number.isFinite(angle)) angle = 0;
      angle = ((angle % 360) + 360) % 360;
      const rec = state.get(el) || { fitMode: FIT_MODES.AUTO, lastScale:1, hadNonZero:false };
      state.set(el, rec);
      const mode = rec.fitMode;

      // Always compute a candidate scale (even for angle 0) so landscape pages after
      // physical rotation still shrink to fit without requiring a manual fit-mode toggle.
      let scale = computeScale(el, angle, mode) || 1;

      // Heuristic: if we just returned to angle 0 (e.g. after server-side apply) and
      // auto mode reports scale 1 but we previously displayed a smaller scaled view,
      // reuse that prior scale to avoid sudden clipping of wide/landscape pages.
      if(angle === 0 && mode === FIT_MODES.AUTO){
        if(scale === 1 && rec.hadNonZero && rec.lastScale && rec.lastScale < 1){
          scale = rec.lastScale; // preserve prior fit
        }
        // Reset hadNonZero so subsequent manual resets don't keep stale scale
        rec.hadNonZero = false;
      } else if(angle !== 0){
        rec.hadNonZero = true;
      }

      rec.lastScale = scale;
      el.style.transform = `rotate(${angle}deg) scale(${scale})`;
      this.updateBadge(el, angle, mode);
    },
    updateBadge(el, angle, mode){
      const badge = ensureBadge(el);
      const label = angle === 0 ? '0°' : `${angle}°`;
      badge.textContent = `${label} · ${mode}`;
      badge.style.opacity = '1';
      clearTimeout(badge._fadeTimer);
      badge._fadeTimer = setTimeout(()=>{ badge.style.opacity='0.4'; }, 1800);
    },
    reset(el){ if(el){
        const rec = state.get(el) || { fitMode: FIT_MODES.AUTO };
        rec.lastScale = 1; rec.hadNonZero = false;
        state.set(el, rec);
        el.style.transform='rotate(0deg) scale(1)';
        this.updateBadge(el, 0, rec.fitMode);
      } },
    // Deprecated physical rotation path removed; logical rotation is auto-saved.
    FIT_MODES
  };
  global.RotationUtils = RotationUtils;
})(window);
