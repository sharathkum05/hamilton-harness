// Which conversation this browser tab is in, so a reload carries on with it.

const STORAGE_KEY = 'hamilton:conversation'

export function remembered(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

/** Start the next chat afresh, for when the rep it would continue has been rebuilt. */
export function forgetConversation() {
  remember(null)
}

export function remember(id: string | null) {
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* a private window may refuse storage; the chat still works for this view */
  }
}
