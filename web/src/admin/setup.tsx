// The setup: a few questions that build a rep from blank. The answers are sent
// together at the end, so the rep is rebuilt once and never left half-made.

import { useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  ExternalLinkIcon,
  TriangleAlertIcon,
  UploadIcon,
} from 'lucide-react'

import type { SetupAnswers, Tone } from '@/admin/api'
import { Field, ROWS, Section, StackField, Toggle } from '@/admin/fields'
import { Snippet } from '@/admin/more'
import type { SectionProps } from '@/admin/sections'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { forgetConversation } from '@/lib/conversation'
import { cn } from '@/lib/utils'

const STEPS = ['Your business', 'What it knows', 'How it sounds', 'How it looks'] as const

const TONES: [Tone, string, string][] = [
  ['friendly', 'Friendly', 'Warm, like a colleague glad to help'],
  ['professional', 'Professional', 'Polite and precise, never casual'],
  ['playful', 'Playful', 'Light, without being silly'],
  ['direct', 'Short and direct', 'The answer first, then one question'],
]

const ROLES = ['customer support', 'sales', 'front desk', 'bookings', 'orders and delivery']

const KNOWLEDGE_EXAMPLE = `## Opening hours
We're open Monday to Saturday, 10 am to 8 pm.

## Delivery
We deliver across the city for ₹150. Orders before 2 pm arrive the same day.

## Returns
Unused items can be returned within 7 days for a full refund.`

/** Below this, the rep has too little to answer from to be worth trying. */
const MIN_KNOWLEDGE = 40

function blankAnswers(): SetupAnswers {
  return {
    company: '',
    rep: '',
    role: 'customer support',
    covers: '',
    knowledge: '',
    tone: ['friendly'],
    emoji: false,
    greeting: '',
    suggestions: [],
    accent: 'auto',
  }
}

function Step({
  number,
  title,
  description,
  children,
}: {
  number: number
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          Step {number} of {STEPS.length}
        </p>
        <CardTitle className="text-xl">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className={ROWS}>{children}</CardContent>
    </Card>
  )
}

function Progress({ step }: { step: number }) {
  return (
    <ol className="grid grid-cols-4 gap-2" aria-label="Setup steps">
      {STEPS.map((label, index) => (
        <li key={label} className="flex flex-col gap-2">
          <span
            className={cn(
              'h-1 rounded-full transition-colors',
              index <= step ? 'bg-foreground' : 'bg-muted',
            )}
          />
          <span
            className={cn(
              'hidden text-xs sm:block',
              index === step ? 'text-foreground font-medium' : 'text-muted-foreground',
            )}
            aria-current={index === step ? 'step' : undefined}
          >
            {label}
          </span>
        </li>
      ))}
    </ol>
  )
}

function Done({ name, go }: { name: string; go: (section: string) => void }) {
  const origin = window.location.origin
  return (
    <Section
      title={`${name} is ready`}
      description="Try it below, then put it on your website with one line. Everything you set up is saved as plain files on this server."
    >
      {/* Beside the dashboard's own live preview the chat is not shown twice. */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px] xl:grid-cols-1">
        <div className="flex min-w-0 flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Put it on your website</CardTitle>
              <CardDescription>Paste this before the closing body tag of any page.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Snippet code={`<script src="${origin}/widget.js" defer></script>`} />
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="outline" size="sm">
                  <a href="/example" target="_blank" rel="noreferrer">
                    See it on an example site <ExternalLinkIcon />
                  </a>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <a href="/demo" target="_blank" rel="noreferrer">
                    Open the chat with the inspector <ExternalLinkIcon />
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Make it yours</CardTitle>
              <CardDescription>
                Each of these is a screen in the sidebar. Changes go live as soon as you save.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {[
                ['knowledge', 'Add more knowledge'],
                ['rules', 'Set rules it must follow'],
                ['handoff', 'Choose when a person takes over'],
                ['test', 'Run the fake customers'],
              ].map(([key, label]) => (
                <Button key={key} variant="secondary" size="sm" onClick={() => go(key)}>
                  {label} <ArrowRightIcon />
                </Button>
              ))}
            </CardContent>
          </Card>
        </div>
        <Card className="overflow-hidden p-0 xl:hidden">
          <iframe title="Your assistant" src="/chat?nopacing&inline" className="h-[520px] w-full" />
        </Card>
      </div>
    </Section>
  )
}

export function SetupSection({ pack, api, commit, go }: SectionProps) {
  const fresh = pack.setup_pending
  const [answers, setAnswers] = useState<SetupAnswers>(() =>
    fresh
      ? blankAnswers()
      : {
          ...blankAnswers(),
          company: pack.persona.company,
          rep: pack.persona.name,
          role: pack.persona.role,
          covers: pack.scope.covers,
          emoji: pack.persona.emoji,
          greeting: pack.widget.greeting,
          suggestions: pack.widget.suggestions,
          accent: pack.widget.accent,
        },
  )
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const file = useRef<HTMLInputElement>(null)
  // Bumped on each upload: the logo keeps its file name, so the browser must be told it changed.
  const [logoVersion, setLogoVersion] = useState(0)

  const set = (changes: Partial<SetupAnswers>) => setAnswers((now) => ({ ...now, ...changes }))
  const company = answers.company.trim() || 'your company'
  const rep = answers.rep.trim() || 'your assistant'

  const ready = [
    Boolean(answers.company.trim() && answers.rep.trim() && answers.role.trim()),
    answers.knowledge.trim().length >= MIN_KNOWLEDGE,
    true,
    true,
  ]
  const missing = [
    'Give the business and the assistant a name.',
    `Write at least a few lines ${rep} can answer from.`,
    '',
    '',
  ]

  const finish = async () => {
    setBusy(true)
    const saved = await commit(`${rep} is ready`, async () => {
      await api.setup(answers)
      // A chat open from before would carry on with the old rep's greeting.
      forgetConversation()
    })
    setBusy(false)
    if (saved) setDone(true)
  }

  if (done) return <Done name={rep} go={go} />

  return (
    <Section
      title={fresh ? 'Set up your assistant' : 'Run the setup again'}
      description={
        fresh
          ? 'Four short steps. At the end your assistant is live, with a chat to try and one line to put it on your website.'
          : 'This builds the assistant again from your answers.'
      }
    >
      {!fresh && (
        <Alert>
          <TriangleAlertIcon />
          <AlertTitle>This starts the assistant over</AlertTitle>
          <AlertDescription>
            Its knowledge, rules, examples and fake customers are replaced by the setup's. The logo
            is kept. To change one thing, use its own screen in the sidebar instead.
          </AlertDescription>
        </Alert>
      )}
      <Progress step={step} />

      {step === 0 && (
        <Step
          number={1}
          title="Your business"
          description="Who the assistant works for, and what it is there to do."
        >
          <Field label="Business name" htmlFor="setup-company">
            <Input
              id="setup-company"
              placeholder="Bloom Florists"
              value={answers.company}
              onChange={(e) => set({ company: e.target.value })}
            />
          </Field>
          <Field
            label="Assistant's name"
            htmlFor="setup-rep"
            hint="A first name. It always says it is an AI when asked."
          >
            <Input
              id="setup-rep"
              placeholder="Ivy"
              value={answers.rep}
              onChange={(e) => set({ rep: e.target.value })}
            />
          </Field>
          <Field label="Its job" htmlFor="setup-role" hint="Pick one or type your own.">
            <Input
              id="setup-role"
              list="setup-roles"
              value={answers.role}
              onChange={(e) => set({ role: e.target.value })}
            />
            <datalist id="setup-roles">
              {ROLES.map((role) => (
                <option key={role} value={role} />
              ))}
            </datalist>
          </Field>
          <Field
            label="What it helps with"
            htmlFor="setup-covers"
            hint="One or two sentences. Anything else, it politely turns away."
          >
            <Textarea
              id="setup-covers"
              rows={3}
              placeholder={`${answers.company.trim() || 'Your company'} only: our products, prices, delivery and taking orders.`}
              value={answers.covers}
              onChange={(e) => set({ covers: e.target.value })}
            />
          </Field>
        </Step>
      )}

      {step === 1 && (
        <Step
          number={2}
          title="What it knows"
          description={`${rep} answers only from this, and says so when something is not here. Paste what your team tells customers: prices, hours, delivery, returns, FAQs.`}
        >
          <div className="flex flex-col gap-3">
            <Textarea
              id="setup-knowledge"
              aria-label="What the assistant knows"
              rows={14}
              className="font-mono text-xs leading-relaxed"
              placeholder={KNOWLEDGE_EXAMPLE}
              value={answers.knowledge}
              onChange={(e) => set({ knowledge: e.target.value })}
            />
            <p className="text-muted-foreground text-sm">
              Start each subject with a line like <code>## Delivery</code>. Each one is looked up on
              its own. Every price and time it may state has to be written here: a figure from
              anywhere else is treated as made up and is never sent.
            </p>
            {!answers.knowledge.trim() && (
              <Button
                variant="outline"
                size="sm"
                className="self-start"
                onClick={() => set({ knowledge: KNOWLEDGE_EXAMPLE })}
              >
                Start from the example
              </Button>
            )}
          </div>
        </Step>
      )}

      {step === 2 && (
        <Step
          number={3}
          title="How it sounds"
          description="The tone it writes in and the first thing customers see."
        >
          <div className="flex flex-col gap-3 py-5 first:pt-0">
            <p className="text-sm font-medium">Tone</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {TONES.map(([key, label, hint]) => {
                const on = answers.tone.includes(key)
                return (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={on}
                    onClick={() =>
                      set({
                        tone: on ? answers.tone.filter((t) => t !== key) : [...answers.tone, key],
                      })
                    }
                    className={cn(
                      'flex items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                      on ? 'border-foreground bg-accent' : 'hover:bg-accent/50',
                    )}
                  >
                    <span
                      className={cn(
                        'mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border',
                        on && 'bg-foreground text-background border-foreground',
                      )}
                    >
                      {on && <CheckIcon className="size-3" />}
                    </span>
                    <span className="flex flex-col gap-0.5">
                      <span className="text-sm font-medium">{label}</span>
                      <span className="text-muted-foreground text-xs">{hint}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
          <Toggle
            id="setup-emoji"
            label="Emoji"
            hint="When off, any emoji it writes are removed before sending."
            checked={answers.emoji}
            onChange={(emoji) => set({ emoji })}
          />
          <div className="py-5">
            <StackField
              label="Greeting"
              htmlFor="setup-greeting"
              hint="Leave empty to use the one shown."
            >
              <Input
                id="setup-greeting"
                placeholder={`Hi, I'm ${rep} from ${company}. How can I help?`}
                value={answers.greeting}
                onChange={(e) => set({ greeting: e.target.value })}
              />
            </StackField>
          </div>
          <div className="pt-5">
            <StackField
              label="Suggested first questions"
              htmlFor="setup-suggestion-0"
              hint="Up to four. Customers tap one instead of typing."
            >
              <div className="grid gap-2 sm:grid-cols-2">
                {[0, 1, 2, 3].map((index) => (
                  <Input
                    key={index}
                    id={`setup-suggestion-${index}`}
                    aria-label={`Suggestion ${index + 1}`}
                    placeholder={index === 0 ? 'Do you deliver today?' : ''}
                    value={answers.suggestions[index] ?? ''}
                    onChange={(e) => {
                      const length = Math.max(answers.suggestions.length, index + 1)
                      const next = Array.from({ length }, (_, at) =>
                        at === index ? e.target.value : (answers.suggestions[at] ?? ''),
                      )
                      set({ suggestions: next })
                    }}
                  />
                ))}
              </div>
            </StackField>
          </div>
        </Step>
      )}

      {step === 3 && (
        <Step
          number={4}
          title="How it looks"
          description="The chat matches your brand. More options are on the Brand screen later."
        >
          <Field label="Logo" hint="PNG, JPG, WebP or SVG, under 500 KB. Square works best.">
            <div className="flex items-center gap-3">
              <div className="bg-muted ring-border flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-full ring-1">
                {pack.widget.logo ? (
                  <img
                    src={`/brand/logo?v=${encodeURIComponent(pack.widget.logo)}-${logoVersion}`}
                    alt="Current logo"
                    className="size-full object-cover"
                  />
                ) : (
                  <span className="font-medium">{company.charAt(0).toUpperCase()}</span>
                )}
              </div>
              <input
                ref={file}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                className="hidden"
                onChange={(e) => {
                  const chosen = e.target.files?.[0]
                  if (chosen)
                    commit('Logo uploaded', () => api.uploadLogo(chosen)).then(() =>
                      setLogoVersion((version) => version + 1),
                    )
                  e.target.value = ''
                }}
              />
              <Button variant="outline" size="sm" onClick={() => file.current?.click()}>
                <UploadIcon /> Upload
              </Button>
            </div>
          </Field>
          <Field
            label="Brand colour"
            htmlFor="setup-accent"
            hint="For the launcher and the customer's messages. Black and white follows the site's theme."
          >
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant={answers.accent === 'auto' ? 'default' : 'outline'}
                aria-pressed={answers.accent === 'auto'}
                onClick={() => set({ accent: answers.accent === 'auto' ? '#2563eb' : 'auto' })}
              >
                Black and white
              </Button>
              {answers.accent !== 'auto' && (
                <>
                  <input
                    type="color"
                    aria-label="Pick the brand colour"
                    value={answers.accent}
                    onChange={(e) => set({ accent: e.target.value })}
                    className="h-9 w-12 cursor-pointer rounded-md border bg-transparent p-1"
                  />
                  <Input
                    id="setup-accent"
                    value={answers.accent}
                    onChange={(e) => set({ accent: e.target.value })}
                    className="font-mono"
                  />
                </>
              )}
            </div>
          </Field>
        </Step>
      )}

      <div className="flex items-center justify-between gap-3">
        <Button
          variant="ghost"
          onClick={() => setStep((now) => now - 1)}
          disabled={step === 0 || busy}
        >
          <ArrowLeftIcon /> Back
        </Button>
        <div className="flex items-center gap-3">
          {!ready[step] && (
            <span className="text-muted-foreground hidden text-sm sm:inline">{missing[step]}</span>
          )}
          {step < STEPS.length - 1 ? (
            <Button onClick={() => setStep((now) => now + 1)} disabled={!ready[step]}>
              Next <ArrowRightIcon />
            </Button>
          ) : (
            <Button onClick={finish} disabled={busy || !ready.every(Boolean)}>
              {busy ? 'Building…' : `Create ${rep}`}
            </Button>
          )}
        </div>
      </div>
    </Section>
  )
}
