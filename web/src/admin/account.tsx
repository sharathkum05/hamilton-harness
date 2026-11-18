// The Account screen: who is signed in, until when, and changing the passcode.

import { useState } from 'react'
import { EyeIcon, EyeOffIcon, LogOutIcon } from 'lucide-react'
import { toast } from 'sonner'

import { changePasscode } from '@/admin/api'
import { Field, ROWS, Section } from '@/admin/fields'
import { useSession } from '@/admin/session'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { sentence } from '@/lib/text'

const MIN = 8

function ends(at: number | null) {
  if (!at) return 'It does not run out: the admin token signs in every request.'
  const when = new Date(at * 1000)
  const tomorrow = new Date(Date.now() + 86_400_000)
  const day =
    when.toDateString() === new Date().toDateString()
      ? 'today'
      : when.toDateString() === tomorrow.toDateString()
        ? 'tomorrow'
        : when.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })
  const time = when.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  return `Until ${day} at ${time}. Sign in again after that.`
}

/** How a new passcode measures up, said plainly. */
function strength(value: string) {
  if (!value) return ''
  if (value.length < MIN) return `Too short: at least ${MIN} characters.`
  if (value.length < 12) return 'Fine. Twelve or more characters is better.'
  return 'Good.'
}

export function AccountSection() {
  const { session, token, signOut } = useSession()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [shown, setShown] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const user = session?.user
  const canChange = Boolean(session?.can_change_passcode)
  const mismatch = again.length > 0 && again !== next
  const ready = current && next.length >= MIN && next === again && !busy

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      await changePasscode(token, current, next)
      toast.success('Passcode changed')
      setCurrent('')
      setNext('')
      setAgain('')
    } catch (failure) {
      setError(failure instanceof Error ? sentence(failure.message) : 'It was not changed.')
    } finally {
      setBusy(false)
    }
  }

  const type = shown ? 'text' : 'password'

  if (session?.demo) {
    return (
      <Section title="Account" description="The admin account that signs in to this dashboard.">
        <Alert>
          <AlertTitle>No account on the public demo</AlertTitle>
          <AlertDescription>
            This dashboard is open to anyone and saves nothing. Run Hamilton yourself to sign in
            with an admin user ID and passcode.
          </AlertDescription>
        </Alert>
      </Section>
    )
  }

  return (
    <Section
      title="Account"
      description="The admin account that signs in to this dashboard. There is one per server; every rep it runs shares it."
    >
      <Card>
        <CardHeader>
          <CardTitle>Signed in</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-5">
          <Avatar className="size-12 rounded-xl after:rounded-xl">
            <AvatarFallback className="rounded-xl text-lg font-medium">
              {(user ?? 'T').charAt(0).toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <p className="truncate font-medium">{user ?? 'Admin token'}</p>
            <p className="text-muted-foreground text-sm">{ends(session?.expires_at ?? null)}</p>
          </div>
          <Button variant="outline" onClick={signOut}>
            <LogOutIcon /> Sign out
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change the passcode</CardTitle>
          <CardDescription>
            The next sign-in needs the new one. Anyone already signed in stays signed in until their
            session runs out.
          </CardDescription>
        </CardHeader>
        {canChange ? (
          <CardContent className={ROWS}>
            <Field label="Current passcode" htmlFor="passcode-current">
              <Input
                id="passcode-current"
                type={type}
                autoComplete="current-password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </Field>
            <Field label="New passcode" htmlFor="passcode-new" hint={strength(next)}>
              <Input
                id="passcode-new"
                type={type}
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
            </Field>
            <Field
              label="New passcode again"
              htmlFor="passcode-again"
              hint={mismatch ? 'The two do not match yet.' : undefined}
            >
              <Input
                id="passcode-again"
                type={type}
                autoComplete="new-password"
                aria-invalid={mismatch}
                value={again}
                onChange={(e) => setAgain(e.target.value)}
              />
            </Field>
            <div className="flex flex-col gap-4 pt-5">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-pressed={shown}
                  onClick={() => setShown((now) => !now)}
                >
                  {shown ? <EyeOffIcon /> : <EyeIcon />} {shown ? 'Hide' : 'Show'} passcodes
                </Button>
                <Button onClick={save} disabled={!ready}>
                  {busy ? 'Changing…' : 'Change passcode'}
                </Button>
              </div>
            </div>
          </CardContent>
        ) : (
          <CardContent>
            <Alert>
              <AlertTitle>Not changed here</AlertTitle>
              <AlertDescription>
                {session?.passcode_note
                  ? sentence(session.passcode_note)
                  : 'This server has no passcode to change.'}
              </AlertDescription>
            </Alert>
          </CardContent>
        )}
      </Card>
    </Section>
  )
}
