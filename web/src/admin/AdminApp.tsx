// The dashboard shell, on the official shadcn/ui sidebar: a token gate, grouped
// navigation that collapses to icons, the open section, and a live preview of
// the chat as customers will see it.

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ComponentType } from 'react'
import {
  BookOpenIcon,
  CodeIcon,
  ExternalLinkIcon,
  FlaskConicalIcon,
  InboxIcon,
  MessagesSquareIcon,
  MicIcon,
  PaletteIcon,
  PanelRightIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  TargetIcon,
  UserRoundCheckIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import { adminApi, loadToken, storeToken } from '@/admin/api'
import type { Pack } from '@/admin/api'
import { InboxSection } from '@/admin/inbox'
import { ConversationsSection, InstallSection, TestSection } from '@/admin/more'
import {
  BrandSection,
  HandoffSection,
  KnowledgeSection,
  RulesSection,
  ScopeSection,
  VoiceSection,
} from '@/admin/sections'
import type { SectionProps } from '@/admin/sections'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Toaster } from '@/components/ui/sonner'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'

type Entry = [string, string, ComponentType<{ className?: string }>, ComponentType<SectionProps>]

const GROUPS: [string, Entry[]][] = [
  [
    'Business',
    [
      ['inbox', 'Orders and quotes', InboxIcon, InboxSection],
      ['conversations', 'Conversations', MessagesSquareIcon, ConversationsSection],
    ],
  ],
  [
    'Your rep',
    [
      ['brand', 'Brand', PaletteIcon, BrandSection],
      ['voice', 'Voice', MicIcon, VoiceSection],
      ['scope', 'Scope', TargetIcon, ScopeSection],
      ['knowledge', 'Knowledge', BookOpenIcon, KnowledgeSection],
      ['rules', 'Rules', ShieldCheckIcon, RulesSection],
      ['handoff', 'Handoff', UserRoundCheckIcon, HandoffSection],
    ],
  ],
  [
    'Go live',
    [
      ['test', 'Test', FlaskConicalIcon, TestSection],
      ['install', 'Install', CodeIcon, InstallSection],
    ],
  ],
]

const ENTRIES = GROUPS.flatMap(([group, entries]) => entries.map((entry) => ({ group, entry })))

function TokenGate({ onToken, rejected }: { onToken: (token: string) => void; rejected: boolean }) {
  const [value, setValue] = useState('')
  return (
    <div className="flex h-full items-center justify-center p-6">
      <form
        className="flex w-full max-w-sm flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          onToken(value.trim())
        }}
      >
        <h1 className="text-lg font-semibold">Dashboard</h1>
        <p className="text-muted-foreground text-sm">
          Enter the admin token. The server prints a link that includes it when started with{' '}
          <code>--admin</code>.
        </p>
        <Input
          type="password"
          aria-label="Admin token"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        {rejected && <p className="text-destructive text-sm">That token was not accepted.</p>}
        <Button type="submit" disabled={!value.trim()}>
          Open dashboard
        </Button>
      </form>
    </div>
  )
}

export function AdminApp() {
  const [token, setToken] = useState(loadToken)
  const [pack, setPack] = useState<Pack | null>(null)
  const [rejected, setRejected] = useState(false)
  const [section, setSection] = useState(() => window.location.hash.slice(1) || 'inbox')
  const [previewKey, setPreviewKey] = useState(0)
  const [showPreview, setShowPreview] = useState(true)
  const api = useMemo(() => adminApi(token), [token])

  // The dashboard follows the visitor's device theme; the brand's theme applies to the chat only.
  useEffect(() => {
    const system = window.matchMedia('(prefers-color-scheme: dark)')
    const sync = () => document.documentElement.classList.toggle('dark', system.matches)
    sync()
    system.addEventListener('change', sync)
    return () => system.removeEventListener('change', sync)
  }, [])

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      setPack(await api.pack())
      setRejected(false)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        storeToken('')
        setToken('')
        setRejected(true)
      } else {
        toast.error('Could not load the pack.')
      }
    }
  }, [api, token])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    document.title = pack ? `${pack.persona.company} dashboard` : 'Dashboard'
  }, [pack])

  const commit = useCallback(
    async (label: string, work: () => Promise<unknown>) => {
      try {
        await work()
        toast.success(label)
        await refresh()
        setPreviewKey((key) => key + 1)
        return true
      } catch (error) {
        // The server says exactly which field was wrong; pass that on.
        toast.error(error instanceof Error ? error.message : 'That could not be saved.')
        return false
      }
    },
    [refresh],
  )

  const go = (key: string) => {
    setSection(key)
    history.replaceState(null, '', `#${key}`)
  }

  if (!token) {
    return (
      <TokenGate
        rejected={rejected}
        onToken={(value) => {
          storeToken(value)
          setToken(value)
        }}
      />
    )
  }
  if (!pack) return null

  const active = ENTRIES.find(({ entry }) => entry[0] === section) ?? ENTRIES[0]
  const Active = active.entry[3]

  return (
    <SidebarProvider className="h-svh min-h-0">
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" className="cursor-default hover:bg-transparent">
                <span className="bg-muted ring-border flex aspect-square size-8 shrink-0 overflow-hidden rounded-lg ring-1">
                  {pack.widget.logo && (
                    <img src={`/brand/logo?k=${previewKey}`} alt="" className="size-full object-cover" />
                  )}
                </span>
                <span className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">{pack.persona.company}</span>
                  <span className="text-muted-foreground truncate text-xs">
                    {pack.persona.name} · {pack.persona.role}
                  </span>
                </span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          {GROUPS.map(([group, entries]) => (
            <SidebarGroup key={group}>
              <SidebarGroupLabel>{group}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {entries.map(([key, label, Icon]) => (
                    <SidebarMenuItem key={key}>
                      <SidebarMenuButton
                        tooltip={label}
                        isActive={active.entry[0] === key}
                        onClick={() => go(key)}
                      >
                        <Icon />
                        <span>{label}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </SidebarContent>
        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="Open the demo">
                <a href="/demo" target="_blank" rel="noreferrer">
                  <ExternalLinkIcon />
                  <span>Open the demo</span>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset className="min-h-0 overflow-hidden">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden sm:block">{active.group}</BreadcrumbItem>
              <BreadcrumbSeparator className="hidden sm:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>{active.entry[1]}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto hidden xl:inline-flex"
            aria-pressed={showPreview}
            onClick={() => setShowPreview((shown) => !shown)}
          >
            <PanelRightIcon /> Preview
          </Button>
        </header>
        <div className="flex min-h-0 flex-1">
          <main className="min-w-0 flex-1 overflow-y-auto">
            <div className="mx-auto max-w-4xl px-5 py-8">
              <Active pack={pack} api={api} commit={commit} />
            </div>
          </main>
          <aside
            className={cn('w-[380px] shrink-0 flex-col border-l', showPreview ? 'hidden xl:flex' : 'hidden')}
          >
            <div className="flex h-11 items-center justify-between border-b px-4">
              <span className="text-sm font-medium">Live preview</span>
              <Button variant="ghost" size="sm" onClick={() => setPreviewKey((key) => key + 1)}>
                <RefreshCwIcon /> Restart
              </Button>
            </div>
            <iframe
              key={previewKey}
              title="Chat preview"
              src="/chat?nopacing&inline"
              className="min-h-0 flex-1"
            />
          </aside>
        </div>
      </SidebarInset>
      <Toaster position="bottom-center" />
    </SidebarProvider>
  )
}
