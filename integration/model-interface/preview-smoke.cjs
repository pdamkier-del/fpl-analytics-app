'use strict';

// Playwright requires this for interception of Chromium worker network requests.
process.env.PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS = '1';

const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const { chromium } = require('playwright');

async function verify() {
  const base = new URL(process.env.FPL_PREVIEW_URL);
  const liveGw = Number(process.env.FPL_EXPECT_LIVE_GW || 0);
  const allowHistorical = process.env.FPL_ALLOW_HISTORICAL === 'true';
  const planFixturePath = process.env.FPL_TEST_PLAN_FIXTURE;
  const fixture = planFixturePath ? JSON.parse(await fs.readFile(planFixturePath, 'utf8')) : null;
  const browser = await chromium.launch({ executablePath: process.env.BROWSER_PATH, args: ['--no-sandbox'] });
  try {
    for (const viewport of [{ width: 390, height: 844 }, { width: 1440, height: 900 }]) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      let submissions = 0;
      await page.route('**/plans**', route => {
        if (route.request().method() !== 'POST') return route.continue();
        submissions++;
        return route.abort();
      });
      async function checkDashboard() {
        if (liveGw) {
          await page.waitForFunction(({ gw, allowHistory }) => {
            const current = window.FplDashboardContext?.();
            return current?.forecast?.gws[0] === gw && (current.usable || allowHistory);
          }, { gw: liveGw, allowHistory: allowHistorical });
        } else {
          await page.waitForFunction(() => window.FplDashboardContext?.()?.usable === false);
        }
      }
      await page.goto(new URL('overview.html', base).href);
      await checkDashboard();
      assert.equal(await page.getByRole('link', { name: /My Team/ }).count(), 0);
      const primary = page.getByRole('navigation', { name: 'FPL Analytics' });
      assert.deepEqual(await primary.getByRole('link').allTextContents(), ['Mit hold', 'Transfers', 'Spillere', 'Avanceret']);
      await primary.getByRole('link', { name: 'Avanceret' }).click();
      await page.getByRole('heading', { name: 'Avanceret' }).waitFor();
      assert.equal(await page.getByRole('link', { name: 'Modelmatematik og versioner' }).count(), 1);
      await page.getByRole('navigation', { name: 'FPL Analytics' }).getByRole('link', { name: 'Mit hold' }).click();
      await checkDashboard();
      await page.getByText('Opdater data og prognoser', { exact: true }).click();
      assert.match(await page.getByRole('link', { name: 'Åbn GitHub Actions' }).getAttribute('href'),
        /\/actions\/workflows\/mm-current-preview-publication\.yml$/);
      await page.waitForFunction(() => /godkendte prognose|Historisk prognose/.test(
        document.getElementById('forecast-refresh-status')?.textContent || ''));
      await page.goto(new URL('my-team-classic.html', base).href);
      await page.waitForURL('**/overview.html');
      await checkDashboard();
      await page.getByRole('heading', { name: 'Mit hold', exact: true }).waitFor();
      assert.equal(await page.locator('#weekly-main').isVisible(), false);
      assert.equal(await page.getByText('Mit hold · nyheder og status', { exact: true }).filter({ visible: true }).count(), 0);
      assert.equal(await page.getByText('Dit gemte hold og din personlige plan i denne browser', { exact: true }).filter({ visible: true }).count(), 0);

      let saved = await page.evaluate(data => {
        const state = data?.state || {
          season: '2026-27', squad: Array.from({ length: 15 }, (_, i) => ({ id: i + 1 })),
        };
        FplManagerStore.save(state);
        if (data) localStorage.setItem('fpl-manager-plan-B-preview-v1', JSON.stringify(data.result));
        return state;
      }, fixture);
      if (!fixture && liveGw) {
        const alerts = await page.evaluate(async () => {
          const news = await FplTeamNews.load();
          const ids = FplDashboardContext().forecast.players.map(player => player.id);
          const flagged = news.players.filter(player => ids.includes(player.id) &&
            (['d', 'i', 's', 'u', 'n'].includes(player.status) || player.recent_red_cards?.length));
          const [owned, other] = flagged;
          if (!owned || !other) return null;
          const squad = [owned.id, ...ids.filter(id => id !== owned.id && id !== other.id).slice(0, 14)];
          FplManagerStore.save({ ...FplManagerStore.read(), squad: squad.map(id => ({ id })) });
          return { owned: owned.id, other: other.id };
        });
        if (alerts) {
          await page.reload();
          const ownedRow = page.locator('#compact-team tr').filter({
            has: page.locator('a[href="player.html?id=' + alerts.owned + '"]'),
          });
          const warning = ownedRow.locator('.compact-player-alert');
          await warning.waitFor();
          assert.equal(await warning.locator('p').isVisible(), false);
          await warning.locator('summary').click();
          assert.equal(await warning.locator('p').isVisible(), true);
          assert.equal(await page.locator('#compact-team a[href="player.html?id=' + alerts.other + '"]').count(), 0);
          saved = await page.evaluate(() => FplManagerStore.read());
        }
      }
      await page.goto(new URL('transfers-classic.html', base).href);
      await page.evaluate(async () => { await FplManagerClient.load(); });
      assert.deepEqual(await page.evaluate(() => FplManagerStore.read()), saved);
      const transferUsable = await page.evaluate(() => FplManagerClient.snapshot().usable);
      if (!allowHistorical || !liveGw) assert.equal(transferUsable, Boolean(liveGw));
      else if (!transferUsable) assert.equal(await page.evaluate(() => FplManagerClient.snapshot().plan), null);
      if (fixture) {
        assert.equal(await page.evaluate(() => FplManagerClient.snapshot().plan?.manager_state_sha256),
          fixture.result.manager_state_sha256);
        saved = await page.evaluate(() => {
          const edited = FplManagerStore.read();
          edited.bank_tenths++;
          FplManagerStore.save(edited);
          return edited;
        });
        await page.reload();
        await page.evaluate(async () => { await FplManagerClient.load(); });
        assert.equal(await page.evaluate(() => FplManagerClient.snapshot().plan), null);
      }

      await page.evaluate(async () => {
        await navigator.serviceWorker.ready;
      });
      await page.waitForFunction(() => !!navigator.serviceWorker.controller);
      const workerPath = process.env.FPL_TEST_WORKER_FILE;
      if (workerPath) {
        const original = await fs.readFile(workerPath, 'utf8');
        const next = original.replace(/const cacheName = cachePrefix \+ '[^']+'/, "const cacheName = cachePrefix + 'smoke-next'");
        assert.notEqual(next, original);
        try {
          await fs.writeFile(workerPath, next);
          await page.evaluate(async () => {
            const registration = await navigator.serviceWorker.ready;
            const updated = new Promise(resolve => {
              navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true });
            });
            await registration.update();
            await Promise.race([updated, new Promise((_, reject) => {
              setTimeout(() => reject(new Error('New worker did not take control')), 10_000);
            })]);
          });
          assert.deepEqual(await page.evaluate(() => FplManagerStore.read()), saved);
          assert(await page.evaluate(async () => (await caches.keys()).some(key => key.endsWith(':smoke-next'))));
        } finally {
          await fs.writeFile(workerPath, original);
        }
      }
      const disconnected = new URL('transfers-classic.html?test-disconnected', base).href;
      let workerNetworkFailed = false;
      await context.route(disconnected, route => {
        if (!route.request().serviceWorker()) return route.continue();
        workerNetworkFailed = true;
        return route.abort('internetdisconnected');
      });
      await page.goto(disconnected, { waitUntil: 'domcontentloaded' });
      await page.getByRole('heading', { name: 'Ingen forbindelse' }).waitFor();
      assert(workerNetworkFailed, 'The service worker must see a failed network request');
      await context.unroute(disconnected);
      await page.goto(new URL('overview.html', base).href, { waitUntil: 'domcontentloaded' });
      await checkDashboard();
      assert.deepEqual(await page.evaluate(() => FplManagerStore.read()), saved);
      assert.equal(submissions, 0);
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

verify().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
