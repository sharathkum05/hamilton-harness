// Small form pieces shared by the dashboard's sections.

import type { ReactNode } from 'react'

import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

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
    <div className="flex items-start justify-between gap-4 rounded-lg border p-3">
      <div className="flex flex-col gap-0.5">
        <Label htmlFor={id}>{label}</Label>
        {hint && <p className="text-muted-foreground text-xs">{hint}</p>}
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl">{title}</h1>
          <p className="text-muted-foreground max-w-[62ch] text-sm">{description}</p>
        </div>
        {actions}
      </div>
      {children}
    </div>
  )
}
