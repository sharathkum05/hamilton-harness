// The product page, in black and white. Type follows a 1.25 scale from a 16px
// body, sections sit 96px apart on desktop, and each section header is 48px
// above its content, so a heading always reads as belonging to what follows.

import { useEffect, useRef, useState } from 'react'
import type { ComponentType, ReactNode, RefObject } from 'react'
import {
  ArrowRightIcon,
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
import { AnimatedShinyText } from '@/components/ui/animated-shiny-text'
import { BentoCard, BentoGrid } from '@/components/ui/bento-grid'
import { BlurFade } from '@/components/ui/blur-fade'
import { BorderBeam } from '@/components/ui/border-beam'
import { Button } from '@/components/ui/button'
import { DotPattern } from '@/components/ui/dot-pattern'
import { MagicCard } from '@/components/ui/magic-card'
import { NumberTicker } from '@/components/ui/number-ticker'
import { Orb } from '@/components/ui/orb'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AnimatedSpan, Terminal, TypingAnimation } from '@/components/ui/terminal'
import { WordRotate } from '@/components/ui/word-rotate'
import { DASHBOARD, FAQ, GUARDS, ROLES, STATS, TERMINAL_LINES } from '@/landing/data'
import { cn } from '@/lib/utils'

const GREY_ORB: [string, string] = ['#e4e4e7', '#a1a1aa']

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

function SectionHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 text-center">
      <p className="text-muted-foreground font-mono text-xs tracking-widest uppercase">{eyebrow}</p>
      <h2 className="text-3xl leading-[1.1] font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      <p className="text-muted-foreground text-lg leading-relaxed text-pretty">{children}</p>
    </div>
  )
}

/** A two-line exchange, used as the picture inside each guardrail card. */
function Exchange({ customer, rep, note }: { customer: string; rep: string; note: string }) {
  return (
    <div className="absolute inset-x-0 top-0 flex flex-col gap-2 p-6 [mask-image:linear-gradient(to_bottom,black_80%,transparent_100%)]">
      <p className="bg-primary text-primary-foreground ml-auto max-w-[85%] rounded-lg px-3 py-2 text-sm">
        {customer}
      </p>
      <p className="bg-secondary max-w-[85%] rounded-lg px-3 py-2 text-sm">{rep}</p>
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
          'flex size-12 items-center justify-center rounded-full border shadow-sm',
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
      className="bg-card relative mx-auto mt-12 flex max-w-4xl items-start justify-between overflow-hidden rounded-xl border px-3 py-10 sm:px-10"
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

export function Landing() {
  const origin = window.location.origin
  const dark = useDarkTheme()
  const strong = dark ? '#fafafa' : '#18181b'

  useEffect(() => {
    document.title = 'repkit: the AI harness for your business'
  }, [])

  return (
    <div className="bg-background text-foreground min-h-full">
      <header className="bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <a href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <span className="ring-border size-6 overflow-hidden rounded-full ring-1">
              <Orb className="size-full" colors={GREY_ORB} />
            </span>
            repkit
          </a>
          <nav aria-label="Page sections" className="text-muted-foreground hidden items-center gap-6 text-sm md:flex">
            <a className="hover:text-foreground" href="#roles">What it runs</a>
            <a className="hover:text-foreground" href="#guardrails">Guardrails</a>
            <a className="hover:text-foreground" href="#dashboard">Dashboard</a>
            <a className="hover:text-foreground" href="#install">Install</a>
          </nav>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <a href="/admin">Dashboard</a>
            </Button>
            <Button asChild size="sm">
              <a href="/demo">Try the demo</a>
            </Button>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="relative overflow-hidden border-b">
          <DotPattern className="text-foreground/15 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]" />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,1fr)_400px] lg:py-24">
            <div className="flex flex-col items-start gap-6">
              <div className="bg-background rounded-full border px-3 py-1 text-sm">
                <AnimatedShinyText>On your brand. Inside your rules. On your topic.</AnimatedShinyText>
              </div>
              <h1 className="text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
                The AI harness for your business.
              </h1>
              <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 text-xl sm:text-2xl">
                <span>It runs your</span>
                <WordRotate
                  className="text-foreground font-semibold"
                  words={['customer support', 'order desk', 'quotation requests', 'front desk']}
                />
              </div>
              <p className="text-muted-foreground max-w-[58ch] text-lg leading-relaxed text-pretty">
                repkit turns one language model into your company's own rep. It answers from your
                knowledge, takes orders and quotation requests, and hands over to your team when it
                should. Code, not a prompt, enforces what it may promise, do and talk about.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button asChild size="lg">
                  <a href="/demo">
                    Try the live demo <ArrowRightIcon />
                  </a>
                </Button>
                <Button asChild size="lg" variant="outline">
                  <a href="#install">Put it on your site</a>
                </Button>
              </div>
            </div>
            <BlurFade delay={0.15} className="relative mx-auto w-full max-w-[400px]">
              <div className="bg-card relative h-[560px] overflow-hidden rounded-xl border shadow-xl">
                <iframe title="Live chat with the demo rep" src="/chat?nopacing&inline" className="size-full" />
                <BorderBeam duration={9} size={120} colorFrom="#a1a1aa" colorTo={strong} />
              </div>
              <p className="text-muted-foreground mt-3 text-center text-sm">
                This is the real rep for a made-up shop. Ask it for a quote, a discount, or a sum.
              </p>
            </BlurFade>
          </div>
        </section>

        {/* Numbers */}
        <section aria-label="repkit in numbers" className="border-b">
          <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-8 px-4 py-12 sm:px-6 lg:grid-cols-4">
            {STATS.map(([value, label]) => (
              <div key={label} className="flex flex-col gap-1">
                <dt className="text-muted-foreground order-2 text-sm text-pretty">{label}</dt>
                <dd className="order-1 text-4xl font-semibold tracking-tight tabular-nums">
                  {value === 0 ? '0' : <NumberTicker value={value} />}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Roles */}
        <section id="roles" className="scroll-mt-14 px-4 py-16 sm:px-6 lg:py-24">
          <SectionHeader eyebrow="What it runs" title="One harness, every front line.">
            The same harness becomes a support rep, an order desk or a front desk. What changes is
            the folder that describes your business.
          </SectionHeader>
          <div className="mx-auto mt-12 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {ROLES.map(([Icon, name, text]) => (
              <MagicCard
                key={name}
                className="rounded-xl"
                gradientColor={dark ? '#262626' : '#e5e5e5'}
                gradientFrom="#a1a1aa"
                gradientTo={strong}
              >
                <div className="flex h-full flex-col gap-3 p-6">
                  <Icon className="size-5" />
                  <h3 className="text-xl font-semibold tracking-tight">{name}</h3>
                  <p className="text-muted-foreground leading-relaxed">{text}</p>
                </div>
              </MagicCard>
            ))}
          </div>
        </section>

        {/* Flow */}
        <section id="how" className="bg-muted/40 scroll-mt-14 border-y px-4 py-16 sm:px-6 lg:py-24">
          <SectionHeader eyebrow="How it works" title="A prompt asks. Code enforces.">
            The model writes a draft in the middle. Before it, a gate decides whether the message is
            your business at all. After it, a guard checks every action and every reply.
          </SectionHeader>
          <Flow dark={dark} />
        </section>

        {/* Guardrails */}
        <section id="guardrails" className="scroll-mt-14 px-4 py-16 sm:px-6 lg:py-24">
          <SectionHeader eyebrow="Guardrails" title="It refuses what it should.">
            Other bots will do a customer's homework. This one is checked in code at every step, so
            a rule holds even when the model is talked out of it. Each example is a test that runs
            on every change.
          </SectionHeader>
          <BentoGrid className="mx-auto mt-12 max-w-6xl auto-rows-[20rem] lg:grid-cols-3">
            {GUARDS.map(({ customer, rep, note, ...guard }) => (
              <BentoCard
                key={guard.name}
                {...guard}
                background={<Exchange customer={customer} rep={rep} note={note} />}
                href="/demo"
                cta="See it in the demo"
              />
            ))}
          </BentoGrid>
        </section>

        {/* Proof */}
        <section className="bg-muted/40 border-y px-4 py-16 sm:px-6 lg:py-24">
          <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
            <div className="flex min-w-0 flex-col gap-4">
              <p className="text-muted-foreground font-mono text-xs tracking-widest uppercase">
                Tested like software
              </p>
              <h2 className="text-3xl leading-[1.1] font-semibold tracking-tight text-balance sm:text-4xl">
                Fake customers try to break it before real ones can.
              </h2>
              <p className="text-muted-foreground text-lg leading-relaxed text-pretty">
                Every pack carries its own test customers: polite, angry, confused and hostile. In
                several the model is made to misbehave on purpose. The run fails if a single rule
                gives way, and it runs on every change.
              </p>
            </div>
            {/* min-w-0 and wrapping: a long line must not widen the page on a phone. */}
            <Terminal className="max-w-none min-w-0 [&_code]:whitespace-pre-wrap [&_pre]:overflow-x-auto">
              <TypingAnimation>$ repkit sim packs/loop-sneakers</TypingAnimation>
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
        <section id="dashboard" className="scroll-mt-14 px-4 py-16 sm:px-6 lg:py-24">
          <SectionHeader eyebrow="Dashboard" title="Run it like part of the business.">
            See the orders and quotation requests it has taken, read any conversation step by step,
            and change anything about the rep without touching code.
          </SectionHeader>
          <div className="mx-auto mt-12 grid max-w-6xl gap-6 lg:grid-cols-2">
            <ul className="grid gap-4 sm:grid-cols-2">
              {DASHBOARD.map(([Icon, name, text]) => (
                <li key={name} className="flex flex-col gap-2 rounded-xl border p-5">
                  <Icon className="text-muted-foreground size-5" />
                  <h3 className="font-semibold">{name}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{text}</p>
                </li>
              ))}
            </ul>
            <div className="bg-card flex flex-col gap-4 rounded-xl border p-6">
              <h3 className="text-xl font-semibold tracking-tight">Or connect Claude and just ask</h3>
              <p className="text-muted-foreground leading-relaxed">
                repkit ships an MCP server. Connect Claude to it and say "add our new returns
                policy", "stop it discussing competitors" or "show me today's quotation requests".
                Claude edits through the same validated editor as the dashboard, and a change that
                would break the rep is refused.
              </p>
              <Snippet
                code={`{
  "mcpServers": {
    "repkit": {
      "command": "repkit",
      "args": ["mcp", "packs/your-company"]
    }
  }
}`}
              />
              <Button asChild variant="outline" className="self-start">
                <a href="/admin">
                  Open the dashboard <ArrowRightIcon />
                </a>
              </Button>
            </div>
          </div>
        </section>

        {/* Install */}
        <section id="install" className="bg-muted/40 scroll-mt-14 border-y px-4 py-16 sm:px-6 lg:py-24">
          <SectionHeader eyebrow="Install" title="One script tag.">
            It works on a hand-written page, a PHP site, WordPress or a React app. The chat loads in
            its own frame, so it cannot clash with your styles.
          </SectionHeader>
          <div className="mx-auto mt-12 max-w-3xl">
            <Tabs defaultValue="html">
              <TabsList>
                <TabsTrigger value="html">HTML</TabsTrigger>
                <TabsTrigger value="php">PHP</TabsTrigger>
                <TabsTrigger value="wordpress">WordPress</TabsTrigger>
                <TabsTrigger value="react">React</TabsTrigger>
              </TabsList>
              <TabsContent value="html">
                <Snippet code={`<script src="${origin}/widget.js" defer></script>`} />
              </TabsContent>
              <TabsContent value="php">
                <Snippet
                  code={`<?php $userId = $_SESSION['user_id'] ?? null; ?>
<script src="${origin}/widget.js" defer
<?php if ($userId): ?>
  data-repkit-customer="<?= htmlspecialchars($userId, ENT_QUOTES) ?>"
  data-repkit-signature="<?= hash_hmac('sha256', $userId, getenv('REPKIT_IDENTITY_SECRET')) ?>"
<?php endif; ?>
></script>`}
                />
              </TabsContent>
              <TabsContent value="wordpress">
                <Snippet
                  code={`add_action('wp_enqueue_scripts', function () {
    wp_enqueue_script('repkit', '${origin}/widget.js', [], null, [
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
            </Tabs>
          </div>
        </section>

        {/* Questions */}
        <section className="px-4 py-16 sm:px-6 lg:py-24">
          <SectionHeader eyebrow="Questions" title="Straight answers.">
            What it does, what it does not, and where the limits are.
          </SectionHeader>
          <Accordion type="single" collapsible className="mx-auto mt-12 max-w-3xl">
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
        <section className="border-t px-4 py-16 sm:px-6 lg:py-24">
          <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 text-center">
            <h2 className="text-3xl leading-[1.1] font-semibold tracking-tight text-balance sm:text-4xl">
              Try to make it break a rule.
            </h2>
            <p className="text-muted-foreground text-lg leading-relaxed text-pretty">
              The demo shows every turn from the inside: the rules the rep was given, each action it
              tried, and what the guard allowed or stopped.
            </p>
            <Button asChild size="lg">
              <a href="/demo">
                Open the demo <ArrowRightIcon />
              </a>
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="text-muted-foreground mx-auto flex max-w-6xl flex-wrap justify-between gap-2 px-4 py-8 text-sm sm:px-6">
          <p>repkit · the AI harness for your business · MIT licence</p>
          <p>Loop Sneakers and Brightside Dental are made-up companies used as demos.</p>
        </div>
      </footer>
    </div>
  )
}
