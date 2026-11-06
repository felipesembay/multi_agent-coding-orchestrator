import {
  Database,
  LockKeyhole,
  RefreshCw,
  SlidersHorizontal,
} from 'lucide-react'
import { useSettings } from '../lib/api'
import { ErrorState, Loading, SectionTitle } from '../components/shared'
import { Button } from '../components/ui/button'
export function SettingsPage() {
  const query = useSettings(),
    data = query.data
  const fields = data
    ? [
        ['Planner', data.planner],
        [
          'Modelo do planner',
          data.planner === 'antigravity'
            ? (data.planner_model ?? 'gemini-4-argon-medium')
            : 'Padrão do CLI · não registrado',
        ],
        ['Implementer', data.implementer],
        [
          'Modelo do implementer',
          data.implementer === 'antigravity'
            ? (data.implementer_model ?? 'gemini-4-argon-medium')
            : 'Padrão do CLI · não registrado',
        ],
        ['Reviewer', data.reviewer],
        ['Modelo do reviewer', 'Padrão do CLI · não registrado'],
        ['Modelo Antigravity direto', data.antigravity_default_model],
        ['Comando de testes', data.test_command ?? 'Não configurado'],
        ['Banco SQLite', data.database],
      ]
    : []
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">LOCAL CONFIGURATION</div>
          <h1>
            Settings<span>.</span>
          </h1>
          <p>
            Configuração atual do processo da API, disponível somente para
            leitura.
          </p>
        </div>
        <Button onClick={() => void query.refetch()}>
          <RefreshCw size={15} />
          Atualizar
        </Button>
      </div>
      {query.isError && (
        <ErrorState error={query.error} retry={query.refetch} />
      )}
      {query.isPending ? (
        <Loading />
      ) : (
        data && (
          <div className="settings-grid">
            <section className="panel">
              <SectionTitle
                title="Agentes e ambiente"
                action={<SlidersHorizontal size={18} />}
              />
              <dl className="settings-list">
                {fields.map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd className="mono">{value}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section className="panel">
              <SectionTitle
                title="Componentes"
                action={<Database size={18} />}
              />
              <dl className="settings-list">
                {Object.entries(data.versions).map(([name, value]) => (
                  <div key={name}>
                    <dt>{name}</dt>
                    <dd className="mono">{value ?? 'Indisponível'}</dd>
                  </div>
                ))}
              </dl>
              <div className="readonly-note">
                <LockKeyhole size={20} />
                <p>
                  Configuração de agentes e modelos é feita no ambiente do
                  processo. Nenhuma alteração é executada pelo dashboard.
                </p>
              </div>
            </section>
          </div>
        )
      )}
      <div className="info-note">
        A configuração da API pode diferir do ambiente usado pelo CLI. Ela não
        identifica os providers de execuções anteriores.
      </div>
    </>
  )
}
