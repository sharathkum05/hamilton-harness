// Client for the dashboard API. Every call carries the admin token.

import { request } from '@/lib/api'

export type Limit = { field: string; max: number | null; min: number | null; allowed: unknown[] | null }

export type Rule = {
  id: string
  text: string
  tool: string | null
  limits: Limit[]
  forbid: boolean
  on_violation: 'block' | 'handoff'
  topics: string[]
  never_say: string[]
  safe_reply: string
}

export type Persona = {
  name: string
  company: string
  role: string
  voice: string[]
  language: string
  max_sentences: number
  emoji: boolean
  banned_phrases: string[]
  disclosure: string
  notes: string
}

export type Scope = {
  covers: string
  off_topic_reply: string
  unsure_reply: string
  refuse: ('math' | 'coding' | 'writing' | 'trivia')[]
  also_refuse: string[]
  strict: boolean
  ground_numbers: boolean
}

export type Widget = {
  greeting: string
  launcher_label: string
  accent: string
  suggestions: string[]
  title: string
  logo: string
  theme: 'auto' | 'light' | 'dark'
  position: 'right' | 'left'
  corners: 'sharp' | 'soft' | 'round'
  font: 'system' | 'serif' | 'rounded' | 'mono'
  header: 'plain' | 'accent'
}

export type Handoff = {
  phrases: string[]
  on_request: boolean
  max_guard_blocks: number
  message: string
}

export type Pack = {
  persona: Persona
  scope: Scope
  widget: Widget
  handoff: Handoff
  policies: Rule[]
  tools: { name: string; description: string; handler: string }[]
  knowledge: { source: string; text: string }[]
  examples: { title: string; turns: { speaker: string; text: string }[] }[]
  scenarios: number
}

export type SimReport = {
  summary: Record<string, number | null>
  results: {
    id: string
    customer: string
    says: string[]
    passed: boolean
    replies: string[]
    failures: { name: string; detail: string }[]
    error: string
  }[]
}

export type ConversationSummary = {
  id: string
  turns: number
  updated_at: number
  opening: string
  handed_off: boolean
  blocked: boolean
  refused: boolean
}

export type TraceEvent = { turn: number; at: number; kind: string } & Record<string, unknown>

const TOKEN_KEY = 'repkit:admin-token'

/** The token arrives once in the URL fragment, which is never sent to a server. */
export function loadToken(): string {
  const fromHash = new URLSearchParams(window.location.hash.slice(1)).get('token')
  if (fromHash) {
    try {
      sessionStorage.setItem(TOKEN_KEY, fromHash)
    } catch {
      /* fall through with the token in memory */
    }
    history.replaceState(null, '', window.location.pathname)
    return fromHash
  }
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

export function storeToken(token: string) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* nothing to do */
  }
}

export function adminApi(token: string) {
  const call = <T>(path: string, init: { method?: string; body?: unknown } = {}) =>
    request<T>(`/api/admin${path}`, { ...init, token })
  return {
    pack: () => call<Pack>('/pack'),
    saveSection: (section: string, values: unknown) =>
      call(`/pack/${section}`, { method: 'PUT', body: values }),
    saveKnowledge: (name: string, text: string) =>
      call(`/knowledge/${encodeURIComponent(name)}`, { method: 'PUT', body: { text } }),
    deleteKnowledge: (name: string) =>
      call(`/knowledge/${encodeURIComponent(name)}`, { method: 'DELETE' }),
    deleteLogo: () => call('/logo', { method: 'DELETE' }),
    async uploadLogo(file: File) {
      const response = await fetch('/api/admin/logo', {
        method: 'PUT',
        headers: { authorization: `Bearer ${token}`, 'content-type': file.type },
        body: file,
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail ?? 'upload failed')
      }
    },
    sim: () => call<SimReport>('/sim', { method: 'POST', body: {} }),
    conversations: () => call<{ conversations: ConversationSummary[] }>('/conversations'),
    conversation: (id: string) => call<{ id: string; events: TraceEvent[] }>(`/conversations/${id}`),
  }
}

export type AdminApi = ReturnType<typeof adminApi>
