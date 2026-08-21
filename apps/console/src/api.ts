import { syntheticData } from './synthetic'
import type {
  ActivityDTO,
  ConsoleData,
  ConsoleState,
  DataMode,
  DecisionPacketDTO,
  ModelRunDTO,
  ObservationDTO,
  SourceFailure,
  StatusDTO,
} from './types'

const endpoints = {
  status: '/api/v1/status',
  activities: '/api/v1/activities',
  observations: '/api/v1/observations',
  modelRuns: '/api/v1/model-runs',
  decisionPackets: '/api/v1/decision-packets',
} as const

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

function sourceUrl(path: string): string {
  return `${apiBaseUrl}${path}`
}

type EndpointKey = keyof typeof endpoints

function unwrapList(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (value && typeof value === 'object' && 'items' in value) {
    const items = (value as { items?: unknown }).items
    return Array.isArray(items) ? items : []
  }
  return []
}

function latestTimestamp(...groups: { created_at?: string; recorded_at?: string; available_at?: string }[][]): string {
  const values = groups.flat().flatMap((item) => [item.created_at, item.recorded_at, item.available_at]).filter((item): item is string => Boolean(item))
  return values.sort().at(-1) ?? new Date().toISOString()
}

export function mapApiData(values: Record<EndpointKey, unknown>): ConsoleData {
  const status = values.status as StatusDTO
  const activityDtos = unwrapList(values.activities) as ActivityDTO[]
  const observationDtos = unwrapList(values.observations) as ObservationDTO[]
  const runDtos = unwrapList(values.modelRuns) as ModelRunDTO[]
  const packetDtos = unwrapList(values.decisionPackets) as DecisionPacketDTO[]
  const activities = activityDtos.map((item) => ({
    activity_id: item.activity_id,
    kind: item.kind,
    account_id: item.account_id,
    effective_at: item.effective_at,
    recorded_at: item.recorded_at,
    amount: item.gross_amount?.amount,
    currency: item.gross_amount?.currency,
    instrument_id: item.instrument_id ?? undefined,
    source: 'ledger append-only',
  }))
  const observations = observationDtos.map((item) => ({
    observation_id: item.observation_id,
    series_id: item.series_id,
    value: item.value,
    unit: item.unit,
    effective_at: item.times.effective_at,
    available_at: item.times.available_at,
    vintage_id: item.vintage_id,
    source: item.source,
  }))
  const modelRuns = runDtos.map((item) => ({
    run_id: item.run_id,
    model: item.model_id,
    created_at: item.created_at,
    dataset_id: item.dataset_fingerprint,
    solver: `${item.solver.solver_id}/${item.solver.version}`,
    status: item.validated ? 'validated' : 'not_validated',
    limitations: item.violations.length > 0 ? item.violations : ['Sem violações registradas'],
  }))
  const decisionPackets = packetDtos.map((item) => {
    const noAction = item.alternatives.find((alternative) => alternative.alternative_id === 'no_action')
    const feasible = item.alternatives.some((alternative) => alternative.feasible)
    const reasons = item.alternatives.flatMap((alternative) => alternative.reasons)
    return {
      packet_id: item.packet_id,
      created_at: item.created_at,
      action: noAction ? 'NO_ACTION disponível' : `${item.alternatives.length} alternativa(s)`,
      model_run_ids: item.model_run_ids,
      evidence_ids: item.evidence_ids,
      status: feasible ? 'pronto para revisão' : 'requer atenção',
      limitations: reasons.length > 0 ? reasons : ['Execução de capital bloqueada'],
      shadow_request_id: item.shadow_request_id ?? undefined,
      knowledge_cutoff: item.knowledge_cutoff ?? undefined,
    }
  })
  return {
    status: {
      service: 'Marko Read API',
      state: status.status,
      version: status.api_version,
      as_of: latestTimestamp(activities, observations, modelRuns, decisionPackets),
      persistence: status.mode === 'postgres' ? 'PostgreSQL append-only' : 'demo em memória',
      limitations: ['Console somente leitura', 'Execução de capital bloqueada'],
      synthetic: status.synthetic,
      mode: status.mode,
    },
    activities,
    observations,
    modelRuns,
    decisionPackets,
  }
}

async function request(endpoint: string, accessToken?: string): Promise<unknown> {
  const response = await fetch(endpoint, {
    cache: 'no-store',
    credentials: 'omit',
    headers: {
      Accept: 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}

export async function loadConsoleData(mode: DataMode, accessToken?: string): Promise<ConsoleState> {
  if (mode === 'synthetic') return { phase: 'ready', mode, data: syntheticData }

  const knownAt = new Date().toISOString()
  const requested: Record<EndpointKey, string> = {
    status: sourceUrl(endpoints.status),
    activities: sourceUrl(endpoints.activities),
    observations: `${sourceUrl(endpoints.observations)}?known_at=${encodeURIComponent(knownAt)}`,
    modelRuns: sourceUrl(endpoints.modelRuns),
    decisionPackets: sourceUrl(endpoints.decisionPackets),
  }
  const keys = Object.keys(requested) as EndpointKey[]
  const settled = await Promise.allSettled(keys.map((key) => request(requested[key], accessToken)))
  const failures: SourceFailure[] = settled.flatMap((result, index) =>
    result.status === 'rejected'
      ? [{ endpoint: requested[keys[index]], message: result.reason instanceof Error ? result.reason.message : 'Falha de rede' }]
      : [],
  )

  if (failures.length > 0) return { phase: 'unavailable', mode, failures }

  const values = Object.fromEntries(settled.map((result, index) => [keys[index], result.status === 'fulfilled' ? result.value : null])) as Record<EndpointKey, unknown>
  return {
    phase: 'ready',
    mode,
    data: mapApiData(values),
  }
}
