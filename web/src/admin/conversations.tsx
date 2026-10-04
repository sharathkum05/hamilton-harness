// Recorded conversations, read as a chat: what the customer said, what the rep
// replied, and between the two, what the harness did and decided.

import { useCallback, useEffect, useState } from 'react'
import { BanIcon, CheckIcon, FileSearchIcon, ShieldAlertIcon, UserRoundCheckIcon, XIcon } from 'lucide-react'
import type { ComponentType } from 'react'

import type { ConversationSummary, TraceEvent } from '@/admin/api'
import { Section } from '@/admin/fields'
import { OPEN_CONVERSATION_KEY } from '@/admin/inbox'
import type { SectionProps } from '@/admin/sections'
import { Badge } from '@/components/ui/badge'
import { Message, MessageContent } from '@/components/ui/message'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

type Note = { Icon: ComponentType<{ className?: string }>; tone: 'plain' | 'good' | 'stop' | 'warn'; text: string }

const TONES = {
  plain: 'text-muted-foreground',
  good: 'text-green-700 dark:text-green-400',
  stop: 'text-red-700 dark:text-red-400',
  warn: 'text-amber-700 dark:text-amber-400',
}

/** What the harness did at this step, in a line, or nothing if the step is not worth a line. */
function note(event: TraceEvent): Note | null {
  const data = event as Record<string, any>
  switch (event.kind) {
    case 'context': {
      const rules: string[] = data.rules ?? []
      if (rules.length === 0 && (data.notes ?? []).length === 0) return null
      return {
        Icon: FileSearchIcon,
        tone: 'plain',
        text: `Given ${rules.length ? `rules ${rules.join(', ')}` : 'no rules'} and ${(data.notes ?? []).length} note(s)`,
      }
    }
    case 'action':
      if (data.outcome === 'ok') {
        return { Icon: CheckIcon, tone: 'good', text: `${data.tool}(${JSON.stringify(data.arguments)})` }
      }
      return {
        Icon: data.outcome === 'blocked' ? ShieldAlertIcon : XIcon,
        tone: data.outcome === 'blocked' ? 'stop' : 'warn',
        text: `${data.tool} ${data.outcome}: ${data.detail}`,
      }
    case 'scope_refused':
      return { Icon: BanIcon, tone: 'warn', text: `Off topic (${data.reason}). The model was not called.` }
    case 'reply_blocked':
      return { Icon: ShieldAlertIcon, tone: 'stop', text: `Draft replaced by "${data.rule}". It said: ${data.draft}` }
    case 'handoff':
      return { Icon: UserRoundCheckIcon, tone: 'warn', text: `Handed to a human (${data.reason}: ${data.detail})` }
    case 'model_error':
      return { Icon: XIcon, tone: 'stop', text: `Model error: ${data.error}` }
    default:
      return null
  }
}

function Transcript({ events }: { events: TraceEvent[] }) {
  const turns = new Map<number, TraceEvent[]>()
  for (const event of events) turns.set(event.turn, [...(turns.get(event.turn) ?? []), event])

  return (
    <div className="flex flex-col gap-5">
      {[...turns.entries()].map(([turn, steps]) => {
        const said = steps.find((step) => step.kind === 'customer') as Record<string, any> | undefined
        const end = steps.find((step) => step.kind === 'turn_end') as Record<string, any> | undefined
        const notes = steps.map(note).filter((item): item is Note => item !== null)
        return (
          <div key={turn} className="flex flex-col gap-1.5">
            {said && (
              <Message from="user" className="py-0">
                <MessageContent className="max-w-[85%] px-3.5 py-2.5">
                  <p className="[overflow-wrap:anywhere] whitespace-pre-wrap">{said.text}</p>
                </MessageContent>
              </Message>
            )}
            {notes.length > 0 && (
              <ul className="my-1 flex flex-col gap-1 border-l pl-3">
                {notes.map((item, index) => (
                  <li key={index} className={cn('flex items-start gap-2 font-mono text-xs', TONES[item.tone])}>
                    <item.Icon className="mt-0.5 size-3.5 shrink-0" />
                    <span className="[overflow-wrap:anywhere]">{item.text}</span>
                  </li>
                ))}
              </ul>
            )}
            {(end?.bubbles ?? []).map((bubble: string, index: number) => (
              <Message key={index} from="assistant" className="py-0">
                <MessageContent className="max-w-[85%] px-3.5 py-2.5">
                  <p className="[overflow-wrap:anywhere] whitespace-pre-wrap">{bubble}</p>
                </MessageContent>
              </Message>
            ))}
          </div>
        )
      })}
    </div>
  )
}

export function ConversationsSection({ api }: SectionProps) {
  const [list, setList] = useState<ConversationSummary[] | null>(null)
  const [open, setOpen] = useState<{ id: string; events: TraceEvent[] } | null>(null)

  const show = useCallback(
    (id: string) => {
      api.conversation(id).then(setOpen).catch(() => setOpen(null))
    },
    [api],
  )

  useEffect(() => {
    api
      .conversations()
      .then((body) => {
        setList(body.conversations)
        // Arriving from an order or quote opens the conversation it came from.
        let wanted: string | null = null
        try {
          wanted = sessionStorage.getItem(OPEN_CONVERSATION_KEY)
          sessionStorage.removeItem(OPEN_CONVERSATION_KEY)
        } catch {
          /* nothing was remembered */
        }
        const first = wanted ?? body.conversations[0]?.id
        if (first) show(first)
      })
      .catch(() => setList([]))
  }, [api, show])

  return (
    <Section
      title="Conversations"
      description="Every conversation is recorded step by step. Between what the customer said and what the rep replied, you can see which rules it was shown, each action it took and what the guard decided."
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-1.5">
          {list === null &&
            [0, 1, 2].map((index) => <Skeleton key={index} className="h-16 rounded-xl" />)}
          {list?.length === 0 && (
            <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
              No conversations yet. Send a message in the preview and it appears here.
            </p>
          )}
          {list?.map((item) => (
            <button
              key={item.id}
              onClick={() => show(item.id)}
              aria-current={open?.id === item.id ? 'true' : undefined}
              className={cn(
                'flex flex-col gap-1.5 rounded-xl border p-3 text-left text-sm transition-colors duration-200',
                open?.id === item.id ? 'bg-muted border-foreground/20' : 'hover:bg-muted/60',
              )}
            >
              <span className="line-clamp-2">{item.opening || '(no message)'}</span>
              <span className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground text-xs tabular-nums">
                  {item.turns} turn{item.turns === 1 ? '' : 's'} ·{' '}
                  {new Date(item.updated_at * 1000).toLocaleString(undefined, {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })}
                </span>
                {item.blocked && <Badge variant="destructive" className="rounded-md">guard</Badge>}
                {item.refused && <Badge variant="outline" className="rounded-md">off topic</Badge>}
                {item.handed_off && <Badge variant="secondary" className="rounded-md">handed off</Badge>}
              </span>
            </button>
          ))}
        </div>
        <div className="bg-card min-w-0 rounded-2xl border p-5">
          {open ? (
            <Transcript events={open.events} />
          ) : (
            <p className="text-muted-foreground text-sm">
              {list?.length ? 'Choose a conversation to read it.' : 'A conversation you open is shown here.'}
            </p>
          )}
        </div>
      </div>
    </Section>
  )
}
