import clsx from 'clsx'
import { NavLink } from 'react-router'

/** Sub-page navigation rendered as an underline tab bar (links, so each tab is addressable). */
export function RouteTabs({
  label,
  tabs,
}: {
  label: string
  tabs: Array<{ to: string; label: string; end?: boolean }>
}) {
  return (
    <nav aria-label={label} className="-mb-px flex gap-1 overflow-x-auto">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            clsx(
              'relative px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors',
              isActive
                ? 'text-ink after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-accent'
                : 'text-muted hover:text-ink',
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
