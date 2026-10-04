// The dashboard shell: a token gate, the navigation, the open section and a
// live preview of the chat as customers will see it.

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ComponentType } from 'react'
import {
  BookOpenIcon,
  CodeIcon,
  FlaskConicalIcon,
  MessagesSquareIcon,
  MicIcon,
  PaletteIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  TargetIcon,
  UserRoundCheckIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import { adminApi, loadToken, storeToken } from '@/admin/api'
import type { Pack } from '@/admin/api'
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
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'

const SECTIONS: [string, string, ComponentType<{ className?: string }>, ComponentType<SectionProps>][] = [
  ['brand', 'Brand', PaletteIcon, BrandSection],
  ['voice', 'Voice', MicIcon, VoiceSection],
  ['scope', 'Scope', TargetIcon, ScopeSection],
  ['knowledge', 'Knowledge', BookOpenIcon, KnowledgeSection],
  ['rules', 'Rules', ShieldCheckIcon, RulesSection],
  ['handoff', 'Handoff', UserRoundCheckIcon, HandoffSection],
  ['test', 'Test', FlaskConicalIcon, TestSection],
  ['conversations', 'Conversations', MessagesSquareIcon, ConversationsSection],
  ['install', 'Install', CodeIcon, InstallSection],
]

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
  const [section, setSection] = useState(() => window.location.hash.slice(1) || 'brand')
  const [previewKey, setPreviewKey] = useState(0)
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

  const Active = (SECTIONS.find(([key]) => key === section) ?? SECTIONS[0])[3]

  return (
    <TooltipProvider>
      <div className="bg-background flex h-full flex-col md:flex-row">
        <aside className="bg-sidebar flex shrink-0 flex-col gap-4 border-b p-3 md:w-56 md:border-r md:border-b-0 md:p-4">
          <div className="flex items-center gap-2.5 px-1">
            <div className="bg-muted ring-border size-8 shrink-0 overflow-hidden rounded-full ring-1">
              {pack.widget.logo && (
                <img src={`/brand/logo?k=${previewKey}`} alt="" className="size-full object-cover" />
              )}
            </div>
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-medium">{pack.persona.company}</span>
              <span className="text-muted-foreground truncate text-xs">
                {pack.persona.name} · {pack.persona.role}
              </span>
            </div>
          </div>
          <nav aria-label="Dashboard sections" className="flex gap-1 overflow-x-auto md:flex-col">
            {SECTIONS.map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => go(key)}
                aria-current={section === key ? 'page' : undefined}
                className={cn(
                  'flex shrink-0 items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm',
                  section === key
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                    : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
                )}
              >
                <Icon className="size-4" />
                {label}
              </button>
            ))}
          </nav>
        </aside>

        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-5 py-8">
            <Active pack={pack} api={api} commit={commit} />
          </div>
        </main>

        <aside className="hidden w-[400px] shrink-0 flex-col border-l xl:flex">
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <span className="text-sm font-medium">Live preview</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPreviewKey((key) => key + 1)}
            >
              <RefreshCwIcon /> Restart
            </Button>
          </div>
          <iframe
            key={previewKey}
            title="Chat preview"
            src="/chat?nopacing&preview"
            className="min-h-0 flex-1"
          />
        </aside>
      </div>
      <Toaster position="bottom-center" />
    </TooltipProvider>
  )
}
