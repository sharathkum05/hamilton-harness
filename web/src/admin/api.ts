// Client for the dashboard API. Every call is signed in: by the cookie set when
// someone signs in with the admin email and password, or by the admin token.

import { request } from '@/lib/api'

export type Limit = {
  field: string
  max: number | null
  min: number | null
  allowed: unknown[] | null
}

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

export type RecordType = {
  name: string
  label: string
  description: string
  fields: { name: string; label: string; type: string; required: boolean }[]
}

export type RecordStatus = 'new' | 'confirmed' | 'done' | 'cancelled'

export type RecordItem = {
  id: string
  type: string
  data: Record<string, string | number>
  status: RecordStatus
  created_at: string
  conversation_id: string
}

export type Overview = {
  records: { total: number; waiting: number; by_type: Record<string, number> }
  conversations: { total: number; handed_off: number; blocked: number; refused: number }
  timeline: { day: string; conversations: number; records: number }[]
  recent_records: RecordItem[]
  recent_conversations: ConversationSummary[]
}

export type Pack = {
  // True until the setup has run once on a rep made by `hamilton-harness studio`.
  setup_pending: boolean
  persona: Persona
  scope: Scope
  widget: Widget
  handoff: Handoff
  model: { name: string; effort: string; max_tokens: number }
  policies: Rule[]
  tools: Tool[]
  records: RecordType[]
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
  // Things in the pack that work against it, which a passing run does not show.
  warnings: { code: string; where: string; message: string }[]
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

const TOKEN_KEY = 'hamilton:admin-token'

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

/** A call to a company's web API, set up without code. */
export type HttpCall = { method: 'GET' | 'POST'; url: string; headers: Record<string, string> }

export type JsonSchema = {
  type?: string
  properties?: Record<string, { type?: string; description?: string; enum?: string[] }>
  required?: string[]
  additionalProperties?: boolean
}

export type Tool = {
  name: string
  description: string
  handler: string
  // "code" tools are Python in the pack; "api" tools are set up in the dashboard.
  kind: 'code' | 'api'
  http: HttpCall | null
  input_schema: JsonSchema
  remember: Record<string, string>
}

export type StageStatus = 'passed' | 'stopped' | 'unused' | 'skipped'
export type Stage = { key: string; name: string; does: string }
export type StageResult = { key: string; status: StageStatus; note: string }

export type Tone = 'friendly' | 'professional' | 'playful' | 'direct'

/** What the setup asks. The server builds a whole rep from these. */
export type SetupAnswers = {
  company: string
  rep: string
  role: string
  covers: string
  knowledge: string
  tone: Tone[]
  emoji: boolean
  greeting: string
  suggestions: string[]
  accent: string
}

// `demo`: the public, read-only dashboard of the hosted demo, open to anyone.
export type AdminSession = { email: string | null; password: boolean; demo: boolean }

export const getSession = (token: string) => request<AdminSession>('/api/admin/session', { token })
export const signIn = (email: string, password: string) =>
  request<{ email: string }>('/api/admin/session', { body: { email, password } })
export const signOut = () => request('/api/admin/session', { method: 'DELETE' })

export function adminApi(token: string) {
  const call = <T>(path: string, init: { method?: string; body?: unknown } = {}) =>
    request<T>(`/api/admin${path}`, { ...init, token })
  return {
    pack: () => call<Pack>('/pack'),
    setup: (answers: SetupAnswers) => call('/setup', { method: 'POST', body: answers }),
    saveTools: (tools: Omit<Tool, 'kind' | 'handler'>[]) =>
      call('/pack/tools', { method: 'PUT', body: tools }),
    tryTool: (name: string, args: Record<string, unknown>) =>
      call<{ ok: boolean; result: string }>(`/tools/${encodeURIComponent(name)}/try`, {
        method: 'POST',
        body: args,
      }),
    flow: () => call<{ stages: Stage[] }>('/flow'),
    tryFlow: (text: string) =>
      call<{ stages: StageResult[]; bubbles: string[] }>('/flow/try', {
        method: 'POST',
        body: { text },
      }),
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
        headers: {
          'content-type': file.type,
          ...(token ? { authorization: `Bearer ${token}` } : {}),
        },
        body: file,
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail ?? 'upload failed')
      }
    },
    overview: () => call<Overview>('/overview'),
    records: () => call<{ records: RecordItem[] }>('/records'),
    setRecordStatus: (id: string, status: RecordStatus) =>
      call<RecordItem>(`/records/${encodeURIComponent(id)}`, { method: 'PATCH', body: { status } }),
    sim: () => call<SimReport>('/sim', { method: 'POST', body: {} }),
    conversations: () => call<{ conversations: ConversationSummary[] }>('/conversations'),
    conversation: (id: string) =>
      call<{ id: string; events: TraceEvent[] }>(`/conversations/${id}`),
  }
}

export type AdminApi = ReturnType<typeof adminApi>
