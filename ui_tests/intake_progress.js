// Minimal client-side logic extracted from template to be unit-testable.
function formatProgressText(payload) {
  const displayProgress = (typeof payload.pdf_progress === 'number' && typeof payload.pdf_total === 'number') ? payload.pdf_progress : payload.progress;
  const displayTotal = (typeof payload.pdf_total === 'number' && typeof payload.pdf_progress === 'number') ? payload.pdf_total : payload.total;
  const progressText = displayTotal > 0 ? `${displayProgress} of ${displayTotal} PDFs` : '0 of 0 PDFs';
  const progressPercent = displayTotal > 0 ? Math.round((displayProgress / displayTotal) * 100) : 0;
  return { progressText, progressPercent };
}

module.exports = { formatProgressText };
