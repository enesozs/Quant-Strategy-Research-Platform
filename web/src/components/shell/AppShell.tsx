import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { Icon, type IconName } from '@/components/ui/Icon'
import { useTheme } from '@/theme/theme'
import { SidebarSlotContext } from './sidebarSlot'

const NAV: Array<{ to: string; label: string; icon: IconName; blurb: string }> = [
  { to: '/compare', label: 'Compare', icon: 'compare', blurb: 'All strategies, one sample' },
  { to: '/backtest', label: 'Backtest', icon: 'backtest', blurb: 'One strategy in depth' },
  { to: '/optimize', label: 'Optimize', icon: 'optimize', blurb: 'Parameter surfaces' },
  { to: '/validate', label: 'Validate', icon: 'validate', blurb: 'Out-of-sample tests' },
  { to: '/pairs', label: 'Pairs', icon: 'pairs', blurb: 'Relative value' },
  { to: '/guide', label: 'Guide', icon: 'guide', blurb: 'Strategy library' },
]

function ApiStatus() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: false,
  })
  const ok = health.isSuccess
  const label = health.isPending ? 'Connecting…' : ok ? 'API connected' : 'API unreachable'
  return (
    <div className="flex items-center gap-2 text-xs text-muted" role="status">
      <span
        className={clsx(
          'size-1.5 rounded-full',
          health.isPending ? 'bg-muted' : ok ? 'bg-pos' : 'bg-neg',
        )}
      />
      {label}
    </div>
  )
}

function ThemeToggle({ compact }: { compact?: boolean }) {
  const { theme, toggle } = useTheme()
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className={clsx(
        'inline-flex items-center gap-2 rounded-lg text-sm text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink',
        compact ? 'size-9 justify-center' : 'h-8 px-2',
      )}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
      {!compact && <span>{theme === 'dark' ? 'Light theme' : 'Dark theme'}</span>}
    </button>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-7 place-items-center rounded-lg bg-accent text-accent-ink">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M2 11.5 5.5 7l3 2.5L14 3"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight text-ink">Strategy Lab</p>
        <p className="text-[11px] text-muted">Quant research platform</p>
      </div>
    </div>
  )
}

function NavItems({ onNavigate, compact }: { onNavigate?: () => void; compact?: boolean }) {
  return (
    <ul className="space-y-0.5">
      {NAV.map((item) => (
        <li key={item.to}>
          <NavLink
            to={item.to}
            onClick={onNavigate}
            title={compact ? item.blurb : undefined}
            className={({ isActive }) =>
              clsx(
                'group flex items-center gap-3 rounded-lg px-2.5 text-sm transition-colors',
                compact ? 'py-1.5' : 'py-2',
                isActive
                  ? 'bg-accent-soft font-medium text-ink'
                  : 'text-ink-2 hover:bg-surface-2 hover:text-ink',
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  name={item.icon}
                  className={clsx(
                    'shrink-0',
                    isActive ? 'text-accent' : 'text-muted group-hover:text-ink-2',
                  )}
                />
                <span className="min-w-0">
                  <span className="block">{item.label}</span>
                  {!compact && (
                    <span className="block truncate text-[11px] font-normal text-muted">
                      {item.blurb}
                    </span>
                  )}
                </span>
              </>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

export function AppShell() {
  const [open, setOpen] = useState(false)
  // Element the active page portals its settings panel into (desktop only).
  const [settingsSlot, setSettingsSlot] = useState<HTMLElement | null>(null)
  const location = useLocation()

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [location.pathname])

  return (
    <div className="min-h-dvh lg:pl-[312px]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      {/* Pinned to the viewport on every page, independent of page height and scroll. */}
      {/* Below the navigation sits the active page's settings panel, so results get the full */}
      {/* width of the page. Only the settings scroll; the Run button stays pinned. */}
      <div className="fixed inset-y-0 left-0 z-20 hidden w-[312px] border-r border-line bg-surface lg:block">
        <aside className="flex h-full flex-col overflow-y-auto px-3 py-4">
          <div className="px-1.5 pb-4">
            <Brand />
          </div>
          <nav aria-label="Main" className="shrink-0">
            <NavItems compact />
          </nav>
          <div ref={setSettingsSlot} className="mt-3 flex min-h-0 flex-1 flex-col" />
          <div className="flex items-center justify-between gap-2 border-t border-line px-1.5 pt-3">
            <ThemeToggle />
            <ApiStatus />
          </div>
        </aside>
      </div>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-bg/85 px-4 backdrop-blur lg:hidden">
        <Brand />
        <div className="flex items-center gap-1">
          <ThemeToggle compact />
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
            aria-expanded={open}
            aria-controls="mobile-nav"
            className="grid size-9 place-items-center rounded-lg text-ink-2 hover:bg-surface-2"
          >
            <Icon name="menu" size={18} />
          </button>
        </div>
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
          />
          <div
            id="mobile-nav"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col border-l border-line bg-surface p-4"
          >
            <div className="mb-4 flex items-center justify-between">
              <Brand />
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation"
                className="grid size-9 place-items-center rounded-lg text-ink-2 hover:bg-surface-2"
                autoFocus
              >
                <Icon name="close" />
              </button>
            </div>
            <nav aria-label="Main" className="flex-1">
              <NavItems onNavigate={() => setOpen(false)} />
            </nav>
            <div className="border-t border-line pt-3">
              <ApiStatus />
            </div>
          </div>
        </div>
      )}

      <main id="main" className="min-w-0">
        <SidebarSlotContext.Provider value={settingsSlot}>
          <Outlet />
        </SidebarSlotContext.Provider>
      </main>
    </div>
  )
}
