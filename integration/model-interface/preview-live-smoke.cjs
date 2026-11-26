'use strict';

const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const path = require('node:path');

async function verify() {
  const base = new URL(process.env.FPL_PREVIEW_URL);
  assert.equal(base.hostname, '127.0.0.1', 'Test finances may only go to the loopback preview');
  const entry = process.env.FPL_PUBLIC_TEST_ENTRY;
  assert.match(entry || '', /^[1-9][0-9]{0,8}$/);
  const alternate = process.env.FPL_ALTERNATE_CAPTURE;
  const widths = process.env.FPL_TEST_WIDTH ? [Number(process.env.FPL_TEST_WIDTH)] : [390, 1440];
  const browser = await chromium.launch({ executablePath: process.env.BROWSER_PATH, args: ['--no-sandbox'] });
  try {
    for (const width of widths) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: alternate ? 'block' : 'allow' });
      const page = await context.newPage();
      await page.goto(new URL('manager-state.html', base).href);
      await page.waitForFunction(() => document.querySelectorAll('#squad tr').length === 15);
      await page.locator('#manager-import-entry').fill(entry);
      await page.locator('#import-manager').click();
      await page.waitForFunction(() => document.querySelector('#manager-import-status').textContent.startsWith('Kladde'));
      const imported = await page.evaluate(async () => {
        const draft = JSON.parse(localStorage.getItem('fpl-manager-draft-v1'));
        const catalogue = await (await fetch('current-players.json')).json();
        const prices = new Map(catalogue.players.map(player => [player.id, player.price]));
        return draft.squad.map(player => ({ id: player.id, price: prices.get(player.id) }));
      });
      assert.equal(imported.length, 15);
      assert.equal(await page.locator('#bank').inputValue(), '');
      assert.equal(await page.locator('#ft').inputValue(), '');
      assert.equal(await page.locator('#squad input').first().inputValue(), '');
      await page.locator('#source').fill('LOCAL TEST ONLY — OFFICIAL PICKS WITH SYNTHETIC FINANCES');
      await page.locator('#bank').fill('1.0');
      await page.locator('#ft').fill('2');
      await page.locator('#observed').fill(new Date(Date.now() - 1500).toISOString().slice(0, 19));
      for (const [index, player] of imported.entries()) {
        await page.locator('#squad input').nth(index).fill(player.price.toFixed(1));
      }
      await page.locator('#confirmed').check();
      await page.locator('#save').click();
      const confirmed = await page.evaluate(() => FplManagerStore.read());
      assert.deepEqual(confirmed.squad.map(player => player.id), imported.map(player => player.id));

      await page.goto(new URL('overview.html', base).href);
      await page.waitForFunction(() => window.FplDashboardContext?.().state?.squad.length === 15);
      assert.deepEqual(await page.evaluate(() => FplDashboardContext().state.squad.map(player => player.id)),
        confirmed.squad.map(player => player.id));
      await page.goto(new URL('transfers-classic.html', base).href);
      await page.evaluate(async () => { await FplManagerClient.load(); });
      assert(await page.evaluate(() => FplManagerClient.snapshot().usable));
      const response = page.waitForResponse(r =>
        r.url().endsWith('/preview-api/preview/plans') && r.request().method() === 'POST');
      const completed = page.waitForResponse(async r => r.url().includes('/preview-api/plans/') &&
        ['completed', 'failed'].includes((await r.json()).status), { timeout: 240_000 });
      await page.locator('[data-compute]').first().click();
      assert.equal((await response).status(), 202);
      assert.equal((await (await completed).json()).status, 'completed');
      await page.waitForFunction(() => FplManagerClient.snapshot().plan?.plan.path.length === 6);
      const binding = await page.evaluate(async () => {
        const { forecast, plan } = FplManagerClient.snapshot();
        return plan.forecast_sha256 === forecast.forecast_sha256 &&
          plan.manager_state_sha256 === await FplManagerClient.hash(FplManagerStore.read());
      });
      assert(binding);
      assert(await page.evaluate(() => {
        const { plan } = FplManagerClient.snapshot();
        return Number.isFinite(plan.comparison.plan_gain_over_hold) &&
          !!plan.chip_assessment.availability && typeof plan.chip_assessment.tc_status === 'string';
      }));

      if (alternate) {
        const originalHash = await page.evaluate(() => FplManagerClient.snapshot().forecast.forecast_sha256);
        const pattern = /\/mm-preview\/(current|gk)\/[^/?]+\.json$/;
        await page.route(pattern, route => {
          const [folder, name] = new URL(route.request().url()).pathname.split('/').slice(-2);
          return route.fulfill({ path: path.join(alternate, folder, name), contentType: 'application/json' });
        });
        await page.reload();
        await page.evaluate(async () => { await FplManagerClient.load(); });
        assert.notEqual(await page.evaluate(() => FplManagerClient.snapshot().forecast.forecast_sha256), originalHash);
        assert.equal(await page.evaluate(() => FplManagerClient.snapshot().plan), null);
        assert.deepEqual(await page.evaluate(() => FplManagerStore.read()), confirmed);
        await page.unroute(pattern);
        await page.reload();
        await page.evaluate(async () => { await FplManagerClient.load(); });
        assert(await page.evaluate(() => !!FplManagerClient.snapshot().plan));
        console.log(width + 'px: a different sealed forecast invalidated only the transfer plan');
      }

      await page.evaluate(() => {
        const state = FplManagerStore.read();
        FplManagerStore.save({ ...state, bank_tenths: state.bank_tenths + 1 });
      });
      await page.reload();
      await page.evaluate(async () => { await FplManagerClient.load(); });
      assert.equal(await page.evaluate(() => FplManagerClient.snapshot().plan), null);
      assert.equal(await page.evaluate(() => FplManagerStore.read().bank_tenths), 11);
      console.log(width + 'px: official import, confirmation, six-GW TS job, bank invalidation and reload passed');
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
