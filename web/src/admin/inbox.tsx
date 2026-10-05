// What the rep has taken down for the business: orders, quotation requests
// and any other record type the pack defines.

import { useCallback, useEffect, useState } from 'react'
import { ArrowRightIcon, InboxIcon, RefreshCwIcon, SearchIcon } from 'lucide-react'

import type { RecordItem, RecordStatus } from '@/admin/api'
import { Section } from '@/admin/fields'
import type { SectionProps } from '@/admin/sections'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const STATUSES: [RecordStatus, string][] = [
  ['new', 'New'],
  ['confirmed', 'Confirmed'],
  ['done', 'Done'],
  ['cancelled', 'Cancelled'],
]

/** Remembered across sections so "open the conversation" lands on the right one. */
export const OPEN_CONVERSATION_KEY = 'hamilton:open-conversation'

export function InboxSection({ pack, api, go }: SectionProps) {
  const [records, setRecords] = useState<RecordItem[] | null>(null)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)

  const load = useCallback(() => {
    api
      .records()
      .then((body) => setRecords(body.records))
      .catch(() => setRecords([]))
  }, [api])

  useEffect(load, [load])

  const labels = Object.fromEntries(pack.records.map((type) => [type.name, type]))
  const needle = query.trim().toLowerCase()
  const shown = (records ?? []).filter(
    (record) =>
      (filter === 'all' || record.type === filter) &&
      (!needle ||
        `${record.id} ${Object.values(record.data).join(' ')}`.toLowerCase().includes(needle)),
  )
  const opened = (records ?? []).find((record) => record.id === openId) ?? null
  const label = (record: RecordItem, key: string) =>
    labels[record.type]?.fields.find((f) => f.name === key)?.label || key

  const openConversation = (record: RecordItem) => {
    try {
      sessionStorage.setItem(OPEN_CONVERSATION_KEY, record.conversation_id)
    } catch {
      /* the conversations screen still opens, just without one selected */
    }
    go('conversations')
  }
  const waiting = (records ?? []).filter((record) => record.status === 'new').length

  const setStatus = async (record: RecordItem, status: RecordStatus) => {
    const updated = await api.setRecordStatus(record.id, status)
    setRecords((current) => (current ?? []).map((r) => (r.id === updated.id ? updated : r)))
  }

  return (
    <Section
      title="Orders and quotes"
      description="Everything the rep has taken down for you. Each one has a reference the customer was given. Work through the new ones and mark them as you go."
      actions={
        <Button variant="outline" onClick={load}>
          <RefreshCwIcon /> Refresh
        </Button>
      }
    >
      {pack.records.length === 0 ? (
        <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
          This pack has no record types yet. Add a <code>records.yaml</code> to let the rep take
          orders, quotation requests or leads.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs value={filter} onValueChange={setFilter}>
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                {pack.records.map((type) => (
                  <TabsTrigger key={type.name} value={type.name}>
                    {type.label}s
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <div className="flex items-center gap-3">
              <span className="text-muted-foreground text-sm tabular-nums">
                {waiting} waiting · {(records ?? []).length} in total
              </span>
              <div className="relative">
                <SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
                <Input
                  aria-label="Search orders and quotes"
                  placeholder="Search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="h-8 w-44 pl-8"
                />
              </div>
            </div>
          </div>
          {shown.length === 0 ? (
            <div className="text-muted-foreground flex flex-col items-center gap-2 rounded-lg border border-dashed p-10 text-center text-sm">
              <InboxIcon className="size-6" />
              <p>Nothing here yet. Ask the rep in the preview for a quote for 40 pairs.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border [scrollbar-width:thin]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Reference</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead>Received</TableHead>
                    <TableHead className="w-36">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {shown.map((record) => (
                    <TableRow
                      key={record.id}
                      className="cursor-pointer"
                      onClick={() => setOpenId(record.id)}
                    >
                      <TableCell className="align-top">
                        <div className="flex flex-col items-start gap-1.5">
                          <span className="flex items-center gap-2 font-mono text-xs">
                            {/* A filled dot marks what nobody has looked at yet. */}
                            <span
                              aria-hidden="true"
                              className={
                                record.status === 'new'
                                  ? 'bg-foreground size-1.5 rounded-full'
                                  : 'size-1.5'
                              }
                            />
                            {record.id}
                          </span>
                          <Badge variant="outline">
                            {labels[record.type]?.label ?? record.type}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="min-w-44 whitespace-normal">
                        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
                          {Object.entries(record.data).map(([key, value]) => (
                            <div key={key} className="contents">
                              <dt className="text-muted-foreground">{label(record, key)}</dt>
                              <dd className="[overflow-wrap:anywhere]">{String(value)}</dd>
                            </div>
                          ))}
                        </dl>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs whitespace-nowrap">
                        {new Date(record.created_at).toLocaleString(undefined, {
                          dateStyle: 'medium',
                          timeStyle: 'short',
                        })}
                      </TableCell>
                      <TableCell onClick={(event) => event.stopPropagation()}>
                        <Select
                          value={record.status}
                          onValueChange={(status) => setStatus(record, status as RecordStatus)}
                        >
                          <SelectTrigger className="h-8 w-32" aria-label={`Status of ${record.id}`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {STATUSES.map(([value, label]) => (
                              <SelectItem key={value} value={value}>
                                {label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}

      {/* A slide-over keeps the list in view, where a popup would cover it. */}
      <Sheet open={opened !== null} onOpenChange={(open) => !open && setOpenId(null)}>
        <SheetContent className="flex flex-col gap-6 sm:max-w-md">
          {opened && (
            <>
              <SheetHeader>
                <SheetTitle className="font-heading text-2xl">{opened.id}</SheetTitle>
                <SheetDescription>
                  {labels[opened.type]?.label ?? opened.type}, received{' '}
                  {new Date(opened.created_at).toLocaleString(undefined, {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })}
                </SheetDescription>
              </SheetHeader>
              <dl className="flex flex-col divide-y px-4">
                {Object.entries(opened.data).map(([key, value]) => (
                  <div key={key} className="flex items-baseline justify-between gap-6 py-3">
                    <dt className="text-muted-foreground text-sm">{label(opened, key)}</dt>
                    <dd className="text-right text-sm font-medium [overflow-wrap:anywhere]">
                      {String(value)}
                    </dd>
                  </div>
                ))}
              </dl>
              <div className="flex flex-col gap-2 px-4">
                <span className="text-muted-foreground text-sm">Status</span>
                <div className="flex flex-wrap gap-1.5">
                  {STATUSES.map(([value, text]) => (
                    <Button
                      key={value}
                      size="sm"
                      variant={opened.status === value ? 'default' : 'outline'}
                      onClick={() => setStatus(opened, value)}
                    >
                      {text}
                    </Button>
                  ))}
                </div>
              </div>
              {opened.conversation_id && (
                <Button
                  variant="ghost"
                  className="mx-4 justify-between"
                  onClick={() => openConversation(opened)}
                >
                  Read the conversation it came from <ArrowRightIcon />
                </Button>
              )}
            </>
          )}
        </SheetContent>
      </Sheet>
    </Section>
  )
}
