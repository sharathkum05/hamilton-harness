// The dashboard shell, on the official shadcn/ui sidebar: a token gate, grouped
// navigation that collapses to icons, a command menu, a theme switcher, the
// open section with its unsaved-changes bar, and a live preview of the chat.

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ComponentType } from 'react'
import {
  BookOpenIcon,
  CodeIcon,
  ExternalLinkIcon,
  FlaskConicalIcon,
  InboxIcon,
  LayoutDashboardIcon,
  MessagesSquareIcon,
  MicIcon,
  MonitorIcon,
  MoonIcon,
  PaletteIcon,
  PanelRightIcon,
  RefreshCwIcon,
  SearchIcon,
  ShieldCheckIcon,
  SunIcon,
  TargetIcon,
  UserRoundCheckIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import { adminApi, loadToken, storeToken } from '@/admin/api'
import type { Pack } from '@/admin/api'
import { CommandMenu } from '@/admin/command-menu'
import { DiscardContext } from '@/admin/fields'
import { InboxSection } from '@/admin/inbox'
import { ConversationsSection } from '@/admin/conversations'
import { InstallSection, TestSection } from '@/admin/more'
import { OverviewSection } from '@/admin/overview'
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Skeleton } from '@/components/ui/skeleton'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ApiError } from '@/lib/api'
import { useTheme } from '@/lib/theme'
import type { Theme } from '@/lib/theme'
import { cn } from '@/lib/utils'

type Icon = ComponentType<{ className?: string }>
type Entry = [string, string, Icon, ComponentType<SectionProps>]

const GROUPS: [string, Entry[]][] = [
  [
    'Business',
    [
      ['overview', 'Overview', LayoutDashboardIcon, OverviewSection],
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
const NAVIGATION = GROUPS.map(
  ([group, entries]) =>
    [group, entries.map(([key, label, icon]) => [key, label, icon])] as [string, [string, string, Icon][]],
)
const THEME_ICON: Record<Theme, Icon> = { system: MonitorIcon, light: SunIcon, dark: MoonIcon }

function TokenGate({ onToken, rejected }: { onToken: (token: string) => void; rejected: boolean }) {
  const [value, setValue] = useState('')
  return (
    <div className="flex h-full items-center justify-center p-6">
      <form
        className="bg-card flex w-full max-w-sm flex-col gap-4 rounded-2xl border p-6"
        onSubmit={(event) => {
          event.preventDefault()
          onToken(value.trim())
        }}
      >
        <h1 className="text-2xl">Dashboard</h1>
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

/** The shape of the dashboard while the pack loads, so nothing jumps when it arrives. */
function LoadingShell() {
  return (
    <div className="flex h-svh" aria-busy="true" aria-label="Loading the dashboard">
      <div className="bg-sidebar hidden w-64 flex-col gap-3 border-r p-4 md:flex">
        <Skeleton className="h-10 w-full" />
        {[...Array(8)].map((_, index) => (
          <Skeleton key={index} className="h-7 w-full" />
        ))}
      </div>
      <div className="flex flex-1 flex-col gap-6 p-8">
        <Skeleton className="h-9 w-72" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-36 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-72 rounded-2xl" />
      </div>
    </div>
  )
}

export function AdminApp() {
  const [token, setToken] = useState(loadToken)
  const [pack, setPack] = useState<Pack | null>(null)
  const [rejected, setRejected] = useState(false)
  const [section, setSection] = useState(() => window.location.hash.slice(1) || 'overview')
  const [previewKey, setPreviewKey] = useState(0)
  const [formKey, setFormKey] = useState(0)
  const [showPreview, setShowPreview] = useState(true)
  const [menuOpen, setMenuOpen] = useState(false)
  const [waiting, setWaiting] = useState(0)
  const { theme, dark, setTheme } = useTheme()
  const api = useMemo(() => adminApi(token), [token])

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

  // The sidebar shows how many orders and quotes are waiting, refreshed as you move around.
  useEffect(() => {
    if (!token) return
    api
      .overview()
      .then((stats) => setWaiting(stats.records.waiting))
      .catch(() => {})
  }, [api, token, section])

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

  const go = useCallback((key: string) => {
    setSection(key)
    history.replaceState(null, '', `#${key}`)
  }, [])

  // Remounting the section throws its edits away and starts again from the saved pack.
  const discard = useCallback(() => setFormKey((key) => key + 1), [])

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
  if (!pack) return <LoadingShell />

  const active = ENTRIES.find(({ entry }) => entry[0] === section) ?? ENTRIES[0]
  const Active = active.entry[3]
  const ThemeIcon = THEME_ICON[theme]

  return (
    // The sidebar's collapsed buttons show tooltips, which need this provider above them.
    <TooltipProvider>
      <a
        href="#content"
        className="bg-primary text-primary-foreground sr-only z-50 rounded-md px-3 py-2 text-sm focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <SidebarProvider className="h-svh min-h-0">
        <Sidebar collapsible="icon">
          <SidebarHeader>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton size="lg" onClick={() => go('overview')} tooltip={pack.persona.company}>
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
                        {key === 'inbox' && waiting > 0 && (
                          <SidebarMenuBadge className="bg-primary text-primary-foreground rounded-md tabular-nums">
                            {waiting}
                          </SidebarMenuBadge>
                        )}
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
            <div className="ml-auto flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                className="text-muted-foreground hidden w-56 justify-between font-normal md:flex"
                onClick={() => setMenuOpen(true)}
              >
                <span className="flex items-center gap-2">
                  <SearchIcon /> Go to
                </span>
                <kbd className="bg-muted rounded px-1.5 font-mono text-[11px]">⌘K</kbd>
              </Button>
              <Button variant="ghost" size="icon" className="size-8 md:hidden" onClick={() => setMenuOpen(true)}>
                <SearchIcon />
                <span className="sr-only">Open the command menu</span>
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="size-8">
                    <ThemeIcon />
                    <span className="sr-only">Theme</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuRadioGroup value={theme} onValueChange={(value) => setTheme(value as Theme)}>
                    <DropdownMenuRadioItem value="light">Light</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="dark">Dark</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="system">Follow this device</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                variant="ghost"
                size="sm"
                className="hidden xl:inline-flex"
                aria-pressed={showPreview}
                onClick={() => setShowPreview((shown) => !shown)}
              >
                <PanelRightIcon /> Preview
              </Button>
            </div>
          </header>
          <div className="flex min-h-0 flex-1">
            <main id="content" tabIndex={-1} className="relative min-w-0 flex-1 overflow-y-auto outline-none">
              <div className="mx-auto max-w-5xl px-5 pt-8 pb-28 sm:px-8">
                <DiscardContext.Provider value={discard}>
                  <Active key={formKey} pack={pack} api={api} commit={commit} go={go} />
                </DiscardContext.Provider>
              </div>
              {/* The open section's unsaved-changes bar is drawn here. */}
              <div id="save-slot" className="pointer-events-none sticky bottom-5 z-20 flex justify-center px-4 *:pointer-events-auto" />
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
        <CommandMenu open={menuOpen} setOpen={setMenuOpen} groups={NAVIGATION} go={go} setTheme={setTheme} />
        <Toaster position="top-center" theme={dark ? 'dark' : 'light'} />
      </SidebarProvider>
    </TooltipProvider>
  )
}
