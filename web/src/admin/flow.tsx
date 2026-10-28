// The Flow screen: the harness drawn as the path every message takes. Each
// block is one stage, with how it is set up for this rep; clicking it opens the
// screen that changes it. A test message runs one real turn and lights the
// path up: where it passed, where it was stopped, and what never ran.

import { useEffect, useState } from 'react'
import type { ComponentType } from 'react'
import {
  BookOpenIcon,
  BrainIcon,
  ChevronRightIcon,
  MessageSquareIcon,
  SendIcon,
  ShieldCheckIcon,
  SigmaIcon,
  TargetIcon,
  UserRoundCheckIcon,
  WrenchIcon,
  ReplyIcon,
} from 'lucide-react'

import type { Pack, Stage, StageResult, StageStatus } from '@/admin/api'
import { Section } from '@/admin/fields'
import type { SectionProps } from '@/admin/sections'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

type Icon = ComponentType<{ className?: string }>

/** For each stage: its icon, the screen that changes it, and how it is set up here. */
const SETUP: Record<string, [Icon, string, (pack: Pack) => string]> = {
  message: [MessageSquareIcon, 'install', () => 'From the chat on your website.'],
  handoff: [
    UserRoundCheckIcon,
    'handoff',
    (pack) =>
      `${pack.handoff.phrases.length} phrase${pack.handoff.phrases.length === 1 ? '' : 's'} · ` +
      `asking for a person ${pack.handoff.on_request ? 'hands over' : 'is ignored'} · ` +
      `after ${pack.handoff.max_guard_blocks} blocks`,
  ],
  context: [
    BookOpenIcon,
    'knowledge',
    (pack) =>
      `${pack.knowledge.length} knowledge file${pack.knowledge.length === 1 ? '' : 's'} · ` +
      `${pack.policies.length} rules · customer memory`,
  ],
  scope: [
    TargetIcon,
    'scope',
    (pack) =>
      `${pack.scope.strict ? 'Strict' : 'Not strict'} · turns away ${
        pack.scope.refuse.length ? pack.scope.refuse.join(', ') : 'nothing by kind'
      }`,
  ],
  model: [BrainIcon, 'voice', (pack) => `${pack.model.name} · effort ${pack.model.effort}`],
  tools: [
    WrenchIcon,
    'tools',
    (pack) => {
      const api = pack.tools.filter((tool) => tool.kind === 'api').length
      return (
        `${pack.tools.length} tool${pack.tools.length === 1 ? '' : 's'}` +
        (api ? ` (${api} API)` : '') +
        ` · ${pack.records.length} kind${pack.records.length === 1 ? '' : 's'} of record`
      )
    },
  ],
  guard: [
    ShieldCheckIcon,
    'rules',
    (pack) => {
      const enforced = pack.policies.filter(
        (rule) => rule.limits.length || rule.forbid || rule.never_say.length,
      ).length
      return `${enforced} rule${enforced === 1 ? '' : 's'} enforced in code · never claims to be human`
    },
  ],
  grounding: [
    SigmaIcon,
    'scope',
    (pack) => (pack.scope.ground_numbers ? 'On: every figure needs a source' : 'Off'),
  ],
  reply: [
    ReplyIcon,
    'voice',
    (pack) =>
      `Up to ${pack.persona.max_sentences} sentences a bubble · emoji ${
        pack.persona.emoji ? 'on' : 'off'
      }`,
  ],
}

const STATUS: Record<StageStatus, [string, string]> = {
  passed: ['Passed', 'border-green-500/40 bg-green-500/10 text-green-700 dark:text-green-300'],
  stopped: ['Stopped it', 'border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300'],
  unused: ['Not needed', 'border-border bg-muted text-muted-foreground'],
  skipped: ['Not reached', 'border-border bg-transparent text-muted-foreground'],
}

const SAMPLES = ['What is 348 * 12?', 'Can I talk to a person?', 'Are you a real person?']

export function FlowSection({ pack, api, go }: SectionProps) {
  const [stages, setStages] = useState<Stage[]>([])
  const [text, setText] = useState('')
  const [results, setResults] = useState<Record<string, StageResult> | null>(null)
  const [bubbles, setBubbles] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .flow()
      .then((flow) => setStages(flow.stages))
      .catch(() => setError('Could not load the flow.'))
  }, [api])

  const send = async (message: string) => {
    if (!message.trim()) return
    setText(message)
    setBusy(true)
    setError('')
    try {
      const turn = await api.tryFlow(message.trim())
      setResults(Object.fromEntries(turn.stages.map((stage) => [stage.key, stage])))
      setBubbles(turn.bubbles)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The message did not go through.')
    } finally {
      setBusy(false)
    }
  }

  const samples = [...pack.widget.suggestions.slice(0, 2), ...SAMPLES]

  return (
    <Section
      title="Flow"
      description="The path every message takes through the harness. Each block is one stage, set up on its own screen; click one to change it. The order is fixed, so every action and every reply passes the checks after the model."
    >
      <Card>
        <CardContent className="flex flex-col gap-3">
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              send(text)
            }}
          >
            <Input
              aria-label="Test message"
              placeholder="Send a test message to see what each stage does with it"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <Button type="submit" disabled={busy || !text.trim()}>
              <SendIcon /> {busy ? 'Running…' : 'Send'}
            </Button>
          </form>
          <div className="flex flex-wrap gap-2">
            {samples.map((sample) => (
              <Button
                key={sample}
                variant="outline"
                size="sm"
                className="rounded-full font-normal"
                disabled={busy}
                onClick={() => send(sample)}
              >
                {sample}
              </Button>
            ))}
          </div>
          <p className="text-muted-foreground text-xs">
            A test runs one real turn as a new customer. Nothing is kept in the inbox or the
            conversations, but a tool that calls your systems does call them.
          </p>
          {error && (
            <p role="alert" className="text-destructive text-sm">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      <ol className="relative flex flex-col gap-3" aria-label="Stages of a turn">
        {stages.map((stage, index) => {
          const [StageIcon, section, summary] = SETUP[stage.key] ?? [
            MessageSquareIcon,
            'overview',
            () => '',
          ]
          const result = results?.[stage.key]
          const [label, tone] = result ? STATUS[result.status] : ['', '']
          return (
            <li key={stage.key} className="relative flex gap-4">
              {/* The line joining the stages, so the blocks read as one path. */}
              {index < stages.length - 1 && (
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute top-11 left-5 h-[calc(100%-1.75rem)] w-px',
                    result &&
                      result.status !== 'skipped' &&
                      results?.[stages[index + 1].key]?.status !== 'skipped'
                      ? 'bg-foreground/40'
                      : 'bg-border',
                  )}
                />
              )}
              <span
                className={cn(
                  'bg-card relative z-10 mt-1 flex size-10 shrink-0 items-center justify-center rounded-xl border',
                  result?.status === 'stopped' &&
                    'border-red-500/60 text-red-600 dark:text-red-400',
                  result?.status === 'passed' &&
                    'border-green-500/60 text-green-700 dark:text-green-400',
                  result?.status === 'skipped' && 'opacity-50',
                )}
              >
                <StageIcon className="size-4" />
              </span>
              <button
                type="button"
                onClick={() => go(section)}
                className={cn(
                  'bg-card hover:bg-accent/40 focus-visible:ring-ring group flex min-w-0 flex-1 flex-col gap-1.5 rounded-xl border p-4 text-left transition-colors outline-none focus-visible:ring-2',
                  result?.status === 'skipped' && 'opacity-60',
                )}
              >
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{stage.name}</span>
                  {result && (
                    <Badge variant="outline" className={cn('rounded-md', tone)}>
                      {label}
                    </Badge>
                  )}
                  <ChevronRightIcon className="text-muted-foreground ml-auto size-4 transition-transform group-hover:translate-x-0.5" />
                </span>
                <span className="text-muted-foreground text-sm">{stage.does}</span>
                <span className="text-xs">{summary(pack)}</span>
                {result?.note && (
                  <span
                    className={cn(
                      'mt-1 rounded-md px-2.5 py-1.5 text-sm',
                      result.status === 'stopped' ? 'bg-red-500/10' : 'bg-muted',
                    )}
                  >
                    {result.note}
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ol>

      {bubbles.length > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-2">
            <p className="text-sm font-medium">What the customer saw</p>
            {bubbles.map((bubble, index) => (
              <p key={index} className="bg-muted self-start rounded-2xl px-3.5 py-2 text-sm">
                {bubble}
              </p>
            ))}
          </CardContent>
        </Card>
      )}
    </Section>
  )
}
