// The dashboard's editing screens. Each one edits a copy of part of the pack
// and saves it through the admin API, which validates it and reloads the rep.

import { useEffect, useRef, useState } from 'react'
import { PlusIcon, Trash2Icon, UploadIcon } from 'lucide-react'

import type { AdminApi, Handoff, Pack, Persona, Rule, Scope, Widget } from '@/admin/api'
import { Field, Lines, Section, Toggle } from '@/admin/fields'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

export type SectionProps = {
  pack: Pack
  api: AdminApi
  /** Run a save, show the outcome, then refresh the pack and the preview. */
  commit: (label: string, work: () => Promise<unknown>) => Promise<boolean>
}

function SaveButton({ dirty, onSave }: { dirty: boolean; onSave: () => void }) {
  return (
    <Button onClick={onSave} disabled={!dirty}>
      {dirty ? 'Save changes' : 'Saved'}
    </Button>
  )
}

/** A local, editable copy of one part of the pack. */
function useDraft<T>(source: T) {
  const [draft, setDraft] = useState(source)
  const [dirty, setDirty] = useState(false)
  useEffect(() => {
    setDraft(source)
    setDirty(false)
  }, [source])
  const set = (changes: Partial<T>) => {
    setDraft((current) => ({ ...current, ...changes }))
    setDirty(true)
  }
  return { draft, set, dirty }
}

function Choice<T extends string>({
  id,
  value,
  options,
  onChange,
}: {
  id: string
  value: T
  options: readonly (readonly [T, string])[]
  onChange: (next: T) => void
}) {
  return (
    <Select value={value} onValueChange={(next) => onChange(next as T)}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map(([key, label]) => (
          <SelectItem key={key} value={key}>
            {label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

const ROLES = ['customer support', 'sales', 'application intake', 'front desk', 'bookings']

// -- Brand -------------------------------------------------------------------

export function BrandSection({ pack, api, commit }: SectionProps) {
  const widget = useDraft<Widget>(pack.widget)
  const persona = useDraft<Persona>(pack.persona)
  const file = useRef<HTMLInputElement>(null)
  const dirty = widget.dirty || persona.dirty
  const w = widget.draft

  const save = () =>
    commit('Brand saved', async () => {
      if (persona.dirty) await api.saveSection('persona', persona.draft)
      if (widget.dirty) await api.saveSection('widget', widget.draft)
    })

  return (
    <Section
      title="Brand"
      description="How the rep is named and how the chat looks on your site. Changes show in the preview as soon as you save."
      actions={<SaveButton dirty={dirty} onSave={save} />}
    >
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Rep's name" htmlFor="rep-name">
            <Input
              id="rep-name"
              value={persona.draft.name}
              onChange={(e) => persona.set({ name: e.target.value })}
            />
          </Field>
          <Field label="Company" htmlFor="company">
            <Input
              id="company"
              value={persona.draft.company}
              onChange={(e) => persona.set({ company: e.target.value })}
            />
          </Field>
          <Field
            label="What the rep does"
            htmlFor="role"
            hint="Pick one or type your own. The same harness runs support, sales and intake."
          >
            <Input
              id="role"
              list="roles"
              value={persona.draft.role}
              onChange={(e) => persona.set({ role: e.target.value })}
            />
            <datalist id="roles">
              {ROLES.map((role) => (
                <option key={role} value={role} />
              ))}
            </datalist>
          </Field>
          <Field label="Panel title" htmlFor="title" hint="Shown at the top of the chat.">
            <Input id="title" value={w.title} onChange={(e) => widget.set({ title: e.target.value })} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Logo and colour</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Logo" hint="PNG, JPG, WebP or SVG, under 500 KB. Square works best.">
            <div className="flex items-center gap-3">
              <div className="bg-muted ring-border size-12 shrink-0 overflow-hidden rounded-full ring-1">
                {pack.widget.logo && (
                  <img
                    src={`/brand/logo?v=${encodeURIComponent(pack.widget.logo)}-${Date.now()}`}
                    alt="Current logo"
                    className="size-full object-cover"
                  />
                )}
              </div>
              <input
                ref={file}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                className="hidden"
                onChange={(e) => {
                  const chosen = e.target.files?.[0]
                  if (chosen) commit('Logo updated', () => api.uploadLogo(chosen))
                  e.target.value = ''
                }}
              />
              <Button variant="outline" size="sm" onClick={() => file.current?.click()}>
                <UploadIcon /> Upload
              </Button>
              {pack.widget.logo && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => commit('Logo removed', () => api.deleteLogo())}
                >
                  Remove
                </Button>
              )}
            </div>
          </Field>
          <Field label="Brand colour" htmlFor="accent" hint="Used for the launcher and the customer's messages.">
            <div className="flex items-center gap-2">
              <input
                type="color"
                aria-label="Pick the brand colour"
                value={w.accent}
                onChange={(e) => widget.set({ accent: e.target.value })}
                className="h-9 w-12 cursor-pointer rounded-md border bg-transparent p-1"
              />
              <Input
                id="accent"
                value={w.accent}
                onChange={(e) => widget.set({ accent: e.target.value })}
                className="font-mono"
              />
            </div>
          </Field>
          <Field label="Theme" htmlFor="theme">
            <Choice
              id="theme"
              value={w.theme}
              onChange={(theme) => widget.set({ theme })}
              options={[
                ['auto', "Follow the visitor's device"],
                ['light', 'Always light'],
                ['dark', 'Always dark'],
              ]}
            />
          </Field>
          <Field label="Header" htmlFor="header">
            <Choice
              id="header"
              value={w.header}
              onChange={(header) => widget.set({ header })}
              options={[
                ['plain', 'Neutral'],
                ['accent', 'Filled with the brand colour'],
              ]}
            />
          </Field>
          <Field label="Corners" htmlFor="corners">
            <Choice
              id="corners"
              value={w.corners}
              onChange={(corners) => widget.set({ corners })}
              options={[
                ['sharp', 'Sharp'],
                ['soft', 'Soft'],
                ['round', 'Round'],
              ]}
            />
          </Field>
          <Field label="Typeface" htmlFor="font">
            <Choice
              id="font"
              value={w.font}
              onChange={(font) => widget.set({ font })}
              options={[
                ['system', 'Sans'],
                ['serif', 'Serif'],
                ['rounded', 'Rounded'],
                ['mono', 'Monospace'],
              ]}
            />
          </Field>
          <Field label="Launcher position" htmlFor="position">
            <Choice
              id="position"
              value={w.position}
              onChange={(position) => widget.set({ position })}
              options={[
                ['right', 'Bottom right'],
                ['left', 'Bottom left'],
              ]}
            />
          </Field>
          <Field label="Launcher label" htmlFor="launcher">
            <Input
              id="launcher"
              value={w.launcher_label}
              onChange={(e) => widget.set({ launcher_label: e.target.value })}
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Opening</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <Field label="Greeting" htmlFor="greeting" hint="The first thing a visitor reads.">
            <Textarea
              id="greeting"
              rows={2}
              value={w.greeting}
              onChange={(e) => widget.set({ greeting: e.target.value })}
            />
          </Field>
          <Field label="Suggested questions" htmlFor="suggestions" hint="Up to four, one per line.">
            <Lines
              id="suggestions"
              key={w.suggestions.join('|')}
              value={w.suggestions}
              onChange={(suggestions) => widget.set({ suggestions: suggestions.slice(0, 4) })}
            />
          </Field>
        </CardContent>
      </Card>
    </Section>
  )
}

// -- Voice -------------------------------------------------------------------

export function VoiceSection({ pack, api, commit }: SectionProps) {
  const { draft, set, dirty } = useDraft<Persona>(pack.persona)
  return (
    <Section
      title="Voice"
      description="How the rep sounds. The traits and the example chats go to the model; the banned phrases are removed in code even if the model writes them."
      actions={
        <SaveButton
          dirty={dirty}
          onSave={() => commit('Voice saved', () => api.saveSection('persona', draft))}
        />
      }
    >
      <Card>
        <CardContent className="grid gap-4">
          <Field label="How they talk" htmlFor="voice" hint="One trait per line, as you would brief a new hire.">
            <Lines id="voice" key={pack.persona.voice.join('|')} value={draft.voice} onChange={(voice) => set({ voice })} rows={5} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Language" htmlFor="language">
              <Input id="language" value={draft.language} onChange={(e) => set({ language: e.target.value })} />
            </Field>
            <Field label="Sentences per message" htmlFor="sentences" hint="Longer replies are split into more messages.">
              <Input
                id="sentences"
                type="number"
                min={1}
                max={6}
                value={draft.max_sentences}
                onChange={(e) => set({ max_sentences: Math.max(1, Number(e.target.value) || 1) })}
              />
            </Field>
          </div>
          <Toggle
            id="emoji"
            label="Allow emoji"
            hint="When off, emoji are stripped from every reply."
            checked={draft.emoji}
            onChange={(emoji) => set({ emoji })}
          />
          <Field label="Phrases the rep never uses" htmlFor="banned" hint="Stock phrases that make it sound like a chatbot. One per line.">
            <Lines id="banned" key={pack.persona.banned_phrases.join('|')} value={draft.banned_phrases} onChange={(banned_phrases) => set({ banned_phrases })} rows={5} />
          </Field>
          <Field
            label="What it says when asked if it is a person"
            htmlFor="disclosure"
            hint="The rep may sound human. It always answers this honestly, with this line."
          >
            <Textarea id="disclosure" rows={2} value={draft.disclosure} onChange={(e) => set({ disclosure: e.target.value })} />
          </Field>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Example chats</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm">
          {pack.examples.length} real conversation{pack.examples.length === 1 ? '' : 's'} in the
          pack's <code className="text-foreground">examples/</code> folder set the rhythm:{' '}
          {pack.examples.map((chat) => chat.title).join(', ') || 'none yet'}.
        </CardContent>
      </Card>
    </Section>
  )
}

// -- Scope -------------------------------------------------------------------

const REFUSALS = [
  ['math', 'Sums and maths problems', 'Sums about your own prices are still allowed.'],
  ['coding', 'Writing or fixing code', ''],
  ['writing', 'Poems, essays, jokes, homework', ''],
  ['trivia', 'General knowledge and translation', ''],
] as const

export function ScopeSection({ pack, api, commit }: SectionProps) {
  const { draft, set, dirty } = useDraft<Scope>(pack.scope)
  const toggle = (kind: Scope['refuse'][number], on: boolean) =>
    set({ refuse: on ? [...draft.refuse, kind] : draft.refuse.filter((k) => k !== kind) })
  return (
    <Section
      title="Scope"
      description="What the rep is for, and what it does with everything else. These checks run in code: an off-topic message is answered with your line and never reaches the model."
      actions={<SaveButton dirty={dirty} onSave={() => commit('Scope saved', () => api.saveSection('scope', draft))} />}
    >
      <Card>
        <CardContent className="grid gap-4">
          <Field label="What the rep helps with" htmlFor="covers" hint="Shown to the model as the whole of its job.">
            <Textarea id="covers" rows={3} value={draft.covers} onChange={(e) => set({ covers: e.target.value })} />
          </Field>
          <Field label="Reply to anything off topic" htmlFor="off-topic">
            <Textarea id="off-topic" rows={2} value={draft.off_topic_reply} onChange={(e) => set({ off_topic_reply: e.target.value })} />
          </Field>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Always turned away</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {REFUSALS.map(([kind, label, hint]) => (
            <Toggle
              key={kind}
              id={`refuse-${kind}`}
              label={label}
              hint={hint || undefined}
              checked={draft.refuse.includes(kind)}
              onChange={(on) => toggle(kind, on)}
            />
          ))}
          <div className="sm:col-span-2">
            <Toggle
              id="strict"
              label="Strict: only answer what the pack covers"
              hint="Turns away any message that matches none of your rules or knowledge. Greetings and answers to the rep's own questions still pass."
              checked={draft.strict}
              onChange={(strict) => set({ strict })}
            />
          </div>
          <div className="sm:col-span-2">
            <Field label="Also turn away" htmlFor="also-refuse" hint="Extra patterns for your business, one regular expression per line. Example: \bcompetitor\b">
              <Lines id="also-refuse" key={pack.scope.also_refuse.join('|')} value={draft.also_refuse} onChange={(also_refuse) => set({ also_refuse })} rows={3} mono />
            </Field>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Made-up facts</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <Toggle
            id="ground"
            label="Block figures the rep was never given"
            hint="A reply stating a price, date or quantity that is in no rule, knowledge file or tool result is replaced before the customer sees it."
            checked={draft.ground_numbers}
            onChange={(ground_numbers) => set({ ground_numbers })}
          />
          <Field label="What it says instead" htmlFor="unsure">
            <Textarea id="unsure" rows={2} value={draft.unsure_reply} onChange={(e) => set({ unsure_reply: e.target.value })} />
          </Field>
        </CardContent>
      </Card>
    </Section>
  )
}

// -- Knowledge ---------------------------------------------------------------

export function KnowledgeSection({ pack, api, commit }: SectionProps) {
  const [open, setOpen] = useState(pack.knowledge[0]?.source ?? '')
  const [text, setText] = useState(pack.knowledge[0]?.text ?? '')
  const [dirty, setDirty] = useState(false)
  const [newName, setNewName] = useState('')

  const choose = (source: string) => {
    setOpen(source)
    setText(pack.knowledge.find((doc) => doc.source === source)?.text ?? '')
    setDirty(false)
  }
  const create = () => {
    const name = newName.trim().replace(/\.md$/, '').replace(/[^A-Za-z0-9_-]+/g, '-') + '.md'
    if (name === '.md') return
    setNewName('')
    setOpen(name)
    setText(`# ${name.replace(/\.md$/, '').replace(/-/g, ' ')}\n\n`)
    setDirty(true)
  }

  return (
    <Section
      title="Knowledge"
      description="The facts the rep answers from. Each message is matched to the few sections it needs, so write under clear headings. A fact that is not here is one the rep should not state."
      actions={
        <SaveButton
          dirty={dirty}
          onSave={async () => {
            if (await commit(`${open} saved`, () => api.saveKnowledge(open, text))) setDirty(false)
          }}
        />
      }
    >
      <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
        <div className="flex flex-col gap-2">
          {pack.knowledge.map((doc) => (
            <Button
              key={doc.source}
              variant={doc.source === open ? 'secondary' : 'ghost'}
              className="justify-start font-mono text-xs"
              onClick={() => choose(doc.source)}
            >
              {doc.source}
            </Button>
          ))}
          <div className="mt-2 flex gap-1.5">
            <Input
              aria-label="New file name"
              placeholder="new-topic"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && create()}
              className="h-8 font-mono text-xs"
            />
            <Button variant="outline" size="icon" className="size-8 shrink-0" onClick={create}>
              <PlusIcon />
              <span className="sr-only">Add knowledge file</span>
            </Button>
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          {open ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <code className="text-sm">{open}</code>
                {pack.knowledge.some((doc) => doc.source === open) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={async () => {
                      if (await commit(`${open} deleted`, () => api.deleteKnowledge(open))) {
                        setOpen('')
                        setText('')
                      }
                    }}
                  >
                    <Trash2Icon /> Delete
                  </Button>
                )}
              </div>
              <Textarea
                aria-label={`Contents of ${open}`}
                value={text}
                onChange={(e) => {
                  setText(e.target.value)
                  setDirty(true)
                }}
                className="min-h-[420px] font-mono text-[13px] leading-relaxed"
              />
            </>
          ) : (
            <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              Choose a file, or add one, to give the rep something to answer from.
            </p>
          )}
        </div>
      </div>
    </Section>
  )
}

// -- Rules -------------------------------------------------------------------

function ruleKind(rule: Rule) {
  if (rule.tool && (rule.limits.length > 0 || rule.forbid)) return 'Enforced on actions'
  if (rule.never_say.length > 0) return 'Enforced on replies'
  return 'Guidance'
}

export function RulesSection({ pack, api, commit }: SectionProps) {
  const [rules, setRules] = useState<Rule[]>(pack.policies)
  const [dirty, setDirty] = useState(false)
  useEffect(() => {
    setRules(pack.policies)
    setDirty(false)
  }, [pack.policies])

  const change = (index: number, changes: Partial<Rule>) => {
    setRules((current) => current.map((rule, i) => (i === index ? { ...rule, ...changes } : rule)))
    setDirty(true)
  }
  const add = () => {
    setRules((current) => [
      ...current,
      {
        id: `rule-${current.length + 1}`,
        text: '',
        tool: null,
        limits: [],
        forbid: false,
        on_violation: 'block',
        topics: [],
        never_say: [],
        safe_reply: "I can't do that one, sorry.",
      },
    ])
    setDirty(true)
  }

  return (
    <Section
      title="Rules"
      description="What the rep may promise and do. The wording is shown to the model. Limits on actions and forbidden phrases are checked in code, so they hold even if the model is talked out of them."
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={add}>
            <PlusIcon /> Add rule
          </Button>
          <SaveButton dirty={dirty} onSave={() => commit('Rules saved', () => api.saveSection('policies', rules))} />
        </div>
      }
    >
      {rules.map((rule, index) => (
        <Card key={index}>
          <CardHeader className="flex flex-row items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <Input
                aria-label="Rule id"
                value={rule.id}
                onChange={(e) => change(index, { id: e.target.value })}
                className="h-8 w-48 font-mono text-xs"
              />
              <Badge variant={ruleKind(rule) === 'Guidance' ? 'outline' : 'default'}>{ruleKind(rule)}</Badge>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground size-8"
              onClick={() => {
                setRules((current) => current.filter((_, i) => i !== index))
                setDirty(true)
              }}
            >
              <Trash2Icon />
              <span className="sr-only">Delete rule {rule.id}</span>
            </Button>
          </CardHeader>
          <CardContent className="grid gap-4">
            <Field label="The rule, in plain words" htmlFor={`text-${index}`}>
              <Textarea id={`text-${index}`} rows={2} value={rule.text} onChange={(e) => change(index, { text: e.target.value })} />
            </Field>
            <Field label="Shown when a message mentions" htmlFor={`topics-${index}`} hint="Comma-separated words. Leave empty to show the rule on every message.">
              <Input
                id={`topics-${index}`}
                defaultValue={rule.topics.join(', ')}
                onBlur={(e) => change(index, { topics: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) })}
              />
            </Field>
            {rule.tool && (
              <div className="bg-muted/50 grid gap-3 rounded-lg p-3 sm:grid-cols-2">
                <p className="text-sm sm:col-span-2">
                  Checked in code on <code>{rule.tool}</code>
                  {rule.forbid && ': the rep may never use it.'}
                </p>
                {rule.limits.map((limit, li) => (
                  <Field
                    key={li}
                    label={limit.allowed ? `Allowed values for ${limit.field}` : `Maximum ${limit.field}`}
                    htmlFor={`limit-${index}-${li}`}
                  >
                    {limit.allowed ? (
                      <Input
                        id={`limit-${index}-${li}`}
                        defaultValue={limit.allowed.join(', ')}
                        onBlur={(e) => {
                          const allowed = e.target.value.split(',').map((v) => v.trim()).filter(Boolean)
                          change(index, { limits: rule.limits.map((l, i) => (i === li ? { ...l, allowed } : l)) })
                        }}
                      />
                    ) : (
                      <Input
                        id={`limit-${index}-${li}`}
                        type="number"
                        value={limit.max ?? ''}
                        onChange={(e) => {
                          const max = e.target.value === '' ? null : Number(e.target.value)
                          change(index, { limits: rule.limits.map((l, i) => (i === li ? { ...l, max } : l)) })
                        }}
                      />
                    )}
                  </Field>
                ))}
                <Field label="When broken" htmlFor={`violation-${index}`}>
                  <Choice
                    id={`violation-${index}`}
                    value={rule.on_violation}
                    onChange={(on_violation) => change(index, { on_violation })}
                    options={[
                      ['block', 'Refuse the action'],
                      ['handoff', 'Hand to a human'],
                    ]}
                  />
                </Field>
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="The rep must never say" htmlFor={`never-${index}`} hint="Regular expressions, one per line.">
                <Lines id={`never-${index}`} key={rule.never_say.join('|')} value={rule.never_say} onChange={(never_say) => change(index, { never_say })} rows={3} mono />
              </Field>
              <Field label="Sent instead" htmlFor={`safe-${index}`}>
                <Textarea id={`safe-${index}`} rows={3} value={rule.safe_reply} onChange={(e) => change(index, { safe_reply: e.target.value })} />
              </Field>
            </div>
          </CardContent>
        </Card>
      ))}
      <Card>
        <CardHeader>
          <CardTitle>Actions the rep can take</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm">
          {pack.tools.map((tool) => (
            <div key={tool.name} className="flex flex-col gap-0.5">
              <code>{tool.name}</code>
              <span className="text-muted-foreground">{tool.description}</span>
            </div>
          ))}
          <p className="text-muted-foreground mt-2 text-xs">
            Actions run your own code, so they are defined in the pack's tools.yaml and handlers.py.
          </p>
        </CardContent>
      </Card>
    </Section>
  )
}

// -- Handoff -----------------------------------------------------------------

export function HandoffSection({ pack, api, commit }: SectionProps) {
  const { draft, set, dirty } = useDraft<Handoff>(pack.handoff)
  return (
    <Section
      title="Handoff"
      description="When a person takes over. These are checked on the customer's own words, before the model sees them."
      actions={<SaveButton dirty={dirty} onSave={() => commit('Handoff saved', () => api.saveSection('handoff', draft))} />}
    >
      <Card>
        <CardContent className="grid gap-4">
          <Field label="Hand off at once when a customer says" htmlFor="phrases" hint="One phrase per line.">
            <Lines id="phrases" key={pack.handoff.phrases.join('|')} value={draft.phrases} onChange={(phrases) => set({ phrases })} rows={6} />
          </Field>
          <Toggle
            id="on-request"
            label="Hand off when a customer asks for a person"
            checked={draft.on_request}
            onChange={(on_request) => set({ on_request })}
          />
          <Field label="Hand off after this many blocked actions" htmlFor="blocks">
            <Input
              id="blocks"
              type="number"
              min={1}
              value={draft.max_guard_blocks}
              onChange={(e) => set({ max_guard_blocks: Math.max(1, Number(e.target.value) || 1) })}
              className="w-32"
            />
          </Field>
          <Field label="What the rep says as it hands over" htmlFor="handoff-message">
            <Textarea id="handoff-message" rows={2} value={draft.message} onChange={(e) => set({ message: e.target.value })} />
          </Field>
        </CardContent>
      </Card>
    </Section>
  )
}
