/* Shared rotation & scaling utilities for PDF/image iframes.
 * Centralizes logic so analysis + manipulation views stay in sync.
 */
(function(global){
  const RotationUtils = {
    applyScaledRotation(el, angle){
      if(!el){ return; }
      if(!Number.isFinite(angle)) angle = 0;
      angle = ((angle % 360) + 360) % 360;
      if(angle === 0){ el.style.transform='rotate(0deg)'; return; }
      const container = el.parentElement;
      if(!container){ el.style.transform=`rotate(${angle}deg)`; return; }
      const cw = container.clientWidth || 1;
      const ch = container.clientHeight || 1;
      if(angle % 180 === 0){ el.style.transform = `rotate(${angle}deg)`; return; }
      // 90/270 case: approximate fit by minimizing overflow. Use geometric mean heuristic.
      const scale = Math.min(cw/ch, ch/cw) || 0.75;
      el.style.transform = `rotate(${angle}deg) scale(${scale})`;
    },
    reset(el){ if(el){ el.style.transform='rotate(0deg)'; } }
  };
  global.RotationUtils = RotationUtils;
})(window);
