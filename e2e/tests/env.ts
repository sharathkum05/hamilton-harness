// Addresses and the throwaway login the end-to-end tests run with.

export const HAMILTON_PORT = 8900
export const SITE_PORT = 8910
export const PHP_PORT = 8911

export const HAMILTON = `http://127.0.0.1:${HAMILTON_PORT}`
export const SITE = `http://127.0.0.1:${SITE_PORT}`
export const PHP = `http://127.0.0.1:${PHP_PORT}`

// Only ever used against the local test server, which these tests start themselves.
export const ADMIN = {
  token: 'e2e-admin-token-not-a-secret',
  email: 'interviewer@example.com',
  password: 'e2e-password-not-a-secret',
  identitySecret: 'e2e-identity-secret',
}
