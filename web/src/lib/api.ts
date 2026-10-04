// Typed client for the repkit HTTP API. The browser only ever sends customer
// text; everything that decides what the rep may do stays on the server.

export type WidgetSettings = {
  greeting: string
  launcher_label: string
  accent: string
  suggestions: string[]
  title: string
  logo_url: string
  theme: 'auto' | 'light' | 'dark'
  position: 'right' | 'left'
  corners: 'sharp' | 'soft' | 'round'
  font: 'system' | 'serif' | 'rounded' | 'mono'
  header: 'plain' | 'accent'
}

export type Config = {
  rep: { name: string; company: string; role: string }
  disclosure: string
  widget: WidgetSettings
  debug: boolean
}

export type TranscriptLine = { from: 'rep' | 'customer'; text: string }

export type ConversationState = {
  id: string
  transcript: TranscriptLine[]
  handed_off: boolean
}

export type Bubble = { text: string; delay: number }

export type TurnDebug = {
  context: { rules: string[]; notes: string[] }
  actions: {
    tool: string
    arguments: unknown
    outcome: 'ok' | 'error' | 'invalid' | 'blocked'
    detail: string
    rules: string[]
  }[]
  replaced_by: string
  refused: string
  handoff: { reason: string; detail: string } | null
  model_calls: number
  latency_ms: number
  tokens: { input: number; output: number }
}

export type TurnResponse = {
  bubbles: Bubble[]
  handed_off: boolean
  debug?: TurnDebug
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function request<T>(
  path: string,
  init: { method?: string; body?: unknown; token?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  if (init.body !== undefined) headers['content-type'] = 'application/json'
  if (init.token) headers.authorization = `Bearer ${init.token}`
  const response = await fetch(path, {
    method: init.method ?? (init.body === undefined ? 'GET' : 'POST'),
    headers,
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  })
  if (!response.ok) {
    let detail = `request failed with ${response.status}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export const getConfig = () => request<Config>('/api/config')

export const startConversation = () =>
  request<ConversationState>('/api/conversations', { body: {} })

export const getConversation = (id: string) =>
  request<ConversationState>(`/api/conversations/${encodeURIComponent(id)}`)

export const sendMessage = (id: string, text: string) =>
  request<TurnResponse>(`/api/conversations/${encodeURIComponent(id)}/messages`, {
    body: { text },
  })
