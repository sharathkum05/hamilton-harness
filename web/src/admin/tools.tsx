// The Tools screen: what the rep can do in a company's systems. Tools written
// in Python are shown as they are; tools that call the company's own web API
// are set up here, with no code, and any tool can be tried with sample inputs.

import { useEffect, useState } from 'react'
import { PlayIcon, PlusIcon, Trash2Icon } from 'lucide-react'

import type { HttpCall, JsonSchema, Tool } from '@/admin/api'
import { Field, ROWS, Section, StackField } from '@/admin/fields'
import type { SectionProps } from '@/admin/sections'
import { Choice, SaveButton } from '@/admin/sections'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

type InputField = {
  name: string
  type: 'text' | 'number' | 'choice'
  description: string
  required: boolean
  choices: string
}

type ApiTool = {
  name: string
  description: string
  http: HttpCall
  fields: InputField[]
  remember: Record<string, string>
}

const TYPES = [
  ['text', 'Text'],
  ['number', 'Number'],
  ['choice', 'One of a list'],
] as const

const METHODS = [
  ['GET', 'GET: look something up'],
  ['POST', 'POST: send something'],
] as const

/** The simple input forms a person can set up, read back from a JSON Schema. */
function fieldsOf(schema: JsonSchema): InputField[] {
  const required = new Set(schema.required ?? [])
  return Object.entries(schema.properties ?? {}).map(([name, property]) => ({
    name,
    type: property.enum
      ? 'choice'
      : ['number', 'integer'].includes(property.type ?? '')
        ? 'number'
        : 'text',
    description: property.description ?? '',
    required: required.has(name),
    choices: (property.enum ?? []).join(', '),
  }))
}

function schemaOf(fields: InputField[]): JsonSchema {
  const properties: JsonSchema['properties'] = {}
  for (const field of fields) {
    const property: { type: string; description?: string; enum?: string[] } = {
      type: field.type === 'number' ? 'number' : 'string',
    }
    if (field.description.trim()) property.description = field.description.trim()
    if (field.type === 'choice') {
      property.enum = field.choices
        .split(',')
        .map((choice) => choice.trim())
        .filter(Boolean)
    }
    properties[field.name.trim()] = property
  }
  return {
    type: 'object',
    properties,
    required: fields.filter((field) => field.required).map((field) => field.name.trim()),
    additionalProperties: false,
  }
}

function toApiTool(tool: Tool): ApiTool {
  return {
    name: tool.name,
    description: tool.description,
    http: tool.http ?? { method: 'GET', url: '', headers: {} },
    fields: fieldsOf(tool.input_schema),
    remember: tool.remember,
  }
}

/** A name the model can use: lower case, digits and underscores. */
function slug(text: string) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/^(\d)/, 't_$1')
    .slice(0, 64)
}

function TryTool({
  name,
  schema,
  api,
}: {
  name: string
  schema: JsonSchema
  api: SectionProps['api']
}) {
  const fields = fieldsOf(schema)
  const [values, setValues] = useState<Record<string, string>>({})
  const [result, setResult] = useState<{ ok: boolean; result: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    const args: Record<string, unknown> = {}
    for (const field of fields) {
      const value = values[field.name]?.trim()
      if (!value) continue
      args[field.name] = field.type === 'number' ? Number(value) : value
    }
    try {
      setResult(await api.tryTool(name, args))
    } catch (error) {
      setResult({ ok: false, result: error instanceof Error ? error.message : 'It did not run.' })
    } finally {
      setBusy(false)
    }
  }

  let shown = result?.result ?? ''
  try {
    shown = JSON.stringify(JSON.parse(shown), null, 2)
  } catch {
    /* not JSON: shown as it came */
  }

  return (
    <div className="bg-muted/40 flex flex-col gap-3 rounded-xl border p-4">
      <p className="text-sm font-medium">Try it</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {fields.map((field) => (
          <StackField key={field.name} label={field.name} htmlFor={`try-${name}-${field.name}`}>
            <Input
              id={`try-${name}-${field.name}`}
              placeholder={field.type === 'choice' ? field.choices : field.description}
              value={values[field.name] ?? ''}
              onChange={(e) => setValues((now) => ({ ...now, [field.name]: e.target.value }))}
            />
          </StackField>
        ))}
      </div>
      <Button size="sm" variant="outline" className="self-start" onClick={run} disabled={busy}>
        <PlayIcon /> {busy ? 'Running…' : 'Run'}
      </Button>
      {result && (
        <div className="flex flex-col gap-1.5">
          <Badge variant={result.ok ? 'default' : 'destructive'} className="rounded-md">
            {result.ok ? 'It worked' : 'It did not work'}
          </Badge>
          <pre className="bg-background max-h-72 overflow-auto rounded-lg border p-3 text-xs leading-relaxed">
            {shown}
          </pre>
        </div>
      )}
    </div>
  )
}

function ApiToolEditor({
  tool,
  change,
  remove,
}: {
  tool: ApiTool
  change: (changes: Partial<ApiTool>) => void
  remove: () => void
}) {
  const id = tool.name || 'new'
  const setField = (index: number, changes: Partial<InputField>) =>
    change({ fields: tool.fields.map((f, i) => (i === index ? { ...f, ...changes } : f)) })
  const headers = Object.entries(tool.http.headers)
  const setHeaders = (rows: [string, string][]) =>
    change({ http: { ...tool.http, headers: Object.fromEntries(rows) } })

  return (
    <CardContent className={ROWS}>
      <Field
        label="Name"
        htmlFor={`${id}-name`}
        hint="What the model calls it. Lower case and underscores, such as check_stock."
      >
        <Input
          id={`${id}-name`}
          className="font-mono"
          value={tool.name}
          onChange={(e) => change({ name: slug(e.target.value) })}
        />
      </Field>
      <Field
        label="What it does"
        htmlFor={`${id}-description`}
        hint="Shown to the model. Say when to use it and what comes back."
      >
        <Textarea
          id={`${id}-description`}
          rows={3}
          value={tool.description}
          onChange={(e) => change({ description: e.target.value })}
        />
      </Field>
      <Field
        label="Call"
        htmlFor={`${id}-url`}
        hint="Inputs in braces, such as {order_id}, go into the address. The rest are sent as the query or the JSON body."
      >
        <div className="flex flex-col gap-2">
          <Choice
            id={`${id}-method`}
            value={tool.http.method}
            options={METHODS}
            onChange={(method) => change({ http: { ...tool.http, method } })}
          />
          <Input
            id={`${id}-url`}
            className="font-mono text-xs"
            placeholder="https://shop.example.com/api/orders/{order_id}"
            value={tool.http.url}
            onChange={(e) => change({ http: { ...tool.http, url: e.target.value } })}
          />
        </div>
      </Field>
      <Field
        label="Headers"
        hint="For an API key, write ${TOOL_SHOP_KEY} and set TOOL_SHOP_KEY on the server. Keys never go in the rep's files."
      >
        <div className="flex flex-col gap-2">
          {headers.map(([name, value], index) => (
            <div key={index} className="flex gap-2">
              <Input
                aria-label="Header name"
                placeholder="Authorization"
                value={name}
                onChange={(e) =>
                  setHeaders(
                    headers.map((row, i) => (i === index ? [e.target.value, row[1]] : row)),
                  )
                }
              />
              <Input
                aria-label="Header value"
                className="font-mono text-xs"
                placeholder="Bearer ${TOOL_SHOP_KEY}"
                value={value}
                onChange={(e) =>
                  setHeaders(
                    headers.map((row, i) => (i === index ? [row[0], e.target.value] : row)),
                  )
                }
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Remove header"
                onClick={() => setHeaders(headers.filter((_, i) => i !== index))}
              >
                <Trash2Icon />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            size="sm"
            className="self-start"
            onClick={() => setHeaders([...headers, [`X-Header-${headers.length + 1}`, '']])}
          >
            <PlusIcon /> Add header
          </Button>
        </div>
      </Field>
      <div className="flex flex-col gap-3 py-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium">Inputs</p>
            <p className="text-muted-foreground text-sm">
              What the model must fill in. Anything that does not fit is refused before the call.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              change({
                fields: [
                  ...tool.fields,
                  {
                    name: `input_${tool.fields.length + 1}`,
                    type: 'text',
                    description: '',
                    required: true,
                    choices: '',
                  },
                ],
              })
            }
          >
            <PlusIcon /> Add input
          </Button>
        </div>
        {tool.fields.map((field, index) => (
          <div key={index} className="grid gap-2 rounded-lg border p-3 sm:grid-cols-[1fr_1fr_auto]">
            <Input
              aria-label="Input name"
              className="font-mono"
              value={field.name}
              onChange={(e) => setField(index, { name: slug(e.target.value) })}
            />
            <Choice
              id={`${id}-type-${index}`}
              value={field.type}
              options={TYPES}
              onChange={(type) => setField(index, { type })}
            />
            <Button
              variant="ghost"
              size="icon"
              aria-label="Remove input"
              onClick={() => change({ fields: tool.fields.filter((_, i) => i !== index) })}
            >
              <Trash2Icon />
            </Button>
            <Input
              aria-label="What this input is"
              placeholder="What this input is, for the model"
              className="sm:col-span-2"
              value={field.description}
              onChange={(e) => setField(index, { description: e.target.value })}
            />
            <label className="text-muted-foreground flex items-center gap-2 text-sm">
              <Switch
                checked={field.required}
                onCheckedChange={(required) => setField(index, { required })}
              />
              Required
            </label>
            {field.type === 'choice' && (
              <Input
                aria-label="Choices"
                placeholder="Choices, separated by commas"
                className="sm:col-span-3"
                value={field.choices}
                onChange={(e) => setField(index, { choices: e.target.value })}
              />
            )}
          </div>
        ))}
      </div>
      <div className="pt-5">
        <Button variant="ghost" size="sm" className="text-destructive" onClick={remove}>
          <Trash2Icon /> Remove this tool
        </Button>
      </div>
    </CardContent>
  )
}

export function ToolsSection({ pack, api, commit, go }: SectionProps) {
  const code = pack.tools.filter((tool) => tool.kind === 'code')
  const saved = pack.tools.filter((tool) => tool.kind === 'api')
  const [tools, setTools] = useState<ApiTool[]>(() => saved.map(toApiTool))
  const [dirty, setDirty] = useState(false)
  useEffect(() => {
    setTools(pack.tools.filter((tool) => tool.kind === 'api').map(toApiTool))
    setDirty(false)
  }, [pack.tools])

  const change = (index: number, changes: Partial<ApiTool>) => {
    setTools((now) => now.map((tool, i) => (i === index ? { ...tool, ...changes } : tool)))
    setDirty(true)
  }
  const add = () => {
    setTools((now) => [
      ...now,
      {
        name: `new_tool_${now.length + 1}`,
        description: '',
        http: { method: 'GET', url: 'https://', headers: {} },
        fields: [],
        remember: {},
      },
    ])
    setDirty(true)
  }
  const save = () =>
    commit('Tools saved', () =>
      api.saveTools(
        tools.map((tool) => ({
          name: tool.name,
          description: tool.description,
          http: tool.http,
          input_schema: schemaOf(tool.fields),
          remember: tool.remember,
        })),
      ),
    )

  return (
    <Section
      title="Tools"
      description="What the rep can do in your systems. The model asks to use a tool; the harness checks the inputs and your rules first, and only then runs it."
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={add}>
            <PlusIcon /> Add an API tool
          </Button>
          <SaveButton dirty={dirty} onSave={save} />
        </div>
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Calls to your own systems</CardTitle>
          <CardDescription>
            Point a tool at your web API and the rep can look things up or send them, with no code.
            Calls go only to public addresses, and never follow a redirect. To set a limit, such as
            a largest refund, add a rule for the tool on the{' '}
            <button className="underline underline-offset-2" onClick={() => go('rules')}>
              Rules
            </button>{' '}
            screen.
          </CardDescription>
        </CardHeader>
        {tools.length === 0 && (
          <CardContent>
            <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              No API tools yet. Add one to let the rep check stock, look up a booking or send an
              order to your system.
            </p>
          </CardContent>
        )}
      </Card>

      {tools.map((tool, index) => {
        const savedTool = saved.find((s) => s.name === tool.name)
        return (
          <Card key={index}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <code className="text-base">{tool.name || 'unnamed'}</code>
                <Badge variant="outline" className="rounded-md">
                  API · {tool.http.method}
                </Badge>
              </CardTitle>
            </CardHeader>
            <ApiToolEditor
              tool={tool}
              change={(changes) => change(index, changes)}
              remove={() => {
                setTools((now) => now.filter((_, i) => i !== index))
                setDirty(true)
              }}
            />
            {savedTool && !dirty && (
              <CardContent>
                <TryTool name={savedTool.name} schema={savedTool.input_schema} api={api} />
              </CardContent>
            )}
          </Card>
        )
      })}

      {code.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Written in code</CardTitle>
            <CardDescription>
              These run Python in the rep's folder, for work an API call cannot do. They are changed
              in tools.yaml and handlers.py; you can try them here.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {code.map((tool) => (
              <div key={tool.name} className="flex flex-col gap-3 rounded-xl border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <code className="text-sm font-medium">{tool.name}</code>
                  <Badge variant="secondary" className="rounded-md">
                    {tool.handler}
                  </Badge>
                </div>
                <p className="text-muted-foreground text-sm">{tool.description}</p>
                <TryTool name={tool.name} schema={tool.input_schema} api={api} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {pack.records.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Built in: taking things down</CardTitle>
            <CardDescription>
              Each kind of record is a tool the rep has without any set-up. What it takes down lands
              in Orders and quotes.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {pack.records.map((record) => (
              <Badge key={record.name} variant="outline" className="rounded-md">
                create_{record.name} · {record.label}
              </Badge>
            ))}
          </CardContent>
        </Card>
      )}
    </Section>
  )
}
