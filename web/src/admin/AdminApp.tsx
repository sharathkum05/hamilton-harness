// The dashboard shell, on the official shadcn/ui sidebar: a sign-in screen, grouped
// navigation that collapses to icons, a command menu, a theme switcher, the
// open section with its unsaved-changes bar, and a live preview of the chat.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ComponentType } from 'react'
import {
  BookOpenIcon,
  CodeIcon,
  ExternalLinkIcon,
  FlaskConicalIcon,
  InboxIcon,
  LayoutDashboardIcon,
  LogOutIcon,
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
  WandSparklesIcon,
  WorkflowIcon,
  WrenchIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import { adminApi, getSession, loadToken, signIn, signOut, storeToken } from '@/admin/api'
import type { Pack } from '@/admin/api'
import { CommandMenu } from '@/admin/command-menu'
import { DiscardContext } from '@/admin/fields'
import { InboxSection } from '@/admin/inbox'
import { ConversationsSection } from '@/admin/conversations'
import { InstallSection, TestSection } from '@/admin/more'
import { OverviewSection } from '@/admin/overview'
import { SetupSection } from '@/admin/setup'
import { FlowSection } from '@/admin/flow'
import { ToolsSection } from '@/admin/tools'
import {
  BrandSection,
  HandoffSection,
  KnowledgeSection,
  RulesSection,
  ScopeSection,
  VoiceSection,
} from '@/admin/sections'
import type { SectionProps } from '@/admin/sections'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
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
import { Label } from '@/components/ui/label'
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
import { forgetConversation } from '@/lib/conversation'
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
      ['flow', 'Flow', WorkflowIcon, FlowSection],
      ['brand', 'Brand', PaletteIcon, BrandSection],
      ['voice', 'Voice', MicIcon, VoiceSection],
      ['scope', 'Scope', TargetIcon, ScopeSection],
      ['knowledge', 'Knowledge', BookOpenIcon, KnowledgeSection],
      ['tools', 'Tools', WrenchIcon, ToolsSection],
      ['rules', 'Rules', ShieldCheckIcon, RulesSection],
      ['handoff', 'Handoff', UserRoundCheckIcon, HandoffSection],
    ],
  ],
  [
    'Go live',
    [
      ['test', 'Test', FlaskConicalIcon, TestSection],
      ['install', 'Install', CodeIcon, InstallSection],
      ['setup', 'Setup', WandSparklesIcon, SetupSection],
    ],
  ],
]

const ENTRIES = GROUPS.flatMap(([group, entries]) => entries.map((entry) => ({ group, entry })))
const NAVIGATION = GROUPS.map(
  ([group, entries]) =>
    [group, entries.map(([key, label, icon]) => [key, label, icon])] as [
      string,
      [string, string, Icon][],
    ],
)
const THEME_ICON: Record<Theme, Icon> = { system: MonitorIcon, light: SunIcon, dark: MoonIcon }

/** The server's reasons are written in lower case for logs; shown here as a sentence. */
function sentence(message: string) {
  const text = message.charAt(0).toUpperCase() + message.slice(1)
  return /[.!?]$/.test(text) ? text : `${text}.`
}

function SignIn({
  onSignedIn,
  onToken,
  tokenRejected,
}: {
  onSignedIn: () => void
  onToken: (token: string) => void
  tokenRejected: boolean
}) {
  const [withToken, setWithToken] = useState(tokenRejected)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState('')
  const [error, setError] = useState(tokenRejected ? 'That token was not accepted.' : '')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (withToken) {
      onToken(token.trim())
      return
    }
    setBusy(true)
    setError('')
    try {
      await signIn(email.trim(), password)
      onSignedIn()
    } catch (failure) {
      setError(failure instanceof Error ? sentence(failure.message) : 'Could not sign in.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-6">
      <form
        className="bg-card flex w-full max-w-sm flex-col gap-5 rounded-2xl border p-6"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <div className="flex flex-col gap-1.5">
          <h1 className="text-2xl">Sign in to the dashboard</h1>
          <p className="text-muted-foreground text-sm">
            {withToken
              ? 'Paste the admin token from the server.'
              : 'The server prints the admin email and password when it starts.'}
          </p>
        </div>
        {withToken ? (
          <div className="flex flex-col gap-2">
            <Label htmlFor="admin-token">Admin token</Label>
            <Input
              id="admin-token"
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-2">
              <Label htmlFor="admin-email">Email</Label>
              <Input
                id="admin-email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="admin-password">Password</Label>
              <Input
                id="admin-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </>
        )}
        {error && (
          <p role="alert" className="text-destructive text-sm">
            {error}
          </p>
        )}
        <Button
          type="submit"
          disabled={busy || (withToken ? !token.trim() : !email.trim() || !password)}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
        <Button
          type="button"
          variant="link"
          className="text-muted-foreground h-auto self-center p-0 text-xs"
          onClick={() => {
            setWithToken((on) => !on)
            setError('')
          }}
        >
          {withToken ? 'Sign in with email and password' : 'Use the admin token instead'}
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
  const [status, setStatus] = useState<'checking' | 'signed-out' | 'signed-in' | 'off'>('checking')
  const [email, setEmail] = useState<string | null>(null)
  const [demo, setDemo] = useState(false)
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

  // Who is signed in: a token from the link, or the cookie from signing in.
  const check = useCallback(async () => {
    try {
      const session = await getSession(token)
      setEmail(session.email)
      setDemo(session.demo)
      setStatus('signed-in')
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        // This server was started without the dashboard, as the hosted demo is.
        setStatus('off')
        return
      }
      if (error instanceof ApiError && error.status === 401 && token) {
        storeToken('')
        setToken('')
        setRejected(true)
      } else if (!(error instanceof ApiError)) {
        toast.error('Could not reach the server.')
      }
      setStatus('signed-out')
    }
  }, [token])

  useEffect(() => {
    check()
  }, [check])

  const refresh = useCallback(async () => {
    if (status !== 'signed-in') return
    try {
      setPack(await api.pack())
      setRejected(false)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        storeToken('')
        setToken('')
        setStatus('signed-out')
      } else {
        toast.error('Could not load the pack.')
      }
    }
  }, [api, status])

  const leave = useCallback(async () => {
    try {
      await signOut()
    } catch {
      /* signed out here either way */
    }
    storeToken('')
    setToken('')
    setPack(null)
    setEmail(null)
    setStatus('signed-out')
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // The sidebar shows how many orders and quotes are waiting, refreshed as you move around.
  useEffect(() => {
    if (status !== 'signed-in') return
    api
      .overview()
      .then((stats) => setWaiting(stats.records.waiting))
      .catch(() => {})
  }, [api, status, section])

  useEffect(() => {
    document.title = pack ? `${pack.persona.company} dashboard` : 'Dashboard'
  }, [pack])

  const commit = useCallback(
    async (label: string, work: () => Promise<unknown>) => {
      try {
        await work()
        toast.success(label)
        await refresh()
        // The preview starts a new chat, so it shows the rep as it is now: a chat it
        // carried on would keep the greeting it opened with.
        forgetConversation()
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

  // A blank rep from `hamilton-harness studio` opens on its setup, once.
  const openedSetup = useRef(false)
  useEffect(() => {
    if (!pack || openedSetup.current) return
    openedSetup.current = true
    if (pack.setup_pending) go('setup')
  }, [pack, go])

  // Remounting the section throws its edits away and starts again from the saved pack.
  const discard = useCallback(() => setFormKey((key) => key + 1), [])

  if (status === 'off') {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="bg-card flex w-full max-w-md flex-col gap-4 rounded-2xl border p-6">
          <h1 className="text-2xl">The dashboard is off on this server</h1>
          <p className="text-muted-foreground text-sm">
            The hosted demo cannot save changes, so its dashboard is switched off. Run the server
            yourself with <code>--admin</code> to use it.
          </p>
          <Button asChild variant="outline" className="self-start">
            <a href="/demo">Back to the demo</a>
          </Button>
        </div>
      </div>
    )
  }
  if (status === 'signed-out') {
    return (
      <SignIn
        tokenRejected={rejected}
        onSignedIn={() => {
          setRejected(false)
          check()
        }}
        onToken={(value) => {
          storeToken(value)
          setToken(value)
          setStatus('checking')
        }}
      />
    )
  }
  if (status === 'checking') return <LoadingShell />
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
        {/* Inset: the page sits on the sidebar's surface as a raised, rounded panel. */}
        <Sidebar variant="inset" collapsible="icon">
          <SidebarHeader>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="lg"
                  onClick={() => go('overview')}
                  tooltip={pack.persona.company}
                >
                  {/* A company with no logo, or one that fails to load, gets its initial. */}
                  <Avatar className="rounded-lg after:rounded-lg">
                    {pack.widget.logo && (
                      <AvatarImage
                        src={`/brand/logo?k=${previewKey}`}
                        alt=""
                        className="rounded-lg"
                      />
                    )}
                    <AvatarFallback className="text-foreground rounded-lg font-medium">
                      {pack.persona.company.trim().charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
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
              {!demo && (
                <SidebarMenuItem>
                  <SidebarMenuButton tooltip="Sign out" onClick={leave}>
                    <LogOutIcon />
                    <span className="grid min-w-0 text-left leading-tight">
                      <span>Sign out</span>
                      {email && (
                        <span className="text-muted-foreground truncate text-xs">{email}</span>
                      )}
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarFooter>
          <SidebarRail />
        </Sidebar>

        <SidebarInset className="min-h-0 overflow-hidden">
          <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
            <Breadcrumb>
              <BreadcrumbList className="flex-nowrap whitespace-nowrap">
                <BreadcrumbItem className="hidden lg:block">{active.group}</BreadcrumbItem>
                <BreadcrumbSeparator className="hidden lg:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>{active.entry[1]}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
            <div className="ml-auto flex items-center gap-1.5">
              <span className="text-muted-foreground mr-1 hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs whitespace-nowrap lg:flex">
                <span className="relative flex size-1.5">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-green-500 opacity-60 motion-reduce:hidden" />
                  <span className="relative inline-flex size-1.5 rounded-full bg-green-500" />
                </span>
                Rep is live
              </span>
              {demo && (
                <span
                  title="Look around and run the fake customers. Changes are not saved here."
                  className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-xs whitespace-nowrap text-amber-700 dark:text-amber-300"
                >
                  Read-only demo
                </span>
              )}
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
              <Button
                variant="ghost"
                size="icon"
                className="size-8 md:hidden"
                onClick={() => setMenuOpen(true)}
              >
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
                  <DropdownMenuRadioGroup
                    value={theme}
                    onValueChange={(value) => setTheme(value as Theme)}
                  >
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
            <main
              id="content"
              tabIndex={-1}
              className="relative min-w-0 flex-1 overflow-y-auto outline-none"
            >
              <div className="mx-auto max-w-5xl px-5 pt-8 pb-28 sm:px-8">
                <DiscardContext.Provider value={discard}>
                  {/* Keyed on the section, so each one eases in as it opens. */}
                  <div
                    key={active.entry[0]}
                    className="animate-in fade-in-0 slide-in-from-bottom-2 duration-300 motion-reduce:animate-none"
                  >
                    <Active key={formKey} pack={pack} api={api} commit={commit} go={go} />
                  </div>
                </DiscardContext.Provider>
              </div>
              {/* The open section's unsaved-changes bar is drawn here. */}
              <div
                id="save-slot"
                className="pointer-events-none sticky bottom-5 z-20 flex justify-center px-4 *:pointer-events-auto"
              />
            </main>
            <aside
              className={cn(
                'w-[380px] shrink-0 flex-col border-l',
                showPreview ? 'hidden xl:flex' : 'hidden',
              )}
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
        <CommandMenu
          open={menuOpen}
          setOpen={setMenuOpen}
          groups={NAVIGATION}
          go={go}
          setTheme={setTheme}
        />
        <Toaster position="top-center" theme={dark ? 'dark' : 'light'} />
      </SidebarProvider>
    </TooltipProvider>
  )
}
