/**
 * The `mcp.project_server` card: a server a folder's own MCP file names, held back
 * when the chat started. Its buttons say what they do: Allow in this folder, Not now.
 */
import { describe, it, expect } from 'vitest'
import { CARD_REGISTRY, cardTitle } from './cardRegistry'

describe('mcp.project_server card', () => {
  it('names its buttons by result and keeps the gateway title', () => {
    const spec = CARD_REGISTRY['mcp.project_server']
    expect(spec.primary()).toBe('Allow in this folder')
    expect(spec.decline?.()).toBe('Not now')
    const title = "Start planted from this folder's .mcp.json?"
    expect(cardTitle({ kind: 'mcp.project_server', params: {}, title, changes: [] })).toBe(title)
  })
})
