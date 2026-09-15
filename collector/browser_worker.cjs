// Controlled Playwright bridge. Python 3.12 owns scheduling/configuration/results.
const fs = require('node:fs');
const path = require('node:path');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  const job = JSON.parse(input);
  let browser;
  try {
    const {chromium} = require(job.runtime.playwright_module);
    browser = await chromium.launch({headless: true, executablePath: job.runtime.chromium});
    for (const task of job.pages) {
      let context;
      // Fixed diagnostic stages only: no selector, URL, DOM or credentials in output.
      let stage = 'context';
      const started = new Date().toISOString();
      try {
        context = await browser.newContext({viewport: job.profile.viewport, deviceScaleFactor: 1,
          locale: job.profile.locale, timezoneId: job.profile.timezone,
          colorScheme: job.profile.color_scheme || 'light',
          storageState: job.auth_state || undefined, serviceWorkers: 'block'});
        // Network origin policy includes redirects and subresources. No arbitrary script/actions from config.
        await context.route('**/*', async route => {
          const url = route.request().url();
          if (job.allowed_origins.includes(new URL(url).origin)) await route.continue();
          else await route.abort('blockedbyclient');
        });
        const page = await context.newPage();
        page.setDefaultTimeout(job.profile.timeout_ms);
        page.setDefaultNavigationTimeout(job.profile.navigation_timeout_ms || job.profile.timeout_ms);
        if (job.login) {
          stage = 'login_navigation';
          const loginResponse = await page.goto(job.login.url, {waitUntil: 'domcontentloaded'});
          if (!loginResponse || !loginResponse.ok()) throw new Error('LoginNavigation');
          stage = 'login_username';
          await page.locator(job.login.username_selector).fill(job.credentials.username);
          stage = 'login_password';
          await page.locator(job.login.password_selector).fill(job.credentials.password);
          stage = 'login_submit';
          await page.locator(job.login.submit_selector).click();
          stage = 'login_success';
          await page.locator(job.login.success_selector).waitFor({state: 'visible'});
          // A hash-only goto after SPA login returns null despite successful navigation.
          // Keep this browsing context/tab so sessionStorage authentication survives,
          // but leave the document before registering target API listeners. The target
          // then makes a full HTTP navigation whose status can still be checked.
          stage = 'navigation_reset';
          await page.goto('about:blank', {waitUntil: 'domcontentloaded'});
        }
        // Register every response listener BEFORE navigation so fast startup API calls are retained.
        // Attach rejection handlers immediately; a failed navigation must not leave an unhandled rejection.
        const responses = (task.wait_for_responses || []).map(wait => {
          const timeout = job.profile.api_timeout_ms || job.profile.timeout_ms;
          let timer;
          const deadline = new Promise((_, reject) => { timer = setTimeout(() => {
            const error = new Error('ResponseTimeout'); error.name = 'TimeoutError'; reject(error);
          }, timeout); });
          const complete = page.waitForResponse(response =>
            response.url() === wait.url && response.request().method() === wait.method && response.status() === wait.status,
            {timeout}).then(async response => {
              const failed = await response.finished();
              if (failed) throw new Error('ResponseIncomplete');
              return {ok: true};
            });
          return Promise.race([complete, deadline]).catch(error => ({ok: false, timeout: error.name === 'TimeoutError'}))
            .finally(() => clearTimeout(timer));
        });
        stage = 'navigation';
        const response = await page.goto(task.url, {waitUntil: 'domcontentloaded'});
        if (!response || !response.ok()) throw new Error('NavigationStatus');
        stage = 'api_wait';
        for (const pending of responses) {
          const result = await pending;
          if (!result.ok) {
            const error = new Error('ResponseWaitFailed');
            if (result.timeout) error.name = 'TimeoutError';
            throw error;
          }
        }
        stage = 'ready';
        await page.locator(task.ready_selector).waitFor({state: 'visible'});
        stage = 'fonts';
        await page.evaluate(() => document.fonts.ready);
        stage = 'masks';
        const masks = (task.masks || []).map(s => page.locator(s));
        for (const mask of masks) {
          if (await mask.count() === 0) throw new Error('MissingMask');
        }
        if (job.credentials) {
          // Account identifiers echoed in a dashboard must not become capture evidence.
          masks.push(page.locator(job.login.username_selector));
          masks.push(page.locator(job.login.password_selector));
          masks.push(page.getByText(job.credentials.username, {exact: false}));
          masks.push(page.getByText(job.credentials.password, {exact: false}));
        }
        const files = [];
        const take = async (index, element) => {
          stage = 'capture';
          const file = `${task.output_prefix || task.id}-${String(index).padStart(3, '0')}.png`;
          const target = path.resolve(job.output, file);
          const relative = path.relative(path.resolve(job.output), target);
          if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('UnsafeOutput');
          fs.mkdirSync(path.dirname(target), {recursive: true});
          const options = {path: target, animations: 'disabled', caret: 'hide', mask: masks, maskColor: '#222222', timeout: job.profile.timeout_ms};
          if (element) await element.screenshot(options); else await page.screenshot({...options, fullPage: false});
          files.push(file);
        };
        if (task.mode === 'element') {
          stage = 'capture';
          const element = page.locator(task.selector);
          const box = await element.boundingBox();
          if (!box || box.width * box.height > 16000000) throw new Error('ElementTooLarge');
          await take(1, element);
        } else if (task.mode === 'viewport') {
          await take(1);
        } else {
          const step = job.profile.viewport.height - job.profile.overlap_px;
          let previous = -1;
          for (let i = 0; ; i++) {
            stage = 'segment_scroll';
            if (i >= job.profile.max_segments) throw new Error('SegmentLimit');
            await page.evaluate(y => window.scrollTo(0, y), i * step);
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            const state = await page.evaluate(() => ({y: window.scrollY, bottom: window.scrollY + window.innerHeight, height: document.documentElement.scrollHeight}));
            if (state.y === previous) throw new Error('ScrollStalled');
            previous = state.y;
            await take(i + 1);
            if (state.bottom >= state.height - 1) break;
          }
        }
        process.stdout.write(JSON.stringify({id: task.id, status: 'passed', files, started, finished: new Date().toISOString(), pid: process.pid}) + '\n');
      } catch (error) {
        // Do not leak query strings, DOM, cookies, or storageState in errors.
        process.stdout.write(JSON.stringify({id: task.id, status: 'failed', error: error.name === 'TimeoutError' ? 'Timeout' : 'CaptureFailed', stage, started, finished: new Date().toISOString(), pid: process.pid}) + '\n');
      } finally { if (context) await context.close(); }
    }
  } catch (_) { process.exitCode = 1; }
  finally { if (browser) await browser.close(); }
});
