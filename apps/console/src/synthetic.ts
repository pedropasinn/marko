import type { ConsoleData } from './types'

export const syntheticData: ConsoleData = {
  status: {
    service: 'marko-api',
    state: 'read_only',
    version: '0.4.0-shadow',
    as_of: '2026-08-20T13:00:00Z',
    persistence: 'append-only',
    limitations: ['Ciclo shadow sem capital real', 'Amostra sintética para inspeção visual'],
    synthetic: true,
    mode: 'local',
  },
  activities: [
    { activity_id: 'act-00041', kind: 'DEPOSIT', account_id: 'custody-main', effective_at: '2026-08-18T13:00:00Z', recorded_at: '2026-08-18T13:01:12Z', amount: '12500.00', currency: 'BRL', source: 'ledger' },
    { activity_id: 'act-00042', kind: 'BUY', account_id: 'custody-main', effective_at: '2026-08-19T14:30:00Z', recorded_at: '2026-08-19T14:30:09Z', amount: '4820.00', currency: 'BRL', instrument_id: 'B5P211', source: 'ledger' },
    { activity_id: 'act-00043', kind: 'FEE', account_id: 'custody-main', effective_at: '2026-08-19T14:30:00Z', recorded_at: '2026-08-19T14:30:09Z', amount: '4.90', currency: 'BRL', source: 'ledger' },
  ],
  observations: [
    { observation_id: 'obs-selic-0820', series_id: 'SELIC', value: '13.90', unit: '% a.a.', effective_at: '2026-08-20T00:00:00Z', available_at: '2026-08-20T12:15:00Z', vintage_id: 'bcb-20260820', source: 'BCB SGS' },
    { observation_id: 'obs-ipca-0731', series_id: 'IPCA', value: '0.31', unit: '% a.m.', effective_at: '2026-07-31T00:00:00Z', available_at: '2026-08-12T12:00:00Z', vintage_id: 'sidra-20260812', source: 'IBGE SIDRA' },
    { observation_id: 'obs-cdi-0819', series_id: 'CDI', value: '13.65', unit: '% a.a.', effective_at: '2026-08-19T00:00:00Z', available_at: '2026-08-20T10:00:00Z', vintage_id: 'b3-20260820', source: 'B3' },
  ],
  modelRuns: [
    { run_id: 'run-cf-0088', model: 'cash_flow_only', created_at: '2026-08-20T12:35:18Z', dataset_id: 'vintage-20260820-1200', solver: 'deterministic-baseline/1.0', status: 'validated', limitations: ['Sem estimação de retorno esperado', 'Custos tributários não otimizados'] },
  ],
  decisionPackets: [
    { packet_id: 'dp-20260820-01', created_at: '2026-08-20T12:42:03Z', action: 'NO_ACTION', model_run_ids: ['run-cf-0088'], evidence_ids: ['obs-selic-0820', 'obs-ipca-0731', 'obs-cdi-0819'], status: 'shadow_ready', limitations: ['Requer revisão humana', 'Execução de capital bloqueada'] },
  ],
}
