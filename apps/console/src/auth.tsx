import { createAuthClient, createInternalNeonAuth } from '@neondatabase/auth'
import { BetterAuthReactAdapter } from '@neondatabase/auth/react/adapters'
import { NeonAuthUIProvider } from '@neondatabase/auth/react/ui'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import type { AnchorHTMLAttributes, ReactNode } from 'react'

export type ConsoleAuthMode = 'public' | 'private'

export function configuredAuthMode(): ConsoleAuthMode {
  return import.meta.env.VITE_AUTH_MODE === 'private' ? 'private' : 'public'
}

const neonAuthUrl = (import.meta.env.VITE_NEON_AUTH_URL ?? '').trim()

function createReactAuthClient(url: string) {
  return createAuthClient(url, { adapter: BetterAuthReactAdapter() })
}

type ReactAuthClient = ReturnType<typeof createReactAuthClient>

const neonAuth = neonAuthUrl
  ? createInternalNeonAuth(neonAuthUrl, { adapter: BetterAuthReactAdapter() })
  : null

export const authClient = (neonAuth?.adapter as ReactAuthClient | undefined) ?? null

export async function resolveBearerToken(
  getJWTToken: () => Promise<string | null>,
): Promise<string | null> {
  const token = (await getJWTToken())?.trim()
  return token || null
}

export async function getApiBearerToken(): Promise<string | null> {
  if (!neonAuth) return null
  return resolveBearerToken(neonAuth.getJWTToken)
}

function Link({ href, ...props }: { href: string } & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <RouterLink to={href} {...props} />
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  if (!authClient || configuredAuthMode() === 'public') return children

  return (
    <NeonAuthUIProvider
      authClient={authClient}
      navigate={(path) => navigate(path)}
      replace={(path) => navigate(path, { replace: true })}
      Link={Link}
    >
      {children}
    </NeonAuthUIProvider>
  )
}
