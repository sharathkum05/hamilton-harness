// The chat panel. Its layout follows the "Voice chat 1" block from ElevenLabs UI
// and it is built from the same official components, wired to the repkit API
// instead of an ElevenLabs voice agent.

import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { RotateCcwIcon, SendIcon, XIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from '@/components/ui/conversation'
import { Input } from '@/components/ui/input'
import { Message, MessageContent } from '@/components/ui/message'
import { MessageLoading } from '@/components/ui/message-loading'
import { Orb } from '@/components/ui/orb'
import { ShimmeringText } from '@/components/ui/shimmering-text'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { Config, TranscriptLine } from '@/lib/api'
import { orbColors } from '@/lib/brand'
import { cn } from '@/lib/utils'

export type PanelStatus = 'loading' | 'ready' | 'typing' | 'offline'

type ChatPanelProps = {
  config: Config
  messages: TranscriptLine[]
  status: PanelStatus
  handedOff: boolean
  error: string | null
  embedded: boolean
  closable: boolean
  onSend: (text: string) => void
  onReset: () => void
  onClose: () => void
  onRetry: () => void
}

function HeaderAction({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground size-8"
          onClick={onClick}
        >
          {children}
          <span className="sr-only">{label}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

/** The brand's logo when the pack has one, the orb when it does not. */
function Mark({
  config,
  className,
  talking,
}: {
  config: Config
  className: string
  talking?: boolean
}) {
  const { widget, rep } = config
  return (
    <div className={cn('ring-border relative overflow-hidden rounded-full ring-1', className)}>
      {widget.logo_url ? (
        <img src={widget.logo_url} alt={`${rep.company} logo`} className="size-full object-cover" />
      ) : (
        <Orb
          className="size-full"
          colors={orbColors(widget.accent)}
          agentState={talking ? 'talking' : null}
        />
      )}
    </div>
  )
}

export function ChatPanel({
  config,
  messages,
  status,
  handedOff,
  error,
  embedded,
  closable,
  onSend,
  onReset,
  onClose,
  onRetry,
}: ChatPanelProps) {
  const [draft, setDraft] = useState('')
  const { rep, widget } = config
  const busy = status === 'typing' || status === 'loading'
  const customerSpoke = messages.some((message) => message.from === 'customer')

  const submit = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    setDraft('')
    onSend(trimmed)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    // Leave IME composition alone: Enter there confirms a character, not a message.
    if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit(draft)
    }
  }

  return (
    <Card
      className={cn(
        'mx-auto flex h-full w-full flex-col gap-0 overflow-hidden py-0',
        embedded && 'rounded-none border-0 shadow-none',
      )}
    >
      <CardHeader
        className={cn(
          'flex shrink-0 flex-row items-center justify-between gap-2 border-b px-4 py-3',
          widget.header === 'accent' && 'bg-primary text-primary-foreground border-transparent',
        )}
      >
        <div className="flex min-w-0 items-center gap-3">
          <Mark config={config} className="size-10 shrink-0" talking={status === 'typing'} />
          <div className="flex min-w-0 flex-col gap-0.5">
            <p className="truncate text-sm leading-none font-medium">{widget.title || rep.name}</p>
            <div className="flex items-center gap-2 text-xs">
              {error ? (
                <p className="text-destructive">{error}</p>
              ) : status === 'typing' ? (
                <ShimmeringText text={`${rep.name} is typing`} className="text-xs" />
              ) : status === 'loading' ? (
                <ShimmeringText text="Connecting" className="text-xs" />
              ) : (
                <p
                  className={cn(
                    'truncate',
                    widget.header === 'accent' ? 'opacity-85' : 'text-muted-foreground',
                  )}
                >
                  {rep.name} · {config.disclosure}
                </p>
              )}
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <div
            aria-hidden="true"
            className={cn(
              'mr-2 size-2 rounded-full transition-all duration-300',
              status === 'ready' && 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]',
              busy && 'bg-muted-foreground/50 animate-pulse',
              status === 'offline' && 'bg-destructive',
            )}
          />
          <HeaderAction label="Start a new chat" onClick={onReset}>
            <RotateCcwIcon className="size-4" />
          </HeaderAction>
          {closable && (
            <HeaderAction label="Close chat" onClick={onClose}>
              <XIcon className="size-4" />
            </HeaderAction>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-hidden p-0">
        <Conversation className="h-full">
          <ConversationContent className="flex min-w-0 flex-col gap-0 p-4 pb-2">
            {status === 'offline' ? (
              <ConversationEmptyState
                title="Couldn't reach the chat"
                description="Check your connection and try again."
              >
                <div className="flex flex-col items-center gap-3 text-center">
                  <p className="text-sm font-medium">Couldn't reach the chat</p>
                  <Button variant="outline" size="sm" onClick={onRetry}>
                    Try again
                  </Button>
                </div>
              </ConversationEmptyState>
            ) : !customerSpoke ? (
              <ConversationEmptyState>
                <div className="flex flex-col items-center gap-3 text-center">
                  <Mark config={config} className="size-12" />
                  <div className="space-y-1">
                    <h3 className="text-sm font-medium">
                      {status === 'loading' ? (
                        <ShimmeringText text="Starting conversation" />
                      ) : (
                        'Start a conversation'
                      )}
                    </h3>
                    <p className="text-muted-foreground mx-auto max-w-[32ch] text-sm">
                      {messages.map((message) => message.text).join(' ')}
                    </p>
                  </div>
                  {widget.suggestions.length > 0 && status !== 'loading' && (
                    <div className="mt-1 flex flex-wrap justify-center gap-1.5">
                      {widget.suggestions.map((suggestion) => (
                        <Button
                          key={suggestion}
                          variant="outline"
                          size="sm"
                          className="h-auto py-1.5 font-normal whitespace-normal"
                          onClick={() => submit(suggestion)}
                        >
                          {suggestion}
                        </Button>
                      ))}
                    </div>
                  )}
                </div>
              </ConversationEmptyState>
            ) : (
              <>
                {messages.map((message, index) => {
                  const from = message.from === 'customer' ? 'user' : 'assistant'
                  const next = messages[index + 1]
                  // One avatar per run of rep bubbles, on the last of them.
                  const endsRun = from === 'assistant' && next?.from !== 'rep'
                  return (
                    <Message
                      key={index}
                      from={from}
                      className={cn('py-1', next && next.from !== message.from && 'pb-3')}
                    >
                      <MessageContent className="max-w-[82%] min-w-0 px-3.5 py-2.5">
                        {/* Plain text on purpose: nothing a customer or the model writes is
                            parsed as Markdown, so an email address or a link shows as typed. */}
                        <p className="[overflow-wrap:anywhere] whitespace-pre-wrap">{message.text}</p>
                      </MessageContent>
                      {from === 'assistant' &&
                        (endsRun && status !== 'typing' ? (
                          <Mark config={config} className="size-6 shrink-0" />
                        ) : (
                          <div className="size-6 shrink-0" />
                        ))}
                    </Message>
                  )
                })}
                {status === 'typing' && (
                  <Message from="assistant" className="py-1">
                    <MessageContent className="px-3.5 py-1.5">
                      <MessageLoading />
                    </MessageContent>
                    <Mark config={config} className="size-6 shrink-0" talking />
                  </Message>
                )}
              </>
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
      </CardContent>

      {handedOff && (
        <div
          role="status"
          className="shrink-0 border-t bg-amber-50 px-4 py-2 text-xs text-amber-900 dark:bg-amber-950/60 dark:text-amber-200"
        >
          A member of the team is taking over this chat.
        </div>
      )}

      <CardFooter className="shrink-0 flex-col gap-2 border-t px-3 py-3">
        <div className="flex w-full items-center gap-2">
          <Input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Type a message..."
            aria-label="Message"
            maxLength={2000}
            className="h-9 focus-visible:ring-0 focus-visible:ring-offset-0"
            disabled={status === 'offline'}
          />
          <Button
            onClick={() => submit(draft)}
            size="icon"
            variant="ghost"
            className="shrink-0 rounded-full"
            disabled={!draft.trim() || busy}
          >
            <SendIcon className="size-4" />
            <span className="sr-only">Send message</span>
          </Button>
        </div>
        <p className="text-muted-foreground w-full text-center text-[11px]">
          {rep.name} is an AI assistant. Ask for a person at any time.
        </p>
      </CardFooter>
    </Card>
  )
}
