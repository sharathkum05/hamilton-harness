// The dashboard's sign-in screen: the admin user ID and passcode the server
// printed when it started, or the admin token instead.

import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import {
  EyeIcon,
  EyeOffIcon,
  KeyRoundIcon,
  LockKeyholeIcon,
  ShieldCheckIcon,
  UserRoundIcon,
  WorkflowIcon,
} from 'lucide-react'

import { signIn } from '@/admin/api'
import { BrandMark } from '@/components/brand-mark'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from '@/components/ui/input-group'
import { Label } from '@/components/ui/label'
import { sentence } from '@/lib/text'

const POINTS: [typeof WorkflowIcon, string][] = [
  [WorkflowIcon, 'Change the rep without code, and watch a message travel through it.'],
  [ShieldCheckIcon, 'Every change is checked before it is saved, and rolled back if it breaks.'],
  [KeyRoundIcon, 'Signing in lasts 12 hours. The passcode is kept only as a hash.'],
]

export function SignIn({
  onSignedIn,
  onToken,
  tokenRejected,
}: {
  onSignedIn: () => void
  onToken: (token: string) => void
  tokenRejected: boolean
}) {
  const [withToken, setWithToken] = useState(tokenRejected)
  const [user, setUser] = useState('')
  const [passcode, setPasscode] = useState('')
  const [token, setToken] = useState('')
  const [shown, setShown] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const [error, setError] = useState(tokenRejected ? 'That token was not accepted.' : '')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (withToken) {
      onToken(token.trim())
      return
    }
    setBusy(true)
    setError('')
    try {
      await signIn(user.trim(), passcode)
      onSignedIn()
    } catch (failure) {
      setError(failure instanceof Error ? sentence(failure.message) : 'Could not sign in.')
      setPasscode('')
    } finally {
      setBusy(false)
    }
  }

  const watchCaps = (event: KeyboardEvent<HTMLInputElement>) =>
    setCapsLock(event.getModifierState('CapsLock'))

  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      {/* The brand side: who this is for, and what signing in opens. */}
      <div className="bg-sidebar hidden flex-col justify-between border-r p-12 lg:flex">
        <div className="flex items-center gap-3">
          <BrandMark className="size-9 rounded-lg text-base" />
          <span className="font-heading text-xl">Hamilton</span>
        </div>
        <div className="flex max-w-md flex-col gap-8">
          <h2 className="font-heading text-4xl leading-tight text-balance">
            The dashboard for your AI rep.
          </h2>
          <ul className="flex flex-col gap-5">
            {POINTS.map(([Icon, text]) => (
              <li key={text} className="text-muted-foreground flex gap-3 text-sm leading-relaxed">
                <Icon className="text-foreground mt-0.5 size-4 shrink-0" />
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-muted-foreground text-xs">Hamilton Harness</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <form
          className="flex w-full max-w-sm flex-col gap-6"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          <div className="flex flex-col gap-2">
            <BrandMark className="size-9 rounded-lg text-base lg:hidden" />
            <h1 className="text-2xl">Sign in to the dashboard</h1>
            <p className="text-muted-foreground text-sm text-pretty">
              {withToken
                ? 'Paste the admin token the server printed when it started.'
                : 'Use the admin user ID and passcode the server printed when it started.'}
            </p>
          </div>

          {withToken ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor="admin-token">Admin token</Label>
              <InputGroup>
                <InputGroupAddon>
                  <KeyRoundIcon />
                </InputGroupAddon>
                <InputGroupInput
                  id="admin-token"
                  type="password"
                  autoComplete="off"
                  autoFocus
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                />
              </InputGroup>
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                <Label htmlFor="admin-user">User ID</Label>
                <InputGroup>
                  <InputGroupAddon>
                    <UserRoundIcon />
                  </InputGroupAddon>
                  <InputGroupInput
                    id="admin-user"
                    autoComplete="username"
                    autoCapitalize="none"
                    spellCheck={false}
                    autoFocus
                    placeholder="admin"
                    value={user}
                    onChange={(e) => setUser(e.target.value)}
                  />
                </InputGroup>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="admin-passcode">Passcode</Label>
                <InputGroup>
                  <InputGroupAddon>
                    <LockKeyholeIcon />
                  </InputGroupAddon>
                  <InputGroupInput
                    id="admin-passcode"
                    type={shown ? 'text' : 'password'}
                    autoComplete="current-password"
                    spellCheck={false}
                    value={passcode}
                    onChange={(e) => setPasscode(e.target.value)}
                    onKeyDown={watchCaps}
                    onKeyUp={watchCaps}
                  />
                  <InputGroupAddon align="inline-end">
                    <InputGroupButton
                      size="icon-xs"
                      aria-label={shown ? 'Hide passcode' : 'Show passcode'}
                      aria-pressed={shown}
                      onClick={() => {
                        setShown((now) => !now)
                        // Back to the box, so Enter signs in rather than pressing this again.
                        document.getElementById('admin-passcode')?.focus()
                      }}
                    >
                      {shown ? <EyeOffIcon /> : <EyeIcon />}
                    </InputGroupButton>
                  </InputGroupAddon>
                </InputGroup>
                {capsLock && (
                  <p className="text-muted-foreground text-xs" role="status">
                    Caps Lock is on.
                  </p>
                )}
              </div>
            </>
          )}

          {error && (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Button
            type="submit"
            disabled={busy || (withToken ? !token.trim() : !user.trim() || !passcode)}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
          <Button
            type="button"
            variant="link"
            className="text-muted-foreground h-auto self-center p-0 text-xs"
            onClick={() => {
              setWithToken((on) => !on)
              setError('')
            }}
          >
            {withToken ? 'Sign in with the user ID and passcode' : 'Use the admin token instead'}
          </Button>
        </form>
      </div>
    </div>
  )
}
