import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadConsoleData, mapApiData } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('mapeamento dos DTOs da Read API', () => {
  it('lê os campos aninhados sem exigir aliases do backend', () => {
    const data = mapApiData({
      status: { status: 'ok', api_version: 'v1', mode: 'postgres', synthetic: false },
      activities: [{
        activity_id: 'activity-1', kind: 'DEPOSIT', account_id: 'account-1',
        effective_at: '2026-08-20T10:00:00Z', recorded_at: '2026-08-20T10:01:00Z',
        gross_amount: { amount: '100.00', currency: 'BRL' }, instrument_id: null,
        quantity: null, fee: null, tax: null, cost_basis: null, counter_amount: null,
        related_account_id: null, related_activity_id: null, related_instrument_id: null,
        ratio: null, external_id: null, correction_of: null, is_reversal: false, sequence: 1,
      }],
      observations: [{
        observation_id: 'observation-1', series_id: 'SELIC', value: '13.90', unit: '% a.a.', source: 'BCB',
        times: { effective_at: '2026-08-19T00:00:00Z', observed_at: '2026-08-20T09:00:00Z', available_at: '2026-08-20T11:00:00Z', ingested_at: '2026-08-20T11:01:00Z' },
        vintage_id: 'vintage-1', raw_payload_hash: 'hash', dimensions: [], quality_flags: [],
      }],
      modelRuns: [{
        run_id: 'run-1', created_at: '2026-08-20T12:00:00Z', model_id: 'cash-flow', code_version: '1', environment_fingerprint: 'env', dataset_fingerprint: 'dataset-1', policy_id: 'policy', policy_version: 1, universe_id: 'universe', universe_version: 1, parameters: [], random_seed: 42,
        solver: { solver_id: 'solver', version: '1.0', tolerances: [], capabilities: [] },
        candidate: { model_id: 'cash-flow', weights: [], expected_return: 0, volatility: 0, solver_status: 'ok', diagnostics: [] },
        validated: true, violations: [],
      }],
      decisionPackets: [{
        packet_id: 'packet-1', created_at: '2026-08-20T12:30:00Z', policy_id: 'policy', policy_version: 1,
        model_run_ids: ['run-1'], evidence_ids: ['observation-1'],
        alternatives: [{ alternative_id: 'no_action', trades: [], projected_weights: [], unallocated_cash: { amount: '100.00', currency: 'BRL' }, turnover: '0', feasible: true, reasons: [] }],
        shadow_request_id: null, knowledge_cutoff: null,
      }],
    })

    expect(data.status).toMatchObject({ mode: 'postgres', synthetic: false, persistence: 'PostgreSQL append-only' })
    expect(data.activities[0]).toMatchObject({ amount: '100.00', currency: 'BRL' })
    expect(data.observations[0].available_at).toBe('2026-08-20T11:00:00Z')
    expect(data.modelRuns[0]).toMatchObject({ dataset_id: 'dataset-1', solver: 'solver/1.0', status: 'validated' })
    expect(data.decisionPackets[0]).toMatchObject({ action: 'NO_ACTION disponível', status: 'pronto para revisão' })
  })

  it('envia bearer somente em memória e desabilita cache e cookies da Read API', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    })
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'ok', api_version: 'v1', mode: 'postgres', synthetic: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await loadConsoleData('http', 'transient-token')

    expect(fetchMock).toHaveBeenCalledTimes(5)
    for (const [, init] of fetchMock.mock.calls) {
      expect(init).toMatchObject({
        cache: 'no-store',
        credentials: 'omit',
        headers: { Accept: 'application/json', Authorization: 'Bearer transient-token' },
      })
    }
    expect(localStorage).toHaveLength(0)
    expect(sessionStorage).toHaveLength(0)
  })
})
