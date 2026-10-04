// Turn a pack's brand settings into the CSS variables the components read.

import type { WidgetSettings } from '@/lib/api'

function channels(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [number, number, number]
}

/** Black or white, whichever reads better on the colour. */
export function inkFor(hex: string): string {
  const linear = (c: number) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  const [r, g, b] = channels(hex)
  const luminance = 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
  return luminance > 0.4 ? '#18181b' : '#ffffff'
}

/** Blend a colour toward white. amount 0 is the colour, 1 is white. */
export function tint(hex: string, amount: number): string {
  const mixed = channels(hex).map((c) => Math.round(c + (255 - c) * amount))
  return `#${mixed.map((c) => c.toString(16).padStart(2, '0')).join('')}`
}

/** The two colours of the orb, drawn from the brand's accent. */
export function orbColors(accent: string): [string, string] {
  return [tint(accent, 0.72), tint(accent, 0.38)]
}

const RADIUS = { sharp: '0.2rem', soft: '0.625rem', round: '1.1rem' }

const FONTS = {
  system: "'Geist Variable', system-ui, sans-serif",
  serif: "Georgia, 'Iowan Old Style', 'Times New Roman', serif",
  rounded: "ui-rounded, 'SF Pro Rounded', 'Nunito', system-ui, sans-serif",
  mono: "ui-monospace, 'SF Mono', Menlo, Consolas, monospace",
}

/** Apply the brand to the document. Returns a function that undoes the theme listener. */
export function applyBrand(widget: WidgetSettings): () => void {
  const root = document.documentElement
  root.style.setProperty('--primary', widget.accent)
  root.style.setProperty('--primary-foreground', inkFor(widget.accent))
  root.style.setProperty('--ring', widget.accent)
  root.style.setProperty('--radius', RADIUS[widget.corners])
  root.style.setProperty('--font-sans', FONTS[widget.font])

  const system = window.matchMedia('(prefers-color-scheme: dark)')
  const sync = () => {
    const dark = widget.theme === 'dark' || (widget.theme === 'auto' && system.matches)
    root.classList.toggle('dark', dark)
  }
  sync()
  system.addEventListener('change', sync)
  return () => system.removeEventListener('change', sync)
}
