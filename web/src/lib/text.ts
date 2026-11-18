// Small helpers for text shown to people.

/** The server's reasons are written in lower case for logs; shown here as a sentence. */
export function sentence(message: string) {
  const text = message.charAt(0).toUpperCase() + message.slice(1)
  return /[.!?]$/.test(text) ? text : `${text}.`
}
