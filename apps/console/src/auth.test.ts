import { describe, expect, it } from 'vitest'
import { resolveBearerToken } from './auth'

describe('credencial da Read API', () => {
  it('usa somente o JWT retornado pela API oficial do Neon Auth', async () => {
    const calls: string[] = []

    const token = await resolveBearerToken(async () => {
      calls.push('getJWTToken')
      return '  signed-jwt  '
    })

    expect(token).toBe('signed-jwt')
    expect(calls).toEqual(['getJWTToken'])
    expect(localStorage).toHaveLength(0)
    expect(sessionStorage).toHaveLength(0)
  })

  it('falha fechado quando o Neon Auth não fornece JWT', async () => {
    await expect(resolveBearerToken(async () => null)).resolves.toBeNull()
    await expect(resolveBearerToken(async () => '   ')).resolves.toBeNull()
  })
})
