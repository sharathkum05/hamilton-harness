// The dashboard's first screen: what needs attention, what the rep has been
// doing, and how to get started when nothing has happened yet.

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ArrowRightIcon, ArrowUpRightIcon, CheckIcon } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import type { Overview } from '@/admin/api'
import { Section } from '@/admin/fields'
import type { SectionProps } from '@/admin/sections'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import type { ChartConfig } from '@/components/ui/chart'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

const CHART: ChartConfig = {
  conversations: { label: 'Conversations', color: 'var(--foreground)' },
  records: { label: 'Orders and quotes', color: 'var(--muted-foreground)' },
}

function Tile({
  label,
  value,
  hint,
  onClick,
  strong,
}: {
  label: string
  value: number
  hint: string
  onClick: () => void
  strong?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'group flex flex-col gap-3 rounded-2xl border p-5 text-left transition-colors duration-200',
        strong ? 'bg-primary text-primary-foreground border-transparent' : 'bg-card hover:bg-muted/50',
      )}
    >
      <span className="flex items-center justify-between text-sm">
        <span className={strong ? 'opacity-80' : 'text-muted-foreground'}>{label}</span>
        <ArrowUpRightIcon className="size-4 opacity-0 transition-opacity duration-200 group-hover:opacity-70" />
      </span>
      <span className="font-heading text-5xl leading-none tabular-nums">{value}</span>
      <span className={cn('text-sm', strong ? 'opacity-80' : 'text-muted-foreground')}>{hint}</span>
    </button>
  )
}

function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="bg-card flex min-w-0 flex-col gap-4 rounded-2xl border p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Step({ done, title, children }: { done: boolean; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        className={cn(
          'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border',
          done && 'bg-primary text-primary-foreground border-transparent',
        )}
      >
        {done && <CheckIcon className="size-3" />}
      </span>
      <div className="flex flex-col gap-1.5">
        <span className={cn('text-sm font-medium', done && 'text-muted-foreground line-through')}>{title}</span>
        {!done && children}
      </div>
    </li>
  )
}

export function OverviewSection({ pack, api, go }: SectionProps) {
  const [stats, setStats] = useState<Overview | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    api.overview().then(setStats).catch(() => setFailed(true))
  }, [api])

  if (failed) {
    return (
      <Section title="Overview" description="The numbers could not be loaded. Check that the server is running, then reload.">
        <span />
      </Section>
    )
  }

  if (!stats) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading the overview">
        <Skeleton className="h-9 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-36 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-72 rounded-2xl" />
      </div>
    )
  }

  const { records, conversations } = stats
  const guard = conversations.blocked + conversations.refused
  const quiet = conversations.total === 0 && records.total === 0
  const labels = Object.fromEntries(pack.records.map((type) => [type.name, type.label]))

  return (
    <Section
      title={`${pack.persona.name} at ${pack.persona.company}`}
      description={
        quiet
          ? 'Nothing has happened yet. Three steps get the rep in front of customers.'
          : 'What needs your attention, and what the rep has been doing.'
      }
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tile
          strong={records.waiting > 0}
          label="Waiting for you"
          value={records.waiting}
          hint={records.waiting === 1 ? 'order or quote to handle' : 'orders and quotes to handle'}
          onClick={() => go('inbox')}
        />
        <Tile
          label="Conversations"
          value={conversations.total}
          hint="recorded step by step"
          onClick={() => go('conversations')}
        />
        <Tile
          label="Guard stepped in"
          value={guard}
          hint="blocked, replaced or turned away"
          onClick={() => go('conversations')}
        />
        <Tile
          label="Handed to your team"
          value={conversations.handed_off}
          hint="conversations passed to a person"
          onClick={() => go('conversations')}
        />
      </div>

      {quiet ? (
        <Panel title="Get started">
          <ol className="flex flex-col gap-5">
            <Step done={false} title="Talk to the rep yourself">
              <p className="text-muted-foreground text-sm">
                Use the live preview on the right, or open the demo to see each turn from the inside.
              </p>
              <Button asChild variant="outline" size="sm" className="self-start">
                <a href="/demo" target="_blank" rel="noreferrer">
                  Open the demo <ArrowUpRightIcon />
                </a>
              </Button>
            </Step>
            <Step done={false} title="Run the fake customers">
              <p className="text-muted-foreground text-sm">
                {pack.scenarios} test customers check that the rep still refuses what it should.
              </p>
              <Button variant="outline" size="sm" className="self-start" onClick={() => go('test')}>
                Go to tests <ArrowRightIcon />
              </Button>
            </Step>
            <Step done={false} title="Put it on your site">
              <p className="text-muted-foreground text-sm">One script tag, for any kind of site.</p>
              <Button variant="outline" size="sm" className="self-start" onClick={() => go('install')}>
                Get the snippet <ArrowRightIcon />
              </Button>
            </Step>
          </ol>
        </Panel>
      ) : (
        <>
          <Panel title="The last two weeks">
            <ChartContainer config={CHART} className="h-60 w-full">
              <AreaChart data={stats.timeline} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="day"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  minTickGap={28}
                  tickFormatter={(day: string) =>
                    new Date(`${day}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
                  }
                />
                <YAxis allowDecimals={false} width={28} tickLine={false} axisLine={false} />
                <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
                <Area
                  dataKey="conversations"
                  type="monotone"
                  stroke="var(--color-conversations)"
                  fill="var(--color-conversations)"
                  fillOpacity={0.12}
                  strokeWidth={2}
                />
                <Area
                  dataKey="records"
                  type="monotone"
                  stroke="var(--color-records)"
                  fill="var(--color-records)"
                  fillOpacity={0.08}
                  strokeWidth={2}
                  strokeDasharray="4 4"
                />
              </AreaChart>
            </ChartContainer>
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel
              title="Latest orders and quotes"
              action={
                <Button variant="ghost" size="sm" onClick={() => go('inbox')}>
                  See all <ArrowRightIcon />
                </Button>
              }
            >
              {stats.recent_records.length === 0 ? (
                <p className="text-muted-foreground text-sm">None yet.</p>
              ) : (
                <ul className="flex flex-col divide-y">
                  {stats.recent_records.map((record) => (
                    <li key={record.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                      <span className="flex min-w-0 flex-col">
                        <span className="font-mono text-xs">{record.id}</span>
                        <span className="text-muted-foreground truncate text-sm">
                          {labels[record.type] ?? record.type} · {Object.values(record.data).slice(0, 2).join(' · ')}
                        </span>
                      </span>
                      <Badge variant={record.status === 'new' ? 'default' : 'outline'} className="rounded-md capitalize">
                        {record.status}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel
              title="Latest conversations"
              action={
                <Button variant="ghost" size="sm" onClick={() => go('conversations')}>
                  See all <ArrowRightIcon />
                </Button>
              }
            >
              {stats.recent_conversations.length === 0 ? (
                <p className="text-muted-foreground text-sm">None yet.</p>
              ) : (
                <ul className="flex flex-col divide-y">
                  {stats.recent_conversations.map((item) => (
                    <li key={item.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                      <span className="min-w-0 truncate text-sm">{item.opening || '(no message)'}</span>
                      <span className="flex shrink-0 gap-1">
                        {item.blocked && <Badge variant="destructive" className="rounded-md">guard</Badge>}
                        {item.refused && <Badge variant="outline" className="rounded-md">off topic</Badge>}
                        {item.handed_off && <Badge variant="secondary" className="rounded-md">handed off</Badge>}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </>
      )}
    </Section>
  )
}
