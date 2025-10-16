const { formatProgressText } = require('./intake_progress');

test('uses pdf_progress/pdf_total when present', () => {
  const payload = { pdf_progress: 2, pdf_total: 5, message: 'Analyzing' };
  const { progressText, progressPercent } = formatProgressText(payload);
  expect(progressText).toBe('2 of 5 PDFs');
  expect(progressPercent).toBe(40);
});

test('falls back to progress/total when pdf_* missing', () => {
  const payload = { progress: 3, total: 6, message: 'Analyzing' };
  const { progressText, progressPercent } = formatProgressText(payload);
  expect(progressText).toBe('3 of 6 PDFs');
  expect(progressPercent).toBe(50);
});
