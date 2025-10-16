// Minimal Playwright config for the repo tests
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './',
  timeout: 30 * 1000,
  use: {
    headless: true,
    viewport: { width: 1280, height: 800 },
    actionTimeout: 10 * 1000,
  }
});
