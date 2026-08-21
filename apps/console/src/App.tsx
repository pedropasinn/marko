import { useEffect, useState, type ComponentType, type SVGProps } from 'react'
import {
  Activity as ActivityIcon,
  AlertTriangle,
  ArrowRight,
  CircleGauge,
  Database,
  FlaskConical,
  LockKeyhole,
  Scale,
  ShieldCheck,
} from 'lucide-react'
import { AuthView } from '@neondatabase/auth/react/ui'
import { useLocation } from 'react-router-dom'
import { loadConsoleData } from './api'
import { authClient, configuredAuthMode, getApiBearerToken, type ConsoleAuthMode } from './auth'
import type { ConsoleData, ConsoleState, DataMode } from './types'

type Icon = ComponentType<SVGProps<SVGSVGElement>>
type CredentialState =
  | { phase: 'idle' }
  | { phase: 'pending' }
  | { phase: 'unavailable' }
  | { phase: 'ready'; token: string }

const navigation: { id: string; label: string; icon: Icon }[] = [
  { id: 'visao-geral', label: 'Visão geral', icon: CircleGauge },
  { id: 'accounting', label: 'Accounting', icon: ActivityIcon },
  { id: 'research', label: 'Research', icon: FlaskConical },
  { id: 'decisions', label: 'Decisions', icon: Scale },
  { id: 'shadow', label: 'Shadow / Persistence', icon: Database },
]

function formatDate(value?: string): string {
  if (!value) return 'não informado'
  const date = new Date(value)
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'UTC' }).format(date) + ' UTC'
}

function shortId(value?: string): string {
  return value || '—'
}

function ModeFlag({ mode, apiSynthetic = false }: { mode: DataMode; apiSynthetic?: boolean }) {
  return mode === 'synthetic' ? (
    <div className="mode-flag mode-flag--synthetic" role="status">
      <AlertTriangle aria-hidden="true" />
      <strong>Dados sintéticos</strong>
      <span>Ambiente demonstrativo. Nenhum registro representa uma pessoa ou conta real.</span>
    </div>
  ) : apiSynthetic ? (
    <div className="mode-flag mode-flag--synthetic" role="status">
      <AlertTriangle aria-hidden="true" />
      <strong>API em modo demo</strong>
      <span>Fonte HTTP conectada; o servidor declarou dados sintéticos.</span>
    </div>
  ) : (
    <div className="mode-flag" role="status">
      <span className="source-dot" aria-hidden="true" />
      <strong>Fonte HTTP</strong>
      <span>Leitura direta de /api/v1</span>
    </div>
  )
}

function Header({
  mode,
  apiSynthetic,
  identity,
  onSignOut,
}: {
  mode: DataMode
  apiSynthetic?: boolean
  identity?: string
  onSignOut?: () => void
}) {
  return (
    <>
      <header className="masthead">
        <a className="brand" href="#visao-geral" aria-label="Marko — ir para Visão geral">
          <span className="brand-mark" aria-hidden="true">M</span>
          <span><strong>MARKO</strong><small>mesa de auditoria</small></span>
        </a>
        <div className="header-controls">
          {identity && <span className="auth-identity">Sessão: {identity}</span>}
          {onSignOut && <button className="auth-action" type="button" onClick={onSignOut}>Sair</button>}
          <div className="read-only"><LockKeyhole aria-hidden="true" /> somente leitura</div>
        </div>
      </header>
      <ModeFlag mode={mode} apiSynthetic={apiSynthetic} />
      <nav className="section-nav" aria-label="Áreas do console">
        {navigation.map(({ id, label, icon: NavIcon }) => (
          <a href={`#${id}`} key={id}><NavIcon aria-hidden="true" />{label}</a>
        ))}
      </nav>
    </>
  )
}

function SectionHeading({ id, index, title, note }: { id: string; index: string; title: string; note: string }) {
  return (
    <div className="section-heading">
      <span className="section-index">{index}</span>
      <div><h2 id={id}>{title}</h2><p>{note}</p></div>
    </div>
  )
}

function Overview({ data }: { data: ConsoleData }) {
  const lastActivity = data.activities.at(-1)
  const lastRun = data.modelRuns.at(-1)
  const lastPacket = data.decisionPackets.at(-1)
  const globalLimitations = data.status.limitations ?? []
  const trail = [
    { label: 'Activity', value: lastActivity?.activity_id, asOf: lastActivity?.recorded_at, source: lastActivity?.source ?? 'ledger', limitations: 'fato imutável' },
    { label: 'ModelRun', value: lastRun?.run_id, asOf: lastRun?.created_at, source: lastRun?.dataset_id ?? 'dataset não informado', limitations: lastRun?.limitations?.[0] ?? 'não informadas' },
    { label: 'DecisionPacket', value: lastPacket?.packet_id, asOf: lastPacket?.created_at, source: lastPacket?.model_run_ids?.join(', ') || 'ModelRun não informado', limitations: lastPacket?.limitations?.[0] ?? 'não informadas' },
    { label: 'Shadow', value: lastPacket?.status ?? data.status.state, asOf: data.status.as_of, source: data.status.persistence, limitations: globalLimitations[0] ?? 'capital real bloqueado' },
  ]

  return (
    <section id="visao-geral" className="panel panel--lead" aria-labelledby="title-overview">
      <div className="lead-copy">
        <p className="eyebrow">estado operacional · {data.status.version}</p>
        <h1 id="title-overview">Acompanhe o que aconteceu, com cada passo explicado.</h1>
        <p>Veja o estado geral primeiro. Quando precisar, abra os detalhes para conferir dados, decisões e suas fontes. O console não movimenta dinheiro.</p>
      </div>
      <div className="status-ruler" aria-label="Resumo do sistema">
        <div><span>serviço</span><strong>{data.status.service}</strong></div>
        <div><span>estado</span><strong className="verified">{data.status.state}</strong></div>
        <div><span>as of</span><strong>{formatDate(data.status.as_of)}</strong></div>
        <div><span>persistência</span><strong>{data.status.persistence}</strong></div>
      </div>
      <div className="portfolio-kpis" aria-label="Cobertura auditável">
        <div><span>Activities</span><strong>{data.activities.length.toLocaleString('pt-BR')}</strong><small>fatos contábeis</small></div>
        <div><span>Observations</span><strong>{data.observations.length.toLocaleString('pt-BR')}</strong><small>no corte conhecido</small></div>
        <div><span>ModelRuns</span><strong>{data.modelRuns.length.toLocaleString('pt-BR')}</strong><small>execuções preservadas</small></div>
        <div><span>DecisionPackets</span><strong>{data.decisionPackets.length.toLocaleString('pt-BR')}</strong><small>decisões rastreáveis</small></div>
      </div>
      <div className="provenance" aria-label="Trilha de proveniência">
        <div className="provenance-title"><ShieldCheck aria-hidden="true" /><strong>Cadeia de custódia</strong><span>último ciclo disponível</span></div>
        <ol>
          {trail.map((item, index) => (
            <li key={item.label}>
              <div className="trail-node"><span>{item.label}</span><strong>{shortId(item.value)}</strong></div>
              <dl>
                <div><dt>as_of</dt><dd>{formatDate(item.asOf)}</dd></div>
                <div><dt>fonte</dt><dd>{item.source || 'não informada'}</dd></div>
                <div><dt>limite</dt><dd>{item.limitations}</dd></div>
              </dl>
              {index < trail.length - 1 && <ArrowRight className="trail-arrow" aria-hidden="true" />}
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function Accounting({ data }: { data: ConsoleData }) {
  return (
    <section id="accounting" className="panel" aria-labelledby="title-accounting">
      <details className="disclosure">
        <summary><SectionHeading id="title-accounting" index="01" title="Accounting" note="Movimentações registradas. Toque para conferir os detalhes." /></summary>
        <div className="table-wrap">
        <table>
          <thead><tr><th>ID / espécie</th><th>Conta</th><th>Instrumento</th><th>Valor</th><th>Efetivo</th><th>Registrado</th></tr></thead>
          <tbody>{data.activities.map((item) => (
            <tr key={item.activity_id}>
              <td data-label="ID / espécie"><code>{item.activity_id}</code><span className="subvalue">{item.kind}</span></td>
              <td data-label="Conta">{item.account_id}</td>
              <td data-label="Instrumento">{item.instrument_id ?? 'caixa'}</td>
              <td data-label="Valor" className="numeric">{item.amount ?? '—'} <small>{item.currency}</small></td>
              <td data-label="Efetivo">{formatDate(item.effective_at)}</td>
              <td data-label="Registrado">{formatDate(item.recorded_at)}</td>
            </tr>
          ))}</tbody>
        </table>
        {data.activities.length === 0 && <p className="empty">Nenhuma Activity disponível nesta fonte.</p>}
        </div>
      </details>
    </section>
  )
}

function Research({ data }: { data: ConsoleData }) {
  return (
    <section id="research" className="panel" aria-labelledby="title-research">
      <details className="disclosure">
        <summary><SectionHeading id="title-research" index="02" title="Research" note="Dados e modelos usados nas análises. Toque para conferir." /></summary>
        <div className="research-split">
        <div>
          <h3>Observações disponíveis</h3>
          <div className="observation-lines">
            {data.observations.map((item) => (
              <article key={item.observation_id}>
                <div><span className="series">{item.series_id}</span><strong>{item.value}</strong><small>{item.unit}</small></div>
                <dl><div><dt>Disponível em</dt><dd>{formatDate(item.available_at)}</dd></div><div><dt>Vintage</dt><dd>{item.vintage_id}</dd></div><div><dt>Fonte</dt><dd>{item.source}</dd></div></dl>
              </article>
            ))}
            {data.observations.length === 0 && <p className="empty">Nenhuma Observation disponível para o corte informado.</p>}
          </div>
        </div>
        <div>
          <h3>Execuções de modelo</h3>
          {data.modelRuns.map((run) => (
            <article className="run-sheet" key={run.run_id}>
              <div className="sheet-stamp"><ShieldCheck aria-hidden="true" /><span>{run.status}</span></div>
              <code>{run.run_id}</code><h4>{run.model}</h4>
              <dl><div><dt>Dataset</dt><dd>{run.dataset_id}</dd></div><div><dt>Solver</dt><dd>{run.solver}</dd></div><div><dt>Executado</dt><dd>{formatDate(run.created_at)}</dd></div></dl>
              <p><strong>Limitações</strong> {(run.limitations ?? []).join(' · ') || 'Não informadas'}</p>
            </article>
          ))}
          {data.modelRuns.length === 0 && <p className="empty">Nenhum ModelRun disponível nesta fonte.</p>}
        </div>
        </div>
      </details>
    </section>
  )
}

function Decisions({ data }: { data: ConsoleData }) {
  return (
    <section id="decisions" className="panel" aria-labelledby="title-decisions">
      <details className="disclosure">
        <summary><SectionHeading id="title-decisions" index="03" title="Decisions" note="Decisões registradas para revisão; nenhuma executa dinheiro." /></summary>
        <div className="decision-ledger">
        {data.decisionPackets.map((packet) => (
          <article key={packet.packet_id}>
            <header><code>{packet.packet_id}</code><span className="status-chip">{packet.status}</span></header>
            <div className="decision-action"><small>Ação registrada</small><strong>{packet.action}</strong></div>
            <dl>
              <div><dt>as_of</dt><dd>{formatDate(packet.created_at)}</dd></div>
              <div><dt>knowledge cutoff</dt><dd>{formatDate(packet.knowledge_cutoff)}</dd></div>
              <div><dt>Shadow request</dt><dd>{packet.shadow_request_id ?? 'não vinculado'}</dd></div>
              <div><dt>ModelRuns</dt><dd>{(packet.model_run_ids ?? []).join(', ') || '—'}</dd></div>
              <div><dt>Evidências</dt><dd>{(packet.evidence_ids ?? []).join(', ') || '—'}</dd></div>
              <div><dt>Limitações</dt><dd>{(packet.limitations ?? []).join(' · ') || 'Não informadas'}</dd></div>
            </dl>
          </article>
        ))}
        {data.decisionPackets.length === 0 && <p className="empty">Nenhum DecisionPacket disponível nesta fonte.</p>}
        </div>
      </details>
    </section>
  )
}

function Shadow({ data }: { data: ConsoleData }) {
  return (
    <section id="shadow" className="panel panel--last" aria-labelledby="title-shadow">
      <details className="disclosure">
        <summary><SectionHeading id="title-shadow" index="04" title="Shadow / Persistence" note="Segurança, integridade e limites da operação de teste." /></summary>
        <div className="shadow-band">
        <div className="shadow-state"><ShieldCheck aria-hidden="true" /><div><small>Integridade declarada</small><strong>{data.status.persistence}</strong></div></div>
        <div className="constraint"><LockKeyhole aria-hidden="true" /><div><strong>Execução bloqueada</strong><span>revisão humana obrigatória</span></div></div>
        <div className="constraint"><Database aria-hidden="true" /><div><strong>Registros imutáveis</strong><span>sem controles de escrita</span></div></div>
      </div>
        <div className="limitations"><span>Limitações vigentes</span><ul>{(data.status.limitations ?? []).map((item) => <li key={item}>{item}</li>)}</ul></div>
      </details>
    </section>
  )
}

function Unavailable({ state }: { state: Extract<ConsoleState, { phase: 'unavailable' }> }) {
  return (
    <main id="conteudo" className="unavailable" tabIndex={-1}>
      <AlertTriangle aria-hidden="true" />
      <p className="eyebrow">conexão interrompida</p>
      <h1>Fonte indisponível</h1>
      <p>O console não substituiu a resposta HTTP por dados demonstrativos. Verifique o serviço e tente novamente.</p>
      <ul>{state.failures.map((failure) => <li key={failure.endpoint}><code>{failure.endpoint}</code><span>{failure.message}</span></li>)}</ul>
    </main>
  )
}

function Console({
  dataMode,
  accessToken,
  identity,
  onSignOut,
}: {
  dataMode: DataMode
  accessToken?: string
  identity?: string
  onSignOut?: () => void
}) {
  const [state, setState] = useState<ConsoleState>({ phase: 'loading', mode: dataMode })

  useEffect(() => {
    let active = true
    setState({ phase: 'loading', mode: dataMode })
    void loadConsoleData(dataMode, accessToken).then((next) => { if (active) setState(next) })
    return () => { active = false }
  }, [accessToken, dataMode])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#conteudo">Pular para o conteúdo</a>
      <Header
        mode={dataMode}
        apiSynthetic={state.phase === 'ready' && state.data.status.synthetic}
        identity={identity}
        onSignOut={onSignOut}
      />
      {state.phase === 'loading' && <main id="conteudo" className="loading" aria-live="polite"><span />Carregando fontes de auditoria…</main>}
      {state.phase === 'unavailable' && <Unavailable state={state} />}
      {state.phase === 'ready' && (
        <main id="conteudo">
          <Overview data={state.data} />
          <Accounting data={state.data} />
          <Research data={state.data} />
          <Decisions data={state.data} />
          <Shadow data={state.data} />
        </main>
      )}
      <footer><span>MARKO / CONSOLE 0.3.1</span><span>READ ONLY · {state.phase === 'ready' ? formatDate(state.data.status.as_of) : 'aguardando fonte'}</span></footer>
    </div>
  )
}

function PrivateConsole() {
  const location = useLocation()
  const client = authClient
  if (!client) return null
  const session = client.useSession()
  const sessionId = session.data?.session.id
  const [credential, setCredential] = useState<CredentialState>({ phase: 'idle' })

  useEffect(() => {
    let active = true
    if (!sessionId) {
      setCredential({ phase: 'idle' })
      return () => { active = false }
    }
    setCredential({ phase: 'pending' })
    void getApiBearerToken()
      .then((token) => {
        if (active) setCredential(token ? { phase: 'ready', token } : { phase: 'unavailable' })
      })
      .catch(() => {
        if (active) setCredential({ phase: 'unavailable' })
      })
    return () => { active = false }
  }, [sessionId])

  if (session.isPending) {
    return <main className="loading" aria-live="polite"><span />Verificando sessão…</main>
  }
  if (!session.data) {
    const authPath = location.pathname.startsWith('/auth/')
      ? location.pathname.slice('/auth/'.length)
      : null
    if (authPath) {
      return <main className="auth-page" id="conteudo"><AuthView pathname={authPath} /></main>
    }
    return (
      <main className="auth-required" id="conteudo">
        <LockKeyhole aria-hidden="true" />
        <h1>Autenticação necessária</h1>
        <p>Entre com a conta autorizada para consultar a fonte privada.</p>
        <a className="auth-action" href="/auth/sign-in">Entrar</a>
      </main>
    )
  }

  if (credential.phase === 'idle' || credential.phase === 'pending') {
    return <main className="loading" aria-live="polite"><span />Obtendo credencial da API…</main>
  }
  if (credential.phase === 'unavailable') {
    return <AuthBlocked message="A sessão não forneceu uma credencial verificável para a Read API." />
  }
  return (
    <Console
      dataMode="http"
      accessToken={credential.token}
      identity={session.data.user.email}
      onSignOut={() => { void client.signOut() }}
    />
  )
}

function AuthBlocked({ message }: { message: string }) {
  return (
    <main className="auth-required" id="conteudo" role="alert">
      <LockKeyhole aria-hidden="true" />
      <h1>Acesso privado bloqueado</h1>
      <p>{message}</p>
    </main>
  )
}

export function App({
  dataMode = import.meta.env.VITE_DATA_MODE === 'synthetic' ? 'synthetic' : 'http',
  authMode = configuredAuthMode(),
}: {
  dataMode?: DataMode
  authMode?: ConsoleAuthMode
}) {
  if (dataMode === 'synthetic' || authMode === 'public') {
    return <Console dataMode={dataMode} />
  }
  if (!authClient) {
    return <AuthBlocked message="VITE_NEON_AUTH_URL é obrigatória quando VITE_AUTH_MODE=private." />
  }
  return <PrivateConsole />
}
