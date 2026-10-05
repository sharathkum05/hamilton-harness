// Small form pieces shared by the dashboard's sections.

import { createContext } from 'react'
import type { ReactNode } from 'react'

import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

/** Throws away unsaved edits in the open section. Provided by the dashboard shell. */
export const DiscardContext = createContext<() => void>(() => {})

/** Class for a card body whose settings sit one per row, with a hairline between them. */
export const ROWS = 'flex flex-col divide-y'

/**
 * One setting as a row: what it is and why on the left, the control on the
 * right. On a narrow screen the control drops below.
 */
export function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string
  hint?: string
  htmlFor?: string
  children: ReactNode
}) {
  return (
    <div className="grid gap-x-10 gap-y-2.5 py-5 first:pt-0 last:pb-0 md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <div className="flex flex-col gap-1">
        <Label htmlFor={htmlFor}>{label}</Label>
        {hint && <p className="text-muted-foreground text-sm leading-snug text-pretty">{hint}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

/** A setting with its label above the control, for tight spaces. */
export function StackField({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string
  hint?: string
  htmlFor?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-muted-foreground text-xs">{hint}</p>}
    </div>
  )
}

/** A list of short strings, edited one per line. */
export function Lines({
  id,
  value,
  onChange,
  rows = 4,
  placeholder,
  mono,
}: {
  id: string
  value: string[]
  onChange: (next: string[]) => void
  rows?: number
  placeholder?: string
  mono?: boolean
}) {
  return (
    <Textarea
      id={id}
      rows={rows}
      placeholder={placeholder}
      className={mono ? 'font-mono text-xs' : undefined}
      defaultValue={value.join('\n')}
      // Parsed on blur so a half-typed line is not trimmed away mid-keystroke.
      onBlur={(event) =>
        onChange(
          event.target.value
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean),
        )
      }
    />
  )
}

/** An on-off setting as a row: the label and what it does, with the switch at the end. */
export function Toggle({
  id,
  label,
  hint,
  checked,
  onChange,
}: {
  id: string
  label: string
  hint?: string
  checked: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <div className="flex items-start justify-between gap-8 py-5 first:pt-0 last:pb-0">
      <div className="flex flex-col gap-1">
        <Label htmlFor={id}>{label}</Label>
        {hint && (
          <p className="text-muted-foreground max-w-[60ch] text-sm leading-snug text-pretty">
            {hint}
          </p>
        )}
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onChange} className="mt-0.5 shrink-0" />
    </div>
  )
}

export function Section({
  title,
  description,
  children,
  actions,
}: {
  title: string
  description: string
  children: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-3xl">{title}</h1>
          <p className="text-muted-foreground max-w-[62ch] text-sm leading-relaxed text-pretty">
            {description}
          </p>
        </div>
        {actions}
      </div>
      {children}
    </div>
  )
}
