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
