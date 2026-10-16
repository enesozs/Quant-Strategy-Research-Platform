// The desktop sidebar hosts the active page's settings panel below the navigation. The shell
// owns the slot element; research pages portal their panel into it on wide screens.

import { createContext, useContext, useSyncExternalStore } from 'react'

export const SidebarSlotContext = createContext<HTMLElement | null>(null)

/** True for content rendered inside the sidebar slot, so panels can drop their card chrome. */
export const InSidebarContext = createContext(false)

export const useSidebarSlot = () => useContext(SidebarSlotContext)
export const useInSidebar = () => useContext(InSidebarContext)

// Matches Tailwind's `lg` breakpoint, where the sidebar is shown.
const DESKTOP_QUERY = '(min-width: 1024px)'

function subscribe(onChange: () => void) {
  const query = window.matchMedia(DESKTOP_QUERY)
  query.addEventListener('change', onChange)
  return () => query.removeEventListener('change', onChange)
}

export function useIsDesktop() {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(DESKTOP_QUERY).matches,
    () => false,
  )
}
