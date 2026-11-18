// Who is signed in to the dashboard, for the screens that show it.

import { createContext, useContext } from 'react'

import type { AdminSession } from '@/admin/api'

export type SessionState = {
  session: AdminSession | null
  // The admin token in use, when the session came from one; '' when it came from signing in.
  token: string
  signOut: () => void
}

export const SessionContext = createContext<SessionState>({
  session: null,
  token: '',
  signOut: () => {},
})

export const useSession = () => useContext(SessionContext)
