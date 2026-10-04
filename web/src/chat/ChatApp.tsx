// State for one chat: loads the pack's brand, keeps the conversation across
// reloads in this tab, and paces replies so they arrive like typed messages.

import { useCallback, useEffect, useRef, useState } from 'react'

import { ChatPanel } from '@/chat/ChatPanel'
import type { PanelStatus } from '@/chat/ChatPanel'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ApiError, getConfig, getConversation, sendMessage, startConversation } from '@/lib/api'
import type { Config, ConversationState, Identity, TranscriptLine } from '@/lib/api'
import { applyBrand } from '@/lib/brand'

const STORAGE_KEY = 'repkit:conversation'
// When the panel runs inside the embed script's iframe, it reports to the page.
const embedded = window.parent !== window
// Shown inside a page rather than behind a launcher, so there is nothing to close.
const inline = new URLSearchParams(window.location.search).has('inline')

function remembered(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function remember(id: string | null) {
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* a private window may refuse storage; the chat still works for this view */
  }
}

/** The embed script passes a signed-in customer in the URL fragment, which is never sent to a server. */
function identityFromHash(): Identity | null {
  const params = new URLSearchParams(window.location.hash.slice(1))
  const customer_id = params.get('customer')
  const signature = params.get('signature')
  return customer_id && signature ? { customer_id, signature } : null
}

const identity = identityFromHash()

function tellPage(type: string, detail?: unknown) {
  if (embedded) window.parent.postMessage({ source: 'repkit', type, detail }, '*')
}

const sleep = (seconds: number) => new Promise((resolve) => setTimeout(resolve, seconds * 1000))

export function ChatApp() {
  const [config, setConfig] = useState<Config | null>(null)
  const [messages, setMessages] = useState<TranscriptLine[]>([])
  const [status, setStatus] = useState<PanelStatus>('loading')
  const [handedOff, setHandedOff] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const conversationId = useRef<string | null>(null)
  const busy = useRef(false)
  const pacing = !new URLSearchParams(window.location.search).has('nopacing')

  const adopt = useCallback((conversation: ConversationState) => {
    conversationId.current = conversation.id
    remember(conversation.id)
    setMessages(conversation.transcript)
    setHandedOff(conversation.handed_off)
  }, [])

  const begin = useCallback(async () => {
    const created = await startConversation(identity)
    adopt(created)
    return created
  }, [adopt])

  const load = useCallback(async () => {
    setStatus('loading')
    setError(null)
    try {
      const loaded = await getConfig()
      setConfig(loaded)
      const saved = remembered()
      let resumed = false
      if (saved) {
        try {
          adopt(await getConversation(saved))
          resumed = true
        } catch (problem) {
          // The server forgot this conversation (restart or timeout): start again.
          if (!(problem instanceof ApiError && problem.status === 404)) throw problem
        }
      }
      if (!resumed) await begin()
      setStatus('ready')
      tellPage('ready', loaded)
    } catch {
      setStatus('offline')
    }
  }, [adopt, begin])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!config) return
    document.title = `Chat with ${config.rep.name}`
    return applyBrand(config.widget)
  }, [config])

  const send = useCallback(
    async (text: string) => {
      if (busy.current || !conversationId.current) return
      busy.current = true
      setError(null)
      setMessages((current) => [...current, { from: 'customer', text }])
      setStatus('typing')
      try {
        let response
        try {
          response = await sendMessage(conversationId.current, text)
        } catch (problem) {
          if (!(problem instanceof ApiError && problem.status === 404)) throw problem
          const fresh = await begin()
          setMessages([...fresh.transcript, { from: 'customer', text }])
          response = await sendMessage(fresh.id, text)
        }
        for (const bubble of response.bubbles) {
          if (pacing) await sleep(bubble.delay)
          setMessages((current) => [...current, { from: 'rep', text: bubble.text }])
        }
        setHandedOff(response.handed_off)
        tellPage('turn', { text, response })
      } catch {
        // Take the unsent message back out so the customer can send it again.
        setMessages((current) => current.slice(0, -1))
        setError("That didn't send. Try again.")
      } finally {
        busy.current = false
        setStatus('ready')
      }
    },
    [begin, pacing],
  )

  const reset = useCallback(async () => {
    if (busy.current) return
    remember(null)
    setStatus('loading')
    try {
      await begin()
      setStatus('ready')
      tellPage('reset')
    } catch {
      setStatus('offline')
    }
  }, [begin])

  // The embedding page may ask the panel to send a message or start over.
  useEffect(() => {
    if (!embedded) return
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || event.data?.source !== 'repkit-host') return
      if (event.data.type === 'send' && typeof event.data.text === 'string') send(event.data.text)
      if (event.data.type === 'reset') reset()
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [send, reset])

  if (!config) {
    return status === 'offline' ? (
      <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-3 text-sm">
        <p>Couldn't reach the chat.</p>
        <button className="text-foreground font-medium underline" onClick={load}>
          Try again
        </button>
      </div>
    ) : null
  }

  return (
    <TooltipProvider>
      <div className={embedded ? 'h-full' : 'mx-auto h-full max-w-md p-4'}>
        <ChatPanel
          config={config}
          messages={messages}
          status={status}
          handedOff={handedOff}
          error={error}
          embedded={embedded}
          closable={embedded && !inline}
          onSend={send}
          onReset={reset}
          onClose={() => tellPage('close')}
          onRetry={load}
        />
      </div>
    </TooltipProvider>
  )
}
