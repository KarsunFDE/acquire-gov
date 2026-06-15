// Demo capture + CORS proof. Drives the wizard, records console errors and
// failed requests (a CORS block surfaces as both), screenshots key steps.
import pw from 'file:///C:/Users/CharlesJester/AppData/Local/npm-cache/_npx/9833c18b2d85bc59/node_modules/playwright/index.js';
const { chromium } = pw;

const OUT = 'C:/Users/CharlesJester/Documents/2026-Training/KarsunFDE/acquire-gov/docs/diagrams/shots';
const BASE = 'http://localhost:4200';
const fs = await import('node:fs');
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();

const consoleErrors = [];
const failedReqs = [];
const aiResponses = [];
page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('requestfailed', r => failedReqs.push(`${r.method()} ${r.url()} :: ${r.failure()?.errorText}`));
page.on('response', async r => {
  if (r.url().includes('/api/ai/')) {
    aiResponses.push(`${r.status()} ${r.request().method()} ${r.url()} acao=${r.headers()['access-control-allow-origin'] || 'NONE'}`);
  }
});

async function shot(name) { await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true }); console.log('shot', name); }

try {
  // Deep links 404 (nginx has no SPA fallback) — enter via the SPA router:
  // load root, then click through to the wizard.
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(800);
  await shot('00-dashboard');
  await page.getByRole('button', { name: /New solicitation/i }).click();
  await page.waitForTimeout(1000);
  await shot('01-wizard-step1');

  // Fill Step 1 required fields.
  await page.fill('input[formControlName="title"]', 'Cloud Managed Services BPA');
  await page.fill('input[formControlName="agencyId"]', 'GSA-FAS');
  await page.fill('input[formControlName="naics"]', '541512');
  await page.selectOption('select[formControlName="setAside"]', { index: 1 }).catch(() => {});
  await page.selectOption('select[formControlName="contractType"]', { index: 1 }).catch(() => {});
  await page.fill('input[formControlName="agencySupplement"]', 'GSAM').catch(() => {});
  await page.waitForTimeout(400);
  await shot('02-step1-filled');

  // Walk to Section C (steps: Basics0, SecA1, SecB2, SecC3).
  for (let i = 0; i < 3; i++) {
    await page.getByRole('button', { name: /Next/i }).click();
    await page.waitForTimeout(300);
  }
  await shot('03-section-c');

  // Trigger AI-draft on the section card.
  const draftBtn = page.getByRole('button', { name: /AI-draft Section/i }).first();
  if (await draftBtn.count()) {
    await draftBtn.click();
    // Wait for the AI call to resolve (200 draft, or 503 bedrock_unavailable —
    // either proves the browser reached the orchestrator without a CORS block).
    await page.waitForResponse(r => r.url().includes('/api/ai/'), { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(1500);
    await shot('04-after-ai-draft');
  } else {
    console.log('NOTE: AI-draft button not found on Sec C step');
  }

  // Jump to Review (Step 12) to show the critic surface.
  for (let i = 0; i < 8; i++) {
    const next = page.getByRole('button', { name: /Next/i });
    if (await next.count()) { await next.click().catch(() => {}); await page.waitForTimeout(250); }
  }
  await shot('05-review-step12');

} catch (e) {
  console.log('SCRIPT ERROR:', e.message);
  await shot('99-error-state');
} finally {
  console.log('\n=== AI responses (CORS proof) ===');
  aiResponses.forEach(r => console.log(' ', r));
  console.log('\n=== Failed requests ===');
  (failedReqs.length ? failedReqs : ['(none)']).forEach(r => console.log(' ', r));
  console.log('\n=== Console errors ===');
  const cors = consoleErrors.filter(e => /CORS|Access-Control|cross-origin/i.test(e));
  console.log('  CORS-related:', cors.length ? cors.join(' | ') : '(none)');
  console.log('  total console errors:', consoleErrors.length);
  await browser.close();
}
