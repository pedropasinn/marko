import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

describe('fontes do console', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('identifica dados sintéticos de forma persistente', async () => {
    render(<App dataMode="synthetic" />)

    expect(await screen.findByText('Dados sintéticos')).toBeVisible()
    expect(screen.getByText(/Nenhum registro representa uma pessoa/)).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Acompanhe o que aconteceu, com cada passo explicado.' })).toBeVisible()
    expect(screen.getByText('DecisionPackets')).toBeVisible()
  })

  it('expõe a indisponibilidade HTTP sem fallback sintético', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    render(<App dataMode="http" />)

    expect(await screen.findByRole('heading', { name: 'Fonte indisponível' })).toBeVisible()
    expect(screen.getByText(/não substituiu a resposta HTTP/)).toBeVisible()
    expect(screen.queryByText('Dados sintéticos')).not.toBeInTheDocument()
    expect(screen.getAllByText('HTTP 503')).toHaveLength(5)
  })

  it('mantém o modo sintético público mesmo quando o auth privado foi solicitado', async () => {
    render(<App dataMode="synthetic" authMode="private" />)

    expect(await screen.findByText('Dados sintéticos')).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Autenticação necessária' })).not.toBeInTheDocument()
  })

  it('bloqueia o modo privado sem URL do Neon Auth', () => {
    render(<App dataMode="http" authMode="private" />)

    expect(screen.getByRole('heading', { name: 'Acesso privado bloqueado' })).toBeVisible()
    expect(screen.getByText(/VITE_NEON_AUTH_URL/)).toBeVisible()
  })
})
