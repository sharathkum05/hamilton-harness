// The dashboard's test runner and install snippets.

import { useState } from 'react'
import { CheckIcon, CopyIcon, PlayIcon } from 'lucide-react'

import type { SimReport } from '@/admin/api'
import { Section } from '@/admin/fields'
import type { SectionProps } from '@/admin/sections'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

// -- Test --------------------------------------------------------------------

const STATS: [string, string][] = [
  ['actions_run', 'Actions run'],
  ['actions_blocked', 'Actions blocked'],
  ['replies_replaced', 'Replies replaced'],
  ['off_topic_refused', 'Off topic refused'],
  ['handoffs', 'Handed to a human'],
]

/** The share of test customers that passed, drawn as a ring. */
function PassRing({ passed, total }: { passed: number; total: number }) {
  const radius = 34
  const around = 2 * Math.PI * radius
  const share = total > 0 ? passed / total : 0
  return (
    <div className="relative size-24 shrink-0">
      <svg viewBox="0 0 80 80" className="size-full -rotate-90" aria-hidden="true">
        <circle cx="40" cy="40" r={radius} fill="none" strokeWidth="7" className="stroke-muted" />
        <circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={around}
          strokeDashoffset={around * (1 - share)}
          className={passed === total ? 'stroke-foreground' : 'stroke-destructive'}
          style={{ transition: 'stroke-dashoffset 600ms ease-out' }}
        />
      </svg>
      <span className="font-heading absolute inset-0 flex items-center justify-center text-xl tabular-nums">
        {Math.round(share * 100)}%
      </span>
    </div>
  )
}

export function TestSection({ pack, api }: SectionProps) {
  const [only, setOnly] = useState<'all' | 'failed'>('all')
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
          <div className="bg-card flex flex-wrap items-center gap-6 rounded-2xl border p-5">
            <PassRing
              passed={Number(report.summary.passed)}
              total={Number(report.summary.scenarios)}
            />
            <div className="flex flex-col gap-1">
              <span className="font-heading text-3xl">
                {report.summary.passed} of {report.summary.scenarios} passed
              </span>
              <span className="text-muted-foreground text-sm">
                {report.summary.passed === report.summary.scenarios
                  ? 'Every rule held. The rep is safe to put in front of customers.'
                  : 'At least one rule gave way. Fix it before the rep goes live.'}
              </span>
            </div>
            <Tabs
              value={only}
              onValueChange={(value) => setOnly(value as 'all' | 'failed')}
              className="ml-auto"
            >
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="failed">Failed</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {STATS.map(([key, label]) => (
              <Card key={key}>
                <CardContent className="flex flex-col gap-1">
                  <span className="text-2xl font-semibold tabular-nums">
                    {report.summary[key] ?? 0}
                  </span>
                  <span className="text-muted-foreground text-xs">{label}</span>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="flex flex-col gap-2">
            {only === 'failed' && report.results.every((result) => result.passed) && (
              <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
                Nothing failed.
              </p>
            )}
            {report.results
              .filter((result) => only === 'all' || !result.passed)
              .map((result) => (
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
                    {result.error && (
                      <p className="text-destructive text-sm">Crashed: {result.error}</p>
                    )}
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
$secret = getenv('HAMILTON_IDENTITY_SECRET');  // same value as on the chat server
?>
<script src="${origin}/widget.js" defer
<?php if ($userId): ?>
  data-hamilton-customer="<?= htmlspecialchars($userId, ENT_QUOTES) ?>"
  data-hamilton-signature="<?= hash_hmac('sha256', $userId, $secret) ?>"
<?php endif; ?>
></script>`,
    ],
    [
      'wordpress',
      'WordPress',
      "Add to your theme's functions.php, or to a small plugin.",
      `add_action('wp_enqueue_scripts', function () {
    wp_enqueue_script('hamilton', '${origin}/widget.js', [], null, [
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
          <CardTitle>Connect Claude</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-muted-foreground text-sm">
            Install the npm package, sign in to this server with the admin token, and add it to
            Claude. Claude can then edit knowledge, rules and settings, work through orders and
            quotes, and rerun the tests.
          </p>
          <Snippet
            code={`npm install -g hamilton-harness
hamilton-harness login --url ${origin}
claude mcp add hamilton -- hamilton-harness mcp`}
          />
          <p className="text-muted-foreground text-sm">
            Without installing: <code className="text-foreground">npx -y hamilton-harness mcp</code>
            , with <code className="text-foreground">HAMILTON_URL</code> and{' '}
            <code className="text-foreground">HAMILTON_ADMIN_TOKEN</code> set.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Options</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground grid gap-2 text-sm">
          <p>
            <code className="text-foreground">data-hamilton-open="true"</code> opens the chat when
            the page loads.
          </p>
          <p>
            <code className="text-foreground">data-hamilton-pacing="off"</code> shows replies at
            once, without typing delays.
          </p>
          <p>
            From your own scripts: <code className="text-foreground">window.hamilton.open()</code>,{' '}
            <code className="text-foreground">close()</code> and{' '}
            <code className="text-foreground">send("text")</code>.
          </p>
        </CardContent>
      </Card>
    </Section>
  )
}
