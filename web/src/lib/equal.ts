// Structural equality for request objects (used to detect "settings changed since last run").

/** JSON with object keys sorted, so key order never affects equality or cache keys. */
export function stableStringify(value: unknown): string {
  return JSON.stringify(value, (_key, inner: unknown) => {
    if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
      return Object.fromEntries(
        Object.entries(inner as Record<string, unknown>)
          .filter(([, v]) => v !== undefined)
          .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)),
      )
    }
    return inner
  })
}

export function sameRequest(a: unknown, b: unknown): boolean {
  return stableStringify(a) === stableStringify(b)
}
