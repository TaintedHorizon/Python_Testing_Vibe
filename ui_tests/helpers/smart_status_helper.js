// Helper to poll /batch/api/smart_processing_status from Playwright JS tests.
// Usage:
// const { pollSmartProcessingStatus } = require('./helpers/smart_status_helper');
// const { lastEvent, meta } = await pollSmartProcessingStatus(page, token, { baseUrl });

async function pollSmartProcessingStatus(pageOrRequest, token, opts = {}) {
  const baseUrl = opts.baseUrl || process.env.BASE_URL || 'http://127.0.0.1:5000'
  const maxPolls = opts.maxPolls || 60
  const stallLimit = opts.stallLimit || 10
  const pollInterval = opts.pollInterval || 1000

  // pageOrRequest may be a Playwright `page` or `APIRequestContext` (page.request)
  const requestCtx = pageOrRequest.request ? pageOrRequest.request : pageOrRequest

  let lastProgress = null
  let stallCount = 0
  let lastEvent = null

  for (let i = 0; i < maxPolls; i++) {
    try {
      const resp = await requestCtx.get(`${baseUrl}/batch/api/smart_processing_status?token=${encodeURIComponent(token)}`)
      const body = await resp.json()
      lastEvent = body?.data?.last_event ?? null
      if (lastEvent && typeof lastEvent === 'object') {
        const prog = lastEvent.progress
        const complete = Boolean(lastEvent.complete)
        if (typeof prog !== 'undefined' && prog !== null) {
          if (prog !== lastProgress) {
            lastProgress = prog
            stallCount = 0
          } else {
            stallCount += 1
          }
        } else {
          stallCount += 1
        }
        if (complete) {
          return { lastEvent, meta: { polls: i + 1, stalled: false, completed: true, lastProgress } }
        }
        if (stallCount >= stallLimit) {
          return { lastEvent, meta: { polls: i + 1, stalled: true, completed: false, lastProgress } }
        }
      }
    } catch (e) {
      // ignore and retry
    }
    await new Promise(r => setTimeout(r, pollInterval))
  }
  return { lastEvent, meta: { polls: maxPolls, stalled: stallCount >= stallLimit, completed: false, lastProgress } }
}

module.exports = { pollSmartProcessingStatus }
