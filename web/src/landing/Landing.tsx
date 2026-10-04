// The product page, in black and white. Headings are set in Cal Sans and body
// text in Geist, on a 1.25 scale from 16px. Sections sit 96px apart on desktop
// and each section header is 48px above its content, so a heading always reads
// as belonging to what follows.

import { useEffect, useRef, useState } from 'react'
import type { ComponentType, ReactNode, RefObject } from 'react'
import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  InboxIcon,
  ShieldCheckIcon,
  SparklesIcon,
  TargetIcon,
  UserIcon,
} from 'lucide-react'

import { Snippet } from '@/admin/more'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { AnimatedBeam } from '@/components/ui/animated-beam'
import { AnimatedList } from '@/components/ui/animated-list'
import { AnimatedShinyText } from '@/components/ui/animated-shiny-text'
import { BentoCard, BentoGrid } from '@/components/ui/bento-grid'
import { BorderBeam } from '@/components/ui/border-beam'
import { BrandMark } from '@/components/brand-mark'
import { Button } from '@/components/ui/button'
import { FlickeringGrid } from '@/components/ui/flickering-grid'
import { MagicCard } from '@/components/ui/magic-card'
import { Marquee } from '@/components/ui/marquee'
import { NumberTicker } from '@/components/ui/number-ticker'
import { Ripple } from '@/components/ui/ripple'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AnimatedSpan, Terminal, TypingAnimation } from '@/components/ui/terminal'
import { WordRotate } from '@/components/ui/word-rotate'
import {
  BUSINESSES,
  DASHBOARD,
  EVENTS,
  FAQ,
  GUARDS,
  ROLES,
  SAID,
  STATS,
  SYSTEMS,
  TERMINAL_LINES,
} from '@/landing/data'
import { cn } from '@/lib/utils'

const HEADING = 'leading-[1.05] text-balance [word-spacing:0.05em]'
// Headlines fade slightly toward the bottom, which gives large type some depth.
const FADE = 'bg-gradient-to-b from-foreground to-foreground/65 bg-clip-text text-transparent'

/** Follow the visitor's device theme, and report it for components that need a colour. */
function useDarkTheme(): boolean {
  const [dark, setDark] = useState(() => window.matchMedia('(prefers-color-scheme: dark)').matches)
  useEffect(() => {
    const system = window.matchMedia('(prefers-color-scheme: dark)')
    const sync = () => {
      document.documentElement.classList.toggle('dark', system.matches)
      setDark(system.matches)
    }
    sync()
    system.addEventListener('change', sync)
    return () => system.removeEventListener('change', sync)
  }, [])
  return dark
}

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="text-muted-foreground inline-flex items-center gap-2 font-mono text-sm">
      <span className="bg-foreground size-1.5 rounded-full" aria-hidden="true" />
      {children}
    </p>
  )
}

function SectionHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children: ReactNode }) {
  return (
    <div className="mx-auto grid max-w-6xl items-end gap-x-12 gap-y-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-4">
        <Eyebrow>{eyebrow}</Eyebrow>
        <h2 className={cn('text-4xl sm:text-5xl lg:text-6xl', HEADING, FADE)}>{title}</h2>
      </div>
      <p className="text-muted-foreground max-w-[52ch] text-lg leading-relaxed text-pretty lg:pb-1.5">
        {children}
      </p>
    </div>
  )
}

/** A two-line exchange, used as the picture inside each guardrail card. */
function Exchange({ customer, rep, note }: { customer: string; rep: string; note: string }) {
  return (
    <div className="absolute inset-x-0 top-0 flex flex-col gap-2 p-6 [mask-image:linear-gradient(to_bottom,black_80%,transparent_100%)]">
      <p className="bg-primary text-primary-foreground ml-auto max-w-[85%] rounded-2xl rounded-br-md px-3.5 py-2 text-sm">
        {customer}
      </p>
      <p className="bg-secondary max-w-[85%] rounded-2xl rounded-bl-md px-3.5 py-2 text-sm">{rep}</p>
      <p className="text-muted-foreground font-mono text-xs">{note}</p>
    </div>
  )
}

function Node({
  nodeRef,
  Icon,
  label,
  strong,
}: {
  nodeRef: RefObject<HTMLDivElement | null>
  Icon: ComponentType<{ className?: string }>
  label: string
  strong?: boolean
}) {
  return (
    <div className="z-10 flex w-16 flex-col items-center gap-2 text-center sm:w-24">
      <div
        ref={nodeRef}
        className={cn(
          'flex size-12 items-center justify-center rounded-2xl border shadow-sm sm:size-14',
          strong ? 'bg-primary text-primary-foreground border-transparent' : 'bg-background',
        )}
      >
        <Icon className="size-5" />
      </div>
      <span className="text-xs leading-tight font-medium">{label}</span>
    </div>
  )
}

/** One message's path through the harness, with the two code checks filled in. */
function Flow({ dark }: { dark: boolean }) {
  const container = useRef<HTMLDivElement>(null)
  const customer = useRef<HTMLDivElement>(null)
  const scope = useRef<HTMLDivElement>(null)
  const model = useRef<HTMLDivElement>(null)
  const guard = useRef<HTMLDivElement>(null)
  const business = useRef<HTMLDivElement>(null)
  const beams: [RefObject<HTMLDivElement | null>, RefObject<HTMLDivElement | null>][] = [
    [customer, scope],
    [scope, model],
    [model, guard],
    [guard, business],
  ]
  return (
    <div
      ref={container}
      className="bg-card relative mx-auto mt-12 flex max-w-6xl items-start justify-between overflow-hidden rounded-2xl border px-3 py-14 sm:px-16"
    >
      <Node nodeRef={customer} Icon={UserIcon} label="Customer" />
      <Node nodeRef={scope} Icon={TargetIcon} label="Scope gate" strong />
      <Node nodeRef={model} Icon={SparklesIcon} label="Model drafts" />
      <Node nodeRef={guard} Icon={ShieldCheckIcon} label="Guard" strong />
      <Node nodeRef={business} Icon={InboxIcon} label="Your business" />
      {beams.map(([from, to], index) => (
        <AnimatedBeam
          key={index}
          containerRef={container}
          fromRef={from}
          toRef={to}
          duration={3}
          delay={index * 0.4}
          pathColor={dark ? '#52525b' : '#a1a1aa'}
          gradientStartColor="#a1a1aa"
          gradientStopColor={dark ? '#fafafa' : '#18181b'}
        />
      ))}
    </div>
  )
}

/** The product, framed as a window: the live chat beside what the harness does behind it. */
function ProductWindow({ strong }: { strong: string }) {
  return (
    <div className="bg-card/80 relative mx-auto mt-14 w-full max-w-5xl overflow-hidden rounded-2xl border shadow-2xl backdrop-blur">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <span className="bg-muted-foreground/30 size-2.5 rounded-full" />
        <span className="bg-muted-foreground/30 size-2.5 rounded-full" />
        <span className="bg-muted-foreground/30 size-2.5 rounded-full" />
        <span className="text-muted-foreground mx-auto font-mono text-xs">loop-sneakers · live</span>
      </div>
      <div className="grid lg:grid-cols-[400px_minmax(0,1fr)]">
        <iframe
          title="Live chat with the demo rep"
          src="/chat?nopacing&inline"
          className="h-[520px] w-full border-b lg:border-r lg:border-b-0"
        />
        <div className="relative flex h-[520px] flex-col gap-4 overflow-hidden p-5">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-lg">Behind the conversation</h3>
            <span className="text-muted-foreground font-mono text-xs">from the test suite</span>
          </div>
          <AnimatedList delay={1800} className="items-stretch gap-2.5">
            {EVENTS.map(([Icon, title, detail]) => (
              <div key={title} className="bg-background flex items-center gap-3 rounded-xl border p-3">
                <span className="bg-muted flex size-9 shrink-0 items-center justify-center rounded-lg">
                  <Icon className="size-4" />
                </span>
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-sm font-medium">{title}</span>
                  <span className="text-muted-foreground truncate text-sm">{detail}</span>
                </span>
              </div>
            ))}
          </AnimatedList>
          <div className="from-card pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t" />
        </div>
      </div>
      <BorderBeam duration={10} size={180} colorFrom="#a1a1aa" colorTo={strong} />
    </div>
  )
}

function SaidChip({ said, outcome }: { said: string; outcome: string }) {
  return (
    <div className="bg-card flex items-center gap-3 rounded-full border py-1.5 pr-1.5 pl-4 text-sm whitespace-nowrap">
      <span>{said}</span>
      <span className="bg-muted text-muted-foreground rounded-full px-2.5 py-1 font-mono text-xs">
        {outcome}
      </span>
    </div>
  )
}

function SystemCard({ Icon, name, kind }: { Icon: ComponentType<{ className?: string }>; name: string; kind: string }) {
  return (
    <div className="bg-card flex h-36 w-52 shrink-0 flex-col justify-between rounded-lg border p-5">
      <Icon className="size-6" />
      <div className="flex flex-col gap-0.5">
        <span className="text-lg leading-tight">{name}</span>
        <span className="text-muted-foreground text-sm">{kind}</span>
      </div>
    </div>
  )
}

export function Landing() {
  const origin = window.location.origin
  const dark = useDarkTheme()
  const strong = dark ? '#fafafa' : '#18181b'

  useEffect(() => {
    document.title = 'Hamilton Harness: the AI harness for your business'
  }, [])

  return (
    <div className="bg-background text-foreground relative min-h-full">
      <div className="grain" aria-hidden="true" />
      {/* A floating glass bar over the page, with the content fading out beneath it. */}
      <div className="scroll-edge" aria-hidden="true" />
      <header className="sticky top-3 z-40 px-3">
        <div className="glass mx-auto flex h-13 max-w-3xl items-center justify-between gap-4 rounded-full px-2 pl-5">
          <a href="/" className="font-heading flex items-center gap-2 text-lg">
            <BrandMark />
            Hamilton
          </a>
          <nav aria-label="Page sections" className="text-foreground/75 hidden items-center gap-0.5 text-sm md:flex">
            <a className="hover:text-foreground hover:bg-foreground/[0.07] rounded-full px-3 py-1.5 transition-colors" href="#roles">What it runs</a>
            <a className="hover:text-foreground hover:bg-foreground/[0.07] rounded-full px-3 py-1.5 transition-colors" href="#integrations">Integrations</a>
            <a className="hover:text-foreground hover:bg-foreground/[0.07] rounded-full px-3 py-1.5 transition-colors" href="#guardrails">Guardrails</a>
            <a className="hover:text-foreground hover:bg-foreground/[0.07] rounded-full px-3 py-1.5 transition-colors" href="#dashboard">Dashboard</a>
            <a className="hover:text-foreground hover:bg-foreground/[0.07] rounded-full px-3 py-1.5 transition-colors" href="#install">Install</a>
          </nav>
          <Button asChild size="sm" className="rounded-full">
            <a href="/demo">
              Try the demo <ArrowUpRightIcon />
            </a>
          </Button>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="relative -mt-[60px] overflow-hidden pt-[60px]">
          <FlickeringGrid
            className="absolute inset-0 [mask-image:radial-gradient(60%_55%_at_50%_0%,black,transparent)]"
            squareSize={4}
            gridGap={6}
            color={dark ? '#fafafa' : '#18181b'}
            maxOpacity={dark ? 0.16 : 0.1}
            flickerChance={0.12}
          />
          <div className="relative mx-auto flex max-w-6xl flex-col items-center px-4 pt-16 pb-16 text-center sm:px-6 lg:pt-24 lg:pb-24">
            <div className="flex flex-col items-center gap-6">
              <a
                href="#guardrails"
                className="bg-background/80 hover:bg-muted rounded-full border px-3.5 py-1 text-sm backdrop-blur transition-colors"
              >
                <AnimatedShinyText className="inline-flex items-center gap-1.5">
                  On your brand. Inside your rules. On your topic. <ArrowRightIcon className="size-3.5" />
                </AnimatedShinyText>
              </a>
              <h1 className={cn('max-w-4xl text-5xl sm:text-6xl lg:text-7xl', HEADING, FADE)}>
                The AI harness for your business.
              </h1>
              <div className="text-muted-foreground flex flex-wrap items-center justify-center gap-x-2 text-xl sm:text-2xl">
                <span>It runs your</span>
                <WordRotate
                  className="text-foreground font-heading"
                  words={['customer support', 'order desk', 'quotation requests', 'front desk']}
                />
              </div>
              <p className="text-muted-foreground max-w-[60ch] text-lg leading-relaxed text-pretty">
                Hamilton turns one language model into your company's own rep. It answers from your
                knowledge, takes orders and quotation requests, and hands over to your team when it
                should. Code, not a prompt, enforces what it may promise, do and talk about.
              </p>
              <div className="flex flex-wrap justify-center gap-3">
                <Button asChild size="lg" className="rounded-full px-6">
                  <a href="/demo">
                    Try the live demo <ArrowRightIcon />
                  </a>
                </Button>
                <Button asChild size="lg" variant="outline" className="rounded-full px-6">
                  <a href="#install">Put it on your site</a>
                </Button>
              </div>
              <p className="text-muted-foreground font-mono text-xs">
                The chat below is live. No sign-up and no API key.
              </p>
            </div>
            <div className="w-full text-left">
              <ProductWindow strong={strong} />
            </div>
          </div>
        </section>

        {/* What customers say */}
        <section aria-label="Examples of what the rep handles" className="border-y py-6">
          <div className="relative [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]">
            <Marquee pauseOnHover className="[--duration:48s] [--gap:0.75rem]">
              {SAID.map(([said, outcome]) => (
                <SaidChip key={said} said={said} outcome={outcome} />
              ))}
            </Marquee>
          </div>
        </section>

        {/* Numbers */}
        <section aria-label="Hamilton Harness in numbers" className="border-b">
          <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-8 px-4 py-14 sm:px-6 lg:grid-cols-4">
            {STATS.map(([value, label]) => (
              <div key={label} className="flex flex-col gap-1.5">
                <dt className="text-muted-foreground order-2 text-sm text-pretty">{label}</dt>
                <dd className="font-heading order-1 text-5xl tabular-nums">
                  {value === 0 ? '0' : <NumberTicker value={value} />}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Roles */}
        <section id="roles" className="scroll-mt-20 px-4 py-20 sm:px-6 lg:py-32">
          <SectionHeader eyebrow="What it runs" title="One harness, every front line.">
            The same harness becomes a support rep, an order desk or a front desk. What changes is
            the folder that describes your business.
          </SectionHeader>
          <div className="mx-auto mt-12 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-12">
            {ROLES.map(([Icon, name, text], index) => (
              <MagicCard
                key={name}
                // 7 + 5, then 5 + 7: the wide card alternates sides.
                className={cn('rounded-2xl', index % 3 === 0 ? 'lg:col-span-7' : 'lg:col-span-5')}
                gradientColor={dark ? '#262626' : '#e5e5e5'}
                gradientFrom="#a1a1aa"
                gradientTo={strong}
              >
                <div className="flex h-full min-h-52 flex-col justify-between gap-8 p-7">
                  <span className="bg-muted flex size-10 items-center justify-center rounded-xl border">
                    <Icon className="size-5" />
                  </span>
                  <div className="flex flex-col gap-2">
                    <h3 className="text-2xl sm:text-3xl">{name}</h3>
                    <p className="text-muted-foreground max-w-[46ch] leading-relaxed">{text}</p>
                  </div>
                </div>
              </MagicCard>
            ))}
          </div>
        </section>

        {/* Integrations */}
        <section id="integrations" className="scroll-mt-20 border-t py-20 lg:py-32">
          <div className="mx-auto flex max-w-3xl flex-col items-center gap-5 px-4 text-center sm:px-6">
            <p className="text-muted-foreground flex items-center gap-3 font-mono text-sm">
              <span className="bg-border h-px w-8" aria-hidden="true" />
              Integrations
              <span className="bg-border h-px w-8" aria-hidden="true" />
            </p>
            <h2 className={cn('text-4xl sm:text-5xl lg:text-6xl', HEADING, FADE)}>
              Connects to your internal systems.
            </h2>
            <p className="text-muted-foreground max-w-[60ch] text-lg leading-relaxed text-pretty">
              The rep collects the details in every conversation and writes them straight to your
              calendar, CRM and tools, so your team never re-enters a thing. Each connection is a
              short action you define over that system's API, so anything with an API can be
              connected, HubSpot, Salesforce, Cal.com and Slack included.
            </p>
          </div>
          <div className="mt-14 flex flex-col gap-4 [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
            <Marquee pauseOnHover className="p-0 [--duration:44s] [--gap:1rem]">
              {SYSTEMS.map(([Icon, name, kind]) => (
                <SystemCard key={name} Icon={Icon} name={name} kind={kind} />
              ))}
            </Marquee>
            <Marquee reverse pauseOnHover className="p-0 [--duration:44s] [--gap:1rem]">
              {BUSINESSES.map(([Icon, name, kind]) => (
                <SystemCard key={name} Icon={Icon} name={name} kind={kind} />
              ))}
            </Marquee>
          </div>
        </section>

        {/* Flow */}
        <section id="how" className="bg-muted/40 scroll-mt-20 border-y px-4 py-20 sm:px-6 lg:py-32">
          <SectionHeader eyebrow="How it works" title="A prompt asks. Code enforces.">
            The model writes a draft in the middle. Before it, a gate decides whether the message is
            your business at all. After it, a guard checks every action and every reply.
          </SectionHeader>
          <Flow dark={dark} />
        </section>

        {/* Guardrails */}
        <section id="guardrails" className="scroll-mt-20 px-4 py-20 sm:px-6 lg:py-32">
          <SectionHeader eyebrow="Guardrails" title="It refuses what it should.">
            Other bots will do a customer's homework. This one is checked in code at every step, so
            a rule holds even when the model is talked out of it. Each example is a test that runs
            on every change.
          </SectionHeader>
          <BentoGrid className="mx-auto mt-12 max-w-6xl auto-rows-[25rem] sm:auto-rows-[20rem] lg:grid-cols-3">
            {GUARDS.map(({ customer, rep, note, ...guard }) => (
              <BentoCard
                key={guard.name}
                {...guard}
                className={cn('rounded-2xl', guard.className)}
                background={<Exchange customer={customer} rep={rep} note={note} />}
                href="/demo"
                cta="See it in the demo"
              />
            ))}
          </BentoGrid>
        </section>

        {/* Proof */}
        <section className="bg-muted/40 border-y px-4 py-20 sm:px-6 lg:py-32">
          <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
            <div className="flex min-w-0 flex-col gap-4">
              <Eyebrow>Tested like software</Eyebrow>
              <h2 className={cn('text-4xl sm:text-5xl', HEADING, FADE)}>
                Fake customers try to break it before real ones can.
              </h2>
              <p className="text-muted-foreground text-lg leading-relaxed text-pretty">
                Every pack carries its own test customers: polite, angry, confused and hostile. In
                several the model is made to misbehave on purpose. The run fails if a single rule
                gives way, and it runs on every change.
              </p>
            </div>
            {/* min-w-0 and wrapping: a long line must not widen the page on a phone. */}
            <Terminal className="max-w-none min-w-0 rounded-2xl [&_code]:whitespace-pre-wrap [&_pre]:overflow-x-auto">
              <TypingAnimation>$ hamilton-harness sim packs/loop-sneakers</TypingAnimation>
              {TERMINAL_LINES.map((line) => (
                <AnimatedSpan key={line} className="text-muted-foreground">
                  {line}
                </AnimatedSpan>
              ))}
              <AnimatedSpan>16/16 scenarios passed, 57/57 checks</AnimatedSpan>
              <AnimatedSpan>blocked by guard 4, replies replaced 3, off topic refused 2</AnimatedSpan>
            </Terminal>
          </div>
        </section>

        {/* Dashboard */}
        <section id="dashboard" className="scroll-mt-20 px-4 py-20 sm:px-6 lg:py-32">
          <SectionHeader eyebrow="Dashboard" title="Run it like part of the business.">
            See the orders and quotation requests it has taken, read any conversation step by step,
            and change anything about the rep without touching code.
          </SectionHeader>
          {/* minmax(0, 1fr) and min-w-0: the code sample must not widen the column on a phone. */}
          <div className="mx-auto mt-12 grid max-w-6xl grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-2">
            <ul className="grid min-w-0 gap-4 sm:grid-cols-2">
              {DASHBOARD.map(([Icon, name, text]) => (
                <li key={name} className="bg-card flex flex-col gap-2 rounded-2xl border p-5">
                  <span className="bg-muted flex size-9 items-center justify-center rounded-lg border">
                    <Icon className="size-4" />
                  </span>
                  <h3 className="text-lg">{name}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{text}</p>
                </li>
              ))}
            </ul>
            <div className="bg-card flex min-w-0 flex-col gap-4 rounded-2xl border p-6">
              <h3 className="text-2xl">Or connect Claude and just ask</h3>
              <p className="text-muted-foreground leading-relaxed">
                Hamilton ships an MCP server. Connect Claude to it and say "add our new returns
                policy", "stop it discussing competitors" or "show me today's quotation requests".
                Claude edits through the same validated editor as the dashboard, and a change that
                would break the rep is refused.
              </p>
              <Snippet
                code={`{
  "mcpServers": {
    "hamilton": {
      "command": "hamilton-harness",
      "args": ["mcp", "packs/your-company"]
    }
  }
}`}
              />
              <Button asChild variant="outline" className="self-start rounded-full">
                <a href="/admin">
                  Open the dashboard <ArrowRightIcon />
                </a>
              </Button>
            </div>
          </div>
        </section>

        {/* Install */}
        <section id="install" className="bg-muted/40 scroll-mt-20 border-y px-4 py-20 sm:px-6 lg:py-32">
          <SectionHeader eyebrow="Install" title="One script tag.">
            It works on a hand-written page, a PHP site, WordPress or a React app. The chat loads in
            its own frame, so it cannot clash with your styles. One npm package connects Claude.
          </SectionHeader>
          <div className="mx-auto mt-12 max-w-6xl">
            <Tabs defaultValue="html">
              <TabsList>
                <TabsTrigger value="html">HTML</TabsTrigger>
                <TabsTrigger value="php">PHP</TabsTrigger>
                <TabsTrigger value="wordpress">WordPress</TabsTrigger>
                <TabsTrigger value="react">React</TabsTrigger>
                <TabsTrigger value="claude">Claude</TabsTrigger>
              </TabsList>
              <TabsContent value="html">
                <Snippet code={`<script src="${origin}/widget.js" defer></script>`} />
              </TabsContent>
              <TabsContent value="php">
                <Snippet
                  code={`<?php $userId = $_SESSION['user_id'] ?? null; ?>
<script src="${origin}/widget.js" defer
<?php if ($userId): ?>
  data-hamilton-customer="<?= htmlspecialchars($userId, ENT_QUOTES) ?>"
  data-hamilton-signature="<?= hash_hmac('sha256', $userId, getenv('HAMILTON_IDENTITY_SECRET')) ?>"
<?php endif; ?>
></script>`}
                />
              </TabsContent>
              <TabsContent value="wordpress">
                <Snippet
                  code={`add_action('wp_enqueue_scripts', function () {
    wp_enqueue_script('hamilton', '${origin}/widget.js', [], null, [
        'strategy' => 'defer', 'in_footer' => true,
    ]);
});`}
                />
              </TabsContent>
              <TabsContent value="react">
                <Snippet
                  code={`import Script from 'next/script'

<Script src="${origin}/widget.js" strategy="lazyOnload" />`}
                />
              </TabsContent>
              <TabsContent value="claude" className="flex flex-col gap-3">
                <p className="text-muted-foreground text-sm">
                  Install the npm package, sign in to your server once, and add it to Claude. Then
                  ask Claude to update the rep in plain words.
                </p>
                <Snippet
                  code={`npm install -g hamilton-harness
hamilton-harness login --url ${origin}
claude mcp add hamilton -- hamilton-harness mcp`}
                />
              </TabsContent>
            </Tabs>
          </div>
        </section>

        {/* Questions */}
        <section className="px-4 py-20 sm:px-6 lg:py-32">
          <SectionHeader eyebrow="Questions" title="Straight answers.">
            What it does, what it does not, and where the limits are.
          </SectionHeader>
          <Accordion type="single" collapsible className="mx-auto mt-12 max-w-6xl">
            {FAQ.map(([question, answer]) => (
              <AccordionItem key={question} value={question}>
                <AccordionTrigger className="text-left text-base">{question}</AccordionTrigger>
                <AccordionContent className="text-muted-foreground text-base leading-relaxed">
                  {answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>

        {/* Closing */}
        <section className="px-4 pb-16 sm:px-6 lg:pb-24">
          <div className="bg-card relative mx-auto flex max-w-6xl flex-col items-center gap-6 overflow-hidden rounded-3xl border px-6 py-20 text-center">
            <Ripple mainCircleSize={160} mainCircleOpacity={0.18} numCircles={7} />
            <h2 className={cn('relative text-4xl sm:text-5xl', HEADING, FADE)}>
              Try to make it break a rule.
            </h2>
            <p className="text-muted-foreground relative max-w-[52ch] text-lg leading-relaxed text-pretty">
              The demo shows every turn from the inside: the rules the rep was given, each action it
              tried, and what the guard allowed or stopped.
            </p>
            <Button asChild size="lg" className="relative rounded-full px-6">
              <a href="/demo">
                Open the demo <ArrowRightIcon />
              </a>
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="text-muted-foreground mx-auto flex max-w-6xl flex-wrap justify-between gap-2 px-4 py-8 text-sm sm:px-6">
          <p className="flex items-center gap-2">
            <BrandMark className="size-5 rounded-md pt-0.5 text-xs" />
            Hamilton Harness · the AI harness for your business · MIT licence
          </p>
          <p>Loop Sneakers and Brightside Dental are made-up companies used as demos.</p>
        </div>
      </footer>
    </div>
  )
}
