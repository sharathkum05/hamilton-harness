// A command menu on Cmd+K or Ctrl+K: jump to any section or run an action
// without reaching for the sidebar.

import { useEffect } from 'react'
import type { ComponentType } from 'react'
import { ExternalLinkIcon, MonitorIcon, MoonIcon, PlayIcon, SunIcon } from 'lucide-react'

import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import type { Theme } from '@/lib/theme'

type Icon = ComponentType<{ className?: string }>

export function CommandMenu({
  open,
  setOpen,
  groups,
  go,
  setTheme,
}: {
  open: boolean
  setOpen: (open: boolean) => void
  groups: [string, [string, string, Icon][]][]
  go: (section: string) => void
  setTheme: (theme: Theme) => void
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen(!open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, setOpen])

  const run = (action: () => void) => {
    setOpen(false)
    action()
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="Command menu"
      description="Jump to a section or run an action"
    >
      {/* The dialog is only a frame. The input and list need this root around them to work. */}
      <Command>
        <CommandInput placeholder="Go to a section or run an action" />
        <CommandList>
          <CommandEmpty>Nothing matches.</CommandEmpty>
          {groups.map(([group, entries]) => (
            <CommandGroup key={group} heading={group}>
              {entries.map(([key, label, Icon]) => (
                <CommandItem
                  key={key}
                  value={`${group} ${label}`}
                  onSelect={() => run(() => go(key))}
                >
                  <Icon />
                  {label}
                </CommandItem>
              ))}
            </CommandGroup>
          ))}
          <CommandSeparator />
          <CommandGroup heading="Actions">
            <CommandItem value="run fake customers tests" onSelect={() => run(() => go('test'))}>
              <PlayIcon />
              Run the fake customers
            </CommandItem>
            <CommandItem
              value="open demo"
              onSelect={() => run(() => window.open('/demo', '_blank', 'noreferrer'))}
            >
              <ExternalLinkIcon />
              Open the demo
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Theme">
            <CommandItem value="theme light" onSelect={() => run(() => setTheme('light'))}>
              <SunIcon />
              Light
            </CommandItem>
            <CommandItem value="theme dark" onSelect={() => run(() => setTheme('dark'))}>
              <MoonIcon />
              Dark
            </CommandItem>
            <CommandItem value="theme system device" onSelect={() => run(() => setTheme('system'))}>
              <MonitorIcon />
              Follow this device
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
