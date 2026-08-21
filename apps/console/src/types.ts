export type DataMode = 'http' | 'synthetic'

export interface StatusSnapshot {
  service: string
  state: string
  version: string
  as_of: string
  persistence: string
  limitations: string[]
  synthetic: boolean
  mode: string
}

export interface Activity {
  activity_id: string
  kind: string
  account_id: string
  effective_at: string
  recorded_at: string
  amount?: string
  currency?: string
  instrument_id?: string
  source: string
}

export interface Observation {
  observation_id: string
  series_id: string
  value: string
  unit: string
  effective_at: string
  available_at: string
  vintage_id: string
  source: string
}

export interface ModelRun {
  run_id: string
  model: string
  created_at: string
  dataset_id: string
  solver: string
  status: string
  limitations: string[]
}

export interface DecisionPacket {
  packet_id: string
  created_at: string
  action: string
  model_run_ids: string[]
  evidence_ids: string[]
  status: string
  limitations: string[]
  shadow_request_id?: string
  knowledge_cutoff?: string
}

export interface ConsoleData {
  status: StatusSnapshot
  activities: Activity[]
  observations: Observation[]
  modelRuns: ModelRun[]
  decisionPackets: DecisionPacket[]
}

export interface MoneyDTO { amount: string; currency: string }
export interface PairDTO { key: string; value: string }
export interface StatusDTO { status: string; api_version: string; mode: string; synthetic: boolean }
export interface ActivityDTO {
  activity_id: string
  kind: string
  account_id: string
  effective_at: string
  recorded_at: string
  gross_amount: MoneyDTO | null
  instrument_id: string | null
  quantity: string | null
  fee: MoneyDTO | null
  tax: MoneyDTO | null
  cost_basis: MoneyDTO | null
  counter_amount: MoneyDTO | null
  related_account_id: string | null
  related_activity_id: string | null
  related_instrument_id: string | null
  ratio: string | null
  external_id: string | null
  correction_of: string | null
  is_reversal: boolean
  sequence: number
}
export interface ObservationDTO {
  observation_id: string
  series_id: string
  value: string
  unit: string
  source: string
  times: { effective_at: string; observed_at: string; available_at: string; ingested_at: string }
  vintage_id: string
  raw_payload_hash: string
  dimensions: PairDTO[]
  quality_flags: string[]
}
export interface ModelRunDTO {
  run_id: string
  created_at: string
  model_id: string
  code_version: string
  environment_fingerprint: string
  dataset_fingerprint: string
  policy_id: string
  policy_version: number
  universe_id: string
  universe_version: number
  parameters: PairDTO[]
  random_seed: number
  solver: { solver_id: string; version: string; tolerances: PairDTO[]; capabilities: string[] }
  candidate: { model_id: string; weights: { asset_id: string; weight: number }[]; expected_return: number; volatility: number; solver_status: string; diagnostics: PairDTO[] }
  validated: boolean
  violations: string[]
}
export interface DecisionPacketDTO {
  packet_id: string
  created_at: string
  policy_id: string
  policy_version: number
  model_run_ids: string[]
  evidence_ids: string[]
  alternatives: { alternative_id: string; trades: unknown[]; projected_weights: unknown[]; unallocated_cash: MoneyDTO; turnover: string; feasible: boolean; reasons: string[] }[]
  shadow_request_id: string | null
  knowledge_cutoff: string | null
}

export interface SourceFailure {
  endpoint: string
  message: string
}

export type ConsoleState =
  | { phase: 'loading'; mode: DataMode }
  | { phase: 'ready'; mode: DataMode; data: ConsoleData }
  | { phase: 'unavailable'; mode: 'http'; failures: SourceFailure[] }
