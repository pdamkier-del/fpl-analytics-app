'use strict';

const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.SITE_CHROME, args: ['--no-sandbox'] });
  try {
    for (const width of [390, 1440]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const base = 'http://127.0.0.1:18098/';
      for (const name of ['my-team-classic.html', 'transfers-classic.html', 'players-classic.html', 'advanced.html']) {
        const response = await page.goto(base + name, { waitUntil: 'domcontentloaded' });
        assert.equal(response.status(), 200);
        const nav = page.getByRole('navigation', { name: 'FPL Analytics' });
        await nav.waitFor();
        assert.deepEqual(await nav.getByRole('link').allTextContents(), ['Mit hold', 'Transfers', 'Spillere', 'Avanceret']);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        if (name === 'my-team-classic.html') await page.getByRole('link', { name: 'Opdater data og prognoser' }).waitFor();
      }
      console.log(width + 'px: normal Pages navigation passed');
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
