// The dashboard's read-only screens: testing, conversations and installing.

import { useEffect, useState } from 'react'
import { CheckIcon, CopyIcon, PlayIcon } from 'lucide-react'

import type { ConversationSummary, SimReport, TraceEvent } from '@/admin/api'
import { Section } from '@/admin/fields'
import type { SectionProps } from '@/admin/sections'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

// -- Test --------------------------------------------------------------------

const STATS: [string, string][] = [
  ['actions_run', 'Actions run'],
  ['actions_blocked', 'Actions blocked'],
  ['replies_replaced', 'Replies replaced'],
  ['off_topic_refused', 'Off topic refused'],
  ['handoffs', 'Handed to a human'],
]

export function TestSection({ pack, api }: SectionProps) {
  const [report, setReport] = useState<SimReport | null>(null)
  const [running, setRunning] = useState(false)
  const [problem, setProblem] = useState('')

  const run = async () => {
    setRunning(true)
    setProblem('')
    try {
      setReport(await api.sim())
    } catch (error) {
      setProblem(error instanceof Error ? error.message : 'The run failed.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <Section
      title="Test"
      description={`Run the pack's ${pack.scenarios} fake customers against the rep as it is configured right now. Some of them have the model misbehave on purpose, to prove the guard holds. Run this after every change to rules or scope.`}
      actions={
        <Button onClick={run} disabled={running || pack.scenarios === 0}>
          <PlayIcon /> {running ? 'Running' : 'Run fake customers'}
        </Button>
      }
    >
      {problem && <p className="text-destructive text-sm">{problem}</p>}
      {!report && !problem && (
        <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
          No run yet. Results appear here.
        </p>
      )}
      {report && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Card className="col-span-2 sm:col-span-1">
              <CardContent className="flex flex-col gap-1">
                <span className="text-2xl font-semibold tabular-nums">
                  {report.summary.passed}/{report.summary.scenarios}
                </span>
                <span className="text-muted-foreground text-xs">Customers passed</span>
              </CardContent>
            </Card>
            {STATS.map(([key, label]) => (
              <Card key={key}>
                <CardContent className="flex flex-col gap-1">
                  <span className="text-2xl font-semibold tabular-nums">{report.summary[key] ?? 0}</span>
                  <span className="text-muted-foreground text-xs">{label}</span>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="flex flex-col gap-2">
            {report.results.map((result) => (
              <Card key={result.id}>
                <CardContent className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={result.passed ? 'secondary' : 'destructive'}>
                      {result.passed ? 'Pass' : 'Fail'}
                    </Badge>
                    <code className="text-sm">{result.id}</code>
                    <span className="text-muted-foreground text-xs">{result.customer}</span>
                  </div>
                  <p className="text-sm">
                    <span className="text-muted-foreground">Customer: </span>
                    {result.says[0]}
                  </p>
                  {result.replies[0] && (
                    <p className="text-sm">
                      <span className="text-muted-foreground">Rep: </span>
                      {result.replies[result.replies.length - 1]}
                    </p>
                  )}
                  {result.error && <p className="text-destructive text-sm">Crashed: {result.error}</p>}
                  {result.failures.map((failure) => (
                    <p key={failure.name} className="text-destructive text-sm">
                      Failed: {failure.name} {failure.detail && `(${failure.detail})`}
                    </p>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </Section>
  )
}

// -- Conversations -----------------------------------------------------------

function describe(event: TraceEvent): { tone: 'plain' | 'good' | 'stop' | 'warn'; text: string } | null {
  const data = event as Record<string, any>
  switch (event.kind) {
    case 'customer':
      return { tone: 'plain', text: `Customer: ${data.text}` }
    case 'context':
      return {
        tone: 'plain',
        text: `Given rules [${(data.rules ?? []).join(', ') || 'none'}] and ${(data.notes ?? []).length} note(s)`,
      }
    case 'action':
      return {
        tone: data.outcome === 'ok' ? 'good' : data.outcome === 'blocked' ? 'stop' : 'warn',
        text: `${data.tool}(${JSON.stringify(data.arguments)}) → ${data.outcome}${
          data.outcome === 'ok' ? '' : `: ${data.detail}`
        }`,
      }
    case 'scope_refused':
      return { tone: 'warn', text: `Off topic (${data.reason}); the model was not called` }
    case 'reply_blocked':
      return { tone: 'stop', text: `Draft replaced by "${data.rule}". It said: ${data.draft}` }
    case 'handoff':
      return { tone: 'warn', text: `Handed to a human (${data.reason}: ${data.detail})` }
    case 'model_error':
      return { tone: 'stop', text: `Model error: ${data.error}` }
    case 'turn_end':
      return { tone: 'plain', text: `Rep: ${(data.bubbles ?? []).join(' ')}` }
    default:
      return null
  }
}

const TONES = {
  plain: '',
  good: 'text-green-700 dark:text-green-400',
  stop: 'text-red-700 dark:text-red-400',
  warn: 'text-amber-700 dark:text-amber-400',
}

export function ConversationsSection({ api }: SectionProps) {
  const [list, setList] = useState<ConversationSummary[] | null>(null)
  const [open, setOpen] = useState<{ id: string; events: TraceEvent[] } | null>(null)

  useEffect(() => {
    api.conversations().then((body) => setList(body.conversations)).catch(() => setList([]))
  }, [api])

  return (
    <Section
      title="Conversations"
      description="Every conversation is recorded step by step: what the customer said, which rules the rep was shown, each action and what the guard decided. Open one to see why the rep answered the way it did."
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-2">
          {list === null && <p className="text-muted-foreground text-sm">Loading…</p>}
          {list?.length === 0 && (
            <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              No conversations yet. Send a message in the preview.
            </p>
          )}
          {list?.map((item) => (
            <button
              key={item.id}
              onClick={() => api.conversation(item.id).then(setOpen)}
              className={cn(
                'hover:bg-muted/60 flex flex-col gap-1.5 rounded-lg border p-3 text-left text-sm',
                open?.id === item.id && 'bg-muted',
              )}
            >
              <span className="line-clamp-2">{item.opening || '(no message)'}</span>
              <span className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground text-xs">
                  {item.turns} turn{item.turns === 1 ? '' : 's'} ·{' '}
                  {new Date(item.updated_at * 1000).toLocaleString()}
                </span>
                {item.blocked && <Badge variant="destructive">guard stepped in</Badge>}
                {item.refused && <Badge variant="outline">off topic</Badge>}
                {item.handed_off && <Badge variant="secondary">handed off</Badge>}
              </span>
            </button>
          ))}
        </div>
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>{open ? `Conversation ${open.id}` : 'Select a conversation'}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5 font-mono text-xs">
            {open?.events.map((event, index) => {
              const line = describe(event)
              if (!line) return null
              return (
                <p
                  key={index}
                  className={cn(
                    '[overflow-wrap:anywhere]',
                    TONES[line.tone],
                    event.kind === 'customer' && index > 0 && 'mt-3 border-t pt-3',
                  )}
                >
                  {line.text}
                </p>
              )
            })}
          </CardContent>
        </Card>
      </div>
    </Section>
  )
}

// -- Install -----------------------------------------------------------------

export function Snippet({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      /* the code is selectable, so copying by hand still works */
    }
  }
  return (
    <div className="relative">
      <pre className="bg-muted overflow-x-auto rounded-lg p-4 pr-12 text-xs leading-relaxed">
        <code>{code}</code>
      </pre>
      <Button variant="ghost" size="icon" className="absolute top-2 right-2 size-8" onClick={copy}>
        {copied ? <CheckIcon /> : <CopyIcon />}
        <span className="sr-only">Copy</span>
      </Button>
    </div>
  )
}

export function InstallSection(_: SectionProps) {
  const origin = window.location.origin
  const snippets: [string, string, string, string][] = [
    [
      'html',
      'Any website',
      'Paste before the closing </body> tag. That is the whole install.',
      `<script src="${origin}/widget.js" defer></script>`,
    ],
    [
      'php',
      'PHP',
      'Add to your footer template. For signed-in customers, sign their id on your server so the rep remembers them. Keep the secret out of the page.',
      `<?php
// footer.php
$userId = $_SESSION['user_id'] ?? null;
$secret = getenv('REPKIT_IDENTITY_SECRET');  // same value as on the chat server
?>
<script src="${origin}/widget.js" defer
<?php if ($userId): ?>
  data-repkit-customer="<?= htmlspecialchars($userId, ENT_QUOTES) ?>"
  data-repkit-signature="<?= hash_hmac('sha256', $userId, $secret) ?>"
<?php endif; ?>
></script>`,
    ],
    [
      'wordpress',
      'WordPress',
      "Add to your theme's functions.php, or to a small plugin.",
      `add_action('wp_enqueue_scripts', function () {
    wp_enqueue_script('repkit', '${origin}/widget.js', [], null, [
        'strategy'  => 'defer',
        'in_footer' => true,
    ]);
});`,
    ],
    [
      'react',
      'React / Next.js',
      'Load the script once, in your root layout.',
      `// app/layout.tsx
import Script from 'next/script'

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Script src="${origin}/widget.js" strategy="lazyOnload" />
      </body>
    </html>
  )
}`,
    ],
  ]

  return (
    <Section
      title="Install"
      description="One script tag puts the chat on your site. It adds a launcher button and loads the chat in its own frame, so it cannot clash with your site's styles."
    >
      <Tabs defaultValue="html">
        <TabsList>
          {snippets.map(([key, label]) => (
            <TabsTrigger key={key} value={key}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        {snippets.map(([key, , note, code]) => (
          <TabsContent key={key} value={key} className="flex flex-col gap-3">
            <p className="text-muted-foreground text-sm">{note}</p>
            <Snippet code={code} />
          </TabsContent>
        ))}
      </Tabs>
      <Card>
        <CardHeader>
          <CardTitle>Options</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground grid gap-2 text-sm">
          <p>
            <code className="text-foreground">data-repkit-open="true"</code> opens the chat when
            the page loads.
          </p>
          <p>
            <code className="text-foreground">data-repkit-pacing="off"</code> shows replies at
            once, without typing delays.
          </p>
          <p>
            From your own scripts: <code className="text-foreground">window.repkit.open()</code>,{' '}
            <code className="text-foreground">close()</code> and{' '}
            <code className="text-foreground">send("text")</code>.
          </p>
        </CardContent>
      </Card>
    </Section>
  )
}
