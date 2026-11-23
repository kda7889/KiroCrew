import React from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const state = vi.hoisted(() => ({ owner: '', ready: true, code: 'synthetic-code' }))
const issue = vi.hoisted(() => vi.fn(async () => ({ code: state.code, expires_in: 300 })))
const subscribe = vi.hoisted(() => vi.fn(async () => ({ ok: true })))
vi.mock('../../api/client', () => ({ api: {
  getMaxConfig: async () => ({ owner_id: state.owner, ready: state.ready, delivery_mode: 'webhook' }),
  issueMaxPairing: issue,
  registerMaxSubscription: subscribe,
} }))
vi.mock('../../i18n/t', () => ({ i18nT: (key: string, values?: Record<string, string>) => key + (values?.id ?? '') }))
vi.mock('../../components/ErrorNotice', () => ({ default: ({ message }: { message: string }) => <div role="alert">{message}</div> }))

import { MaxPanel } from './MaxPanel'

afterEach(() => { cleanup(); vi.clearAllMocks(); state.owner = ''; state.ready = true })

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MaxPanel /></QueryClientProvider>)
  return client
}

test('the owner gets a code through a button without a browser console', async () => {
  mount()
  const button = await screen.findByRole('button', { name: 'pages.settings.maxPanel.pair' })
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(button)
  expect(await screen.findByText('/start synthetic-code')).toBeTruthy()
  expect(issue).toHaveBeenCalledTimes(1)
})

test('a paired account hides and discards the short-lived code', async () => {
  const client = mount()
  const button = await screen.findByRole('button', { name: 'pages.settings.maxPanel.pair' })
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(button)
  await screen.findByText('/start synthetic-code')
  state.owner = '42'
  await client.invalidateQueries({ queryKey: ['max-config'] })
  await screen.findByText('pages.settings.maxPanel.paired42')
  await waitFor(() => expect(screen.queryByText('/start synthetic-code')).toBeNull())
  expect(screen.queryByRole('button', { name: 'pages.settings.maxPanel.pair' })).toBeNull()
})

test('an inactive channel cannot issue codes', async () => {
  state.ready = false
  mount()
  await screen.findByText('pages.settings.maxPanel.inactive')
  const button = await screen.findByRole('button', { name: 'pages.settings.maxPanel.pair' })
  expect((button as HTMLButtonElement).disabled).toBe(true)
  expect(issue).not.toHaveBeenCalled()
})

test('the owner explicitly registers the webhook from Settings', async () => {
  mount()
  const button = await screen.findByRole('button', { name: 'pages.settings.maxPanel.subscribe' })
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  expect(subscribe).not.toHaveBeenCalled()
  fireEvent.click(button)
  await screen.findByText('pages.settings.maxPanel.subscribed')
  expect(subscribe).toHaveBeenCalledTimes(1)
})

test('a rejected subscription shows an error without claiming success', async () => {
  subscribe.mockRejectedValueOnce(new Error('owner_only'))
  mount()
  const button = await screen.findByRole('button', { name: 'pages.settings.maxPanel.subscribe' })
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(button)
  await screen.findByRole('alert')
  expect(screen.queryByText('pages.settings.maxPanel.subscribed')).toBeNull()
})
