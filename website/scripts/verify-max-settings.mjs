/** Built-SPA fixture preflight. No gateway, auth exchange or MAX network calls.
 * Run on a host with working Chromium sandboxing; never disable it to pass.
 * Usage: node scripts/verify-max-settings.mjs /absolute/evidence/directory
 */
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { isAbsolute, join } from 'node:path'
import { chromium, expect } from '@playwright/test'
import { serveDist } from './lib/serve-dist.mjs'
import { stubDashboardApi, json } from './lib/stub-dashboard-api.mjs'
import { chromiumExecutable } from './lib/chromium-executable.mjs'

const out = process.argv[2]
assert(out && isAbsolute(out), 'Choose an absolute evidence directory')
const browser = await chromium.launch({
  headless: true, chromiumSandbox: true, executablePath: chromiumExecutable(),
})
let srv
try {
  const preview = await serveDist()
  srv = preview.srv
  const { base } = preview
  mkdirSync(out, { recursive: true })
  for (const scenario of ['disabled', 'teammate', 'paired', 'pair', 'subscription', 'denied']) {
    const context = await browser.newContext({ locale: 'en-US', serviceWorkers: 'block' })
    try {
      const page = await context.newPage()
      const errors = []
      const posts = []
      page.on('pageerror', error => errors.push(error.message))
      // Only built assets reach the loopback static preview. All API traffic is
      // fulfilled below; an unexpected external request fails the preflight.
      await page.route('**/*', route => {
        if (new URL(route.request().url()).origin === base) return route.continue()
        errors.push('Unexpected external request')
        return route.abort()
      })
      await stubDashboardApi(page, {
        localStorageEntries: { 'mc-lang': 'en' },
        extra: async (path, route) => {
          if (path === '/api/auth/me') return json(route, {
            user: 'fixture-user', app: '', owner_ok: scenario !== 'teammate',
          })
          if (path === '/api/governance/channels') return json(route, { max: true })
          if (path === '/api/max/config') return json(route, {
            enabled: scenario !== 'disabled', ready: scenario !== 'disabled',
            connected: false, delivery_mode: 'webhook',
            owner_id: scenario === 'paired' ? '42' : '',
          })
          if (path === '/api/max/pairing' || path === '/api/max/subscription') {
            assert.equal(route.request().method(), 'POST')
            assert.deepEqual(route.request().postDataJSON(), {})
            posts.push(path)
            if (scenario === 'denied') return json(route, { error: 'owner_only' }, 403)
            if (path.endsWith('/pairing')) {
              return json(route, { code: 'fixture-code-not-valid', expires_in: 300 })
            }
            return json(route, { ok: true })
          }
          // A built SPA also reads owner roster APIs. No backend is running.
          return false
        },
      })
      await page.route('**/v1/**', route => json(route, {}))
      await page.goto(`${base}/settings/channels/max`, { waitUntil: 'domcontentloaded' })
      const pair = page.getByRole('button', { name: 'Pair owner', exact: true })
      const subscribe = page.getByRole('button', { name: 'Register webhook', exact: true })
      if (scenario === 'teammate') {
        await expect(page.getByTestId('channel-owner-only')).toBeVisible()
        await expect(pair).toHaveCount(0)
        await expect(subscribe).toHaveCount(0)
      } else if (scenario === 'disabled') {
        await expect(pair).toBeDisabled()
        await expect(subscribe).toBeDisabled()
      } else if (scenario === 'paired') {
        await expect(page.getByText('Owner paired: 42', { exact: true })).toBeVisible()
        await expect(pair).toHaveCount(0)
      } else if (scenario === 'pair') {
        await pair.click()
        await expect(page.getByText('/start fixture-code-not-valid', { exact: true })).toBeVisible()
        assert.deepEqual(posts, ['/api/max/pairing'])
      } else {
        await subscribe.click()
        const success = page.getByText('Webhook registered. Delivery is not yet tested.', { exact: true })
        if (scenario === 'subscription') await expect(success).toBeVisible()
        else {
          await expect(page.getByText('owner_only', { exact: true })).toBeVisible()
          await expect(success).toHaveCount(0)
        }
        assert.deepEqual(posts, ['/api/max/subscription'])
      }
      if (['disabled', 'teammate', 'paired'].includes(scenario)) assert.deepEqual(posts, [])
      assert.deepEqual(errors, [])
      if (scenario === 'disabled' || scenario === 'pair') {
        await page.screenshot({ path: join(out, `max-${scenario}.png`) })
      }
      console.log(`PASS ${scenario} (fixtures only)`)
    } finally {
      await context.close()
    }
  }
} finally {
  await browser.close()
  if (srv) await new Promise((resolve, reject) => srv.close(error => error ? reject(error) : resolve()))
}
