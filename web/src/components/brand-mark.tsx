import { cn } from '@/lib/utils'

/** H squared: the two H's of Hamilton Harness. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'bg-foreground text-background font-heading inline-flex size-7 shrink-0 items-start justify-center rounded-lg pt-1 text-base leading-none',
        className,
      )}
    >
      H<sup className="-ml-px text-[0.55em] leading-none">2</sup>
    </span>
  )
}
