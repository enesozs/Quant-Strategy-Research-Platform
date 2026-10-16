// A tiny module-level store so page state (form values, last run) survives navigation.
// Each key holds one value; components subscribe with useSyncExternalStore.

import { useCallback, useSyncExternalStore } from 'react'

const values = new Map<string, unknown>()
const listeners = new Map<string, Set<() => void>>()

function emit(key: string) {
  listeners.get(key)?.forEach((listener) => listener())
}

export function getStoreValue<T>(key: string, initial: T | (() => T)): T {
  if (!values.has(key)) {
    values.set(key, typeof initial === 'function' ? (initial as () => T)() : initial)
  }
  return values.get(key) as T
}

export function setStoreValue<T>(key: string, next: T | ((previous: T) => T)) {
  const previous = values.get(key) as T
  const value = typeof next === 'function' ? (next as (p: T) => T)(previous) : next
  if (Object.is(value, previous)) return
  values.set(key, value)
  emit(key)
}

function subscribe(key: string, listener: () => void) {
  let set = listeners.get(key)
  if (!set) {
    set = new Set()
    listeners.set(key, set)
  }
  set.add(listener)
  return () => {
    set.delete(listener)
  }
}

export type Setter<T> = (next: T | ((previous: T) => T)) => void

/** Like useState, but the value lives outside React and outlives the component. */
export function usePageState<T>(key: string, initial: T | (() => T)): [T, Setter<T>] {
  const value = useSyncExternalStore(
    useCallback((listener) => subscribe(key, listener), [key]),
    () => getStoreValue(key, initial),
  )
  const set = useCallback<Setter<T>>((next) => setStoreValue(key, next), [key])
  return [value, set]
}

/** Patch helper for object-shaped page state. */
export function usePatch<T extends object>(set: Setter<T>) {
  return useCallback(
    <K extends keyof T>(field: K, value: T[K]) =>
      set((previous) => ({ ...previous, [field]: value })),
    [set],
  )
}
