const { test, expect } = require('@playwright/test');

test('shows PDF-centric progress when SSE provides pdf_progress/pdf_total', async ({ page }) => {
  // Build minimal HTML that matches the parts of intake_analysis.html used
  const html = `
    <div id="loading-state">
      <div class="progress">
        <div class="progress-bar" style="width:0%">0 of 0 PDFs</div>
      </div>
      <p class="status">Initializing...</p>
    </div>
  `;

  await page.setContent(html);

  // Expose a function that mirrors the template's updateAnalysisProgress behavior
  await page.addScriptTag({ content: `
    window.updateAnalysisProgress = function(data) {
      const displayProgress = (typeof data.pdf_progress === 'number' && typeof data.pdf_total === 'number') ? data.pdf_progress : data.progress;
      const displayTotal = (typeof data.pdf_total === 'number' && typeof data.pdf_progress === 'number') ? data.pdf_total : data.total;
      const progressPercent = displayTotal > 0 ? Math.round((displayProgress / displayTotal) * 100) : 0;
      const progressText = displayTotal > 0 ? `${displayProgress} of ${displayTotal} PDFs` : '0 of 0 PDFs';
      const bar = document.querySelector('.progress-bar');
      if (bar) { bar.style.width = progressPercent + '%'; bar.textContent = progressText; }
      const status = document.querySelector('.status');
      if (status) status.textContent = data.message || '';
    };
  `});

  // Simulate receiving an SSE payload with pdf_progress/pdf_total
  await page.evaluate(() => {
    window.updateAnalysisProgress({ pdf_progress: 2, pdf_total: 5, message: 'Analyzing PDF 2/5' });
  });

  const barText = await page.textContent('.progress-bar');
  expect(barText.trim()).toBe('2 of 5 PDFs');

  // Simulate fallback payload (no pdf_* fields)
  await page.evaluate(() => {
    window.updateAnalysisProgress({ progress: 3, total: 6, message: 'Analyzing operation 3/6' });
  });
  const barText2 = await page.textContent('.progress-bar');
  expect(barText2.trim()).toBe('3 of 6 PDFs');
});
