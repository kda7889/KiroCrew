/**
 * A resize across 768px while a fold is reported keeps the side panel where it
 * is mounted (panelInlineHost, lib/touchLayoutForm.ts). The fold holds the
 * two-pane form on both sides of 768px, so no form switch runs; moving the
 * panel to the other host there would mount a second panel and load an open
 * app frame again, losing what was typed or drawn in it. Uses the real
 * `useIsMobile`, so the host follows the committed form as in the product.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, act, waitFor, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Provider } from 'react-redux'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { createTestStore } from './helpers'
import { ThemeProvider } from '../hooks/useTheme'
import { __resetPanelTabs } from '../hooks/usePanelTabs'
import { switchSlot, sseMcpAppRender } from '../store/chatSlice'
import type { ViewportSegment } from '../hooks/useViewportSegments'

const device = vi.hoisted(() => ({ width: 951, segments: null as null | ViewportSegment[] }))
vi.mock('../hooks/useViewportSegments', async (orig) => ({
  ...(await orig<typeof import('../hooks/useViewportSegments')>()),
  useViewportSegments: () => device.segments,
}))
vi.mock('react-virtuoso', () => ({ Virtuoso: () => null }))
vi.mock('../components/ChatInput', () => ({ default: () => null }))
vi.mock('../components/WelcomeView', () => ({ default: () => null }))
vi.mock('../components/MarkdownPanel', () => ({ default: () => null }))
vi.mock('../components/MarkdownRenderer', () => ({ default: () => null }))
vi.mock('../components/TypewriterText', () => ({ default: () => null }))
vi.mock('../components/OverlayDrawer', () => ({ default: () => null }))
vi.mock('../components/AgentDropdownList', () => ({ default: () => null }))
vi.mock('../components/ModelDropdownList', () => ({ default: () => null }))
vi.mock('../components/InfoTip', () => ({ default: () => null }))
vi.mock('../components/SegmentedControl', () => ({ default: () => null }))
vi.mock('../pages/chat/CollapsibleToolGroup', () => ({ default: () => null }))
vi.mock('../pages/chat/ActivityViewer', () => ({ default: () => null }))
vi.mock('../pages/chat/SessionColorPicker', () => ({ default: () => null }))
vi.mock('../pages/chat', () => ({ ChatFooter: () => null, AssistantMessage: () => null, McpInfoButton: () => null }))
vi.mock('../pages/ChatSidebar', () => ({ default: () => null, SIDEBAR_MIN: 200, SIDEBAR_MAX: 500 }))
vi.mock('../pages/chat/ChatSettings', () => ({ loadChatConfig: () => ({ contentWidth: 'compact' }), CONTENT_WIDTH: { compact: { messages: '800px', input: '816px' }, comfortable: { messages: '84%', input: '85%' }, full: { messages: '92%', input: '93%' } } }))
vi.mock('../pages/chat/SidePanel', () => ({
  // The app tab's frame stands in for McpAppFrame: one iframe per mounted panel.
  default: ({ tabsCtl }: { tabsCtl: { tabs: { kind: string }[] } }) =>
    tabsCtl.tabs.some(t => t.kind === 'app') ? <iframe data-testid="app-frame" title="app" /> : <div data-testid="side-panel" />,
  SIDE_PANEL_MIN_W: 320, SIDE_PANEL_RESERVED_W: 560, CHAT_PANE_MIN_W: 320,
  sidePanelFillWidth: () => undefined,
}))
vi.mock('../hooks/useBranding', () => ({ useBranding: () => ({ botName: 'Test', avatar: '' }) }))
vi.mock('../hooks/useAgents', () => ({ useAgents: () => ({ agents: [], defaultAgent: null }) }))
vi.mock('../hooks/useFilteredDropdown', () => ({ useFilteredDropdown: () => ({ filtered: [], query: '', setQuery: vi.fn(), selectedIndex: 0, setSelectedIndex: vi.fn(), onKeyDown: vi.fn() }) }))
vi.mock('../hooks/useVoiceInput', () => ({ useVoiceInput: () => ({ recording: false, transcribing: false, toggle: vi.fn() }), voiceInputSupported: false }))
vi.mock('../api/client', () => ({
  api: new Proxy({}, {
    get: (_t, k: string) => {
      if (k === 'dashboardConfig') return vi.fn().mockResolvedValue({ mcp_app_panel: true })
      if (k === 'chatSlotDetail') return vi.fn().mockResolvedValue({ messages: [], has_more: false, total: 0 })
      return vi.fn().mockResolvedValue({})
    },
  }),
}))
// A desktop browser with a mouse (no touch-first rule): the width query
// decides unfolded, and the fold query matches while segments are reported.
const listeners = new Set<() => void>()
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((q: string) => ({
    get matches() {
      if (q.includes('viewport-segments')) return device.segments !== null && device.width >= 640
      const max = /max-width:\s*(\d+)px/.exec(q)
      return max ? device.width <= Number(max[1]) : false
    },
    media: q, onchange: null, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: (_t: string, cb: () => void) => { listeners.add(cb) },
    removeEventListener: (_t: string, cb: () => void) => { listeners.delete(cb) },
    dispatchEvent: vi.fn(),
  })),
})
globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) }) as unknown as typeof fetch
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver

import ChatPage from '../pages/ChatPage'

const TAB: ViewportSegment[] = [{ x: 0, width: 475.5 }, { x: 475.5, width: 475.5 }]

/** Renders the page; the returned `redraw` renders the same tree again, as a
 *  form or segments change would. */
function renderChat(store: ReturnType<typeof createTestStore>) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const tree = () => (
    <QueryClientProvider client={queryClient}>
      <Provider store={store}>
        <ThemeProvider>
          <MemoryRouter initialEntries={['/chat']}>
            <Routes><Route path="/chat/:slug?" element={<ChatPage />} /></Routes>
          </MemoryRouter>
        </ThemeProvider>
      </Provider>
    </QueryClientProvider>
  )
  const { rerender } = render(tree())
  return { redraw: () => rerender(tree()) }
}

/** Opens an MCP App in the side panel and returns its frame. */
async function openAppFrame(store: ReturnType<typeof createTestStore>): Promise<Element | null> {
  act(() => { store.dispatch(switchSlot.pending('r1', 'slot-a')) })
  await act(async () => { await Promise.resolve() })
  act(() => {
    store.dispatch(sseMcpAppRender({
      session_key: 'slot-a', tool_call_id: 'call-1', server: 'aws-mcp', tool: 'visualize',
      html: '<!doctype html><html><body>app</body></html>', csp: null, permissions: null, spool_id: 'spool-1',
    }))
  })
  await waitFor(() => expect(document.querySelector('[data-testid="app-frame"]')).not.toBeNull())
  return document.querySelector('[data-testid="app-frame"]')
}

/** Resizes the window and fires what a real resize fires. */
function resizeTo(width: number) {
  device.width = width
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 600 })
  for (const cb of [...listeners]) cb()
  window.dispatchEvent(new Event('resize'))
}

describe('an MCP App frame across a resize while folded', () => {
  let shellColumn: HTMLElement
  beforeEach(() => {
    localStorage.clear()
    __resetPanelTabs()
    device.segments = null
    resizeTo(951)
    shellColumn = document.createElement('div')
    shellColumn.id = 'activity-bar-slot'
    document.body.appendChild(shellColumn)
  })
  afterEach(() => {
    cleanup()
    shellColumn.remove()
    device.segments = null
    resizeTo(1024)
  })

  it('keeps the same iframe node from 951px to 700px and back while the fold holds', async () => {
    const SPLIT = (w: number): ViewportSegment[] => [{ x: 0, width: w / 2 }, { x: w / 2, width: w / 2 }]
    device.segments = SPLIT(951)
    resizeTo(951)
    const store = createTestStore()
    const { redraw } = renderChat(store)
    const frame = await openAppFrame(store)
    expect(frame).not.toBeNull()

    act(() => { device.segments = SPLIT(700); resizeTo(700); redraw() })
    await act(async () => { await Promise.resolve() })
    expect(document.querySelector('[data-testid="app-frame"]')).toBe(frame)

    act(() => { device.segments = SPLIT(951); resizeTo(951); redraw() })
    await act(async () => { await Promise.resolve() })
    expect(document.querySelector('[data-testid="app-frame"]')).toBe(frame)
    expect(frame?.isConnected).toBe(true)
  })

  it('keeps the same iframe node from 700px folded to 951px folded, then laid flat at 951px', async () => {
    const SPLIT = (w: number): ViewportSegment[] => [{ x: 0, width: w / 2 }, { x: w / 2, width: w / 2 }]
    device.segments = SPLIT(700)
    resizeTo(700)
    const store = createTestStore()
    const { redraw } = renderChat(store)
    const frame = await openAppFrame(store)
    expect(frame).not.toBeNull()

    act(() => { device.segments = SPLIT(951); resizeTo(951); redraw() })
    await act(async () => { await Promise.resolve() })
    expect(document.querySelector('[data-testid="app-frame"]')).toBe(frame)

    // Laid flat at 951px: the form is desktop before and after, so the panel stays.
    act(() => { device.segments = null; for (const cb of [...listeners]) cb(); redraw() })
    await act(async () => { await Promise.resolve() })
    expect(document.querySelector('[data-testid="app-frame"]')).toBe(frame)
    expect(frame?.isConnected).toBe(true)
  })
})
