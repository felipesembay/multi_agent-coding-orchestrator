import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/button'
import { mutate } from '../lib/projects'
import {
  copyDefinition,
  copyName,
  finiteNumbers,
  issueLabel,
  movedSteps,
  optionalStep,
  topologyValid,
  validateDefinition,
} from '../lib/workflow-editor'
import type {
  SavedWorkflow,
  WorkflowDefinition,
  WorkflowStep,
  WorkflowVersion,
} from '../types'

const titles = {
  plan: 'Planejamento',
  implement: 'Implementação',
  test: 'Testes',
  review: 'Revisão',
  document: 'Documentação',
  human_gate: 'Aprovação humana',
}

export function WorkflowEditor({
  initial,
  workflow,
  baseVersion,
  versions = [],
  onVersion,
}: {
  initial: WorkflowDefinition
  workflow?: SavedWorkflow
  baseVersion?: WorkflowVersion
  versions?: WorkflowVersion[]
  onVersion?: (id: string) => void
}) {
  const navigate = useNavigate(),
    cache = useQueryClient()
  const [draft, setDraft] = useState(() => copyDefinition(initial))
  const [description, setDescription] = useState(workflow?.description ?? '')
  const [stable, setStable] = useState(draft)
  const [optional, setOptional] = useState<'document' | 'test' | 'human_gate'>(
    'document',
  )
  const [operationError, setOperationError] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setStable(draft), 300)
    return () => clearTimeout(timer)
  }, [draft])
  const numeric = finiteNumbers(draft)
  const validation = useQuery({
    queryKey: ['workflow-definition-validation', stable],
    queryFn: ({ signal }) => validateDefinition(stable, signal),
    enabled: finiteNumbers(stable),
    retry: false,
  })
  const current = numeric && JSON.stringify(stable) === JSON.stringify(draft)
  const valid =
    current &&
    validation.data?.valid === true &&
    !validation.isFetching &&
    !validation.error
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial)
  const readonly = workflow?.read_only ?? false
  const save = useMutation({
    mutationFn: async ({ copy }: { copy: boolean }) => {
      const definition = copyDefinition(draft)
      if (copy) definition.name = copyName(definition.name)
      if (workflow && !copy) {
        const version = await mutate<WorkflowVersion>(
          `/workflows/${encodeURIComponent(workflow.id)}/versions`,
          { definition },
        )
        return {
          saved: {
            ...workflow,
            name: version.definition.name,
            latest_version: version,
          },
          version,
          created: false,
        }
      }
      const saved = await mutate<SavedWorkflow>('/workflows', {
        definition,
        description,
      })
      if (!saved.latest_version) throw new Error('Resposta de versão inválida.')
      return { saved, version: saved.latest_version, created: true }
    },
    onSuccess: async ({ saved, version, created }) => {
      cache.setQueryData<SavedWorkflow[]>(['workflows'], (previous) => [
        ...(previous ?? []).filter((item) => item.id !== saved.id),
        saved,
      ])
      cache.setQueryData<WorkflowVersion[]>(
        ['workflow-versions', saved.id],
        (previous) =>
          created
            ? [version]
            : [
                ...(previous ?? []).filter((item) => item.id !== version.id),
                version,
              ],
      )
      navigate(
        `/workflows/${encodeURIComponent(saved.id)}?version=${encodeURIComponent(version.id)}`,
      )
      await cache.invalidateQueries({ queryKey: ['workflows'] })
      await cache.invalidateQueries({
        queryKey: ['workflow-versions', saved.id],
      })
    },
  })
  const locked = readonly || save.isPending
  const limits = draft.limits ?? {
    max_total_steps: 200,
    max_duration_s: 14400,
    budget_usd: null,
  }
  const approval = draft.approval ?? {
    require_tests: true,
    require_reviewer: true,
    human_gate_after_plan: false,
  }
  function update(stepId: string, values: Partial<WorkflowStep>) {
    const next = draft.steps.map((step) =>
      step.id === stepId ? { ...step, ...values } : step,
    )
    if ('per_task' in values && !topologyValid(next)) {
      setOperationError(
        'Agrupe as etapas por tarefa antes de mudar este escopo.',
      )
      return
    }
    setOperationError('')
    setDraft({ ...draft, steps: next })
  }
  function move(from: number, to: number) {
    const next = movedSteps(draft.steps, from, to)
    if (next) setDraft({ ...draft, steps: next })
  }
  function removable(step: WorkflowStep) {
    return (
      (step.type === 'document' ||
        step.type === 'human_gate' ||
        (step.type === 'test' &&
          draft.steps.filter((s) => s.type === 'test').length > 1)) &&
      topologyValid(draft.steps.filter((s) => s.id !== step.id))
    )
  }
  return (
    <section className="workflow-page">
      <div className="section-title">
        <div>
          <h1>{workflow ? 'Editar workflow' : 'Novo workflow'}</h1>
          <p>
            Salvar cria uma versão imutável; execuções anteriores não mudam.
          </p>
        </div>
        <Button asChild>
          <Link to="/workflows">Todos os workflows</Link>
        </Button>
      </div>
      <p>
        Defina etapas e limites aqui. Providers e modelos são escolhidos antes
        de cada execução. Salvar não inicia agentes.
      </p>
      {readonly && (
        <p role="status">
          Esta definição é somente leitura. Crie uma cópia para editar.
        </p>
      )}
      {baseVersion && (
        <label className="workflow-version">
          Versão do workflow
          <select
            aria-label="Versão do workflow"
            value={baseVersion.id}
            disabled={dirty || save.isPending}
            onChange={(event) => onVersion?.(event.target.value)}
          >
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                Versão {version.version}
              </option>
            ))}
          </select>
        </label>
      )}
      {dirty && workflow && (
        <p>
          Há alterações não salvas. Salve ou descarte antes de trocar de versão.
        </p>
      )}
      <fieldset className="request-form workflow-editor" disabled={locked}>
        <legend>Definição</legend>
        <label>
          Nome do workflow
          <input
            aria-label="Nome do workflow"
            value={draft.name}
            maxLength={120}
            onChange={(event) =>
              setDraft({ ...draft, name: event.target.value })
            }
          />
        </label>
        {!workflow ? (
          <label>
            Descrição
            <textarea
              value={description}
              maxLength={2000}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
        ) : (
          workflow.description && <p>{workflow.description}</p>
        )}
        <ol aria-label="Etapas do workflow" className="workflow-stage-list">
          {draft.steps.map((step, index) => (
            <li
              key={step.id}
              data-step-id={step.id}
              draggable={!locked && index > 0}
              onDragStart={(event) =>
                event.dataTransfer.setData('text/plain', step.id)
              }
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault()
                if (!locked)
                  move(
                    draft.steps.findIndex(
                      (s) => s.id === event.dataTransfer.getData('text/plain'),
                    ),
                    index,
                  )
              }}
            >
              <div className="section-title">
                <div>
                  <strong className="mono">{step.id}</strong>
                  <span> · {titles[step.type]}</span>
                </div>
                <div className="workflow-stage-actions">
                  <Button
                    type="button"
                    size="sm"
                    aria-label={`Mover ${step.id} para cima`}
                    disabled={!movedSteps(draft.steps, index, index - 1)}
                    onClick={() => move(index, index - 1)}
                  >
                    ↑
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    aria-label={`Mover ${step.id} para baixo`}
                    disabled={!movedSteps(draft.steps, index, index + 1)}
                    onClick={() => move(index, index + 1)}
                  >
                    ↓
                  </Button>
                  {removable(step) && (
                    <Button
                      type="button"
                      size="sm"
                      aria-label={`Remover ${step.id}`}
                      onClick={() =>
                        setDraft({
                          ...draft,
                          steps: draft.steps.filter((s) => s.id !== step.id),
                        })
                      }
                    >
                      Remover
                    </Button>
                  )}
                </div>
              </div>
              {step.type !== 'plan' && (
                <label className="confirmation-checkbox">
                  <input
                    type="checkbox"
                    aria-label={`Por tarefa em ${step.id}`}
                    checked={step.per_task ?? false}
                    onChange={(event) =>
                      update(step.id, { per_task: event.target.checked })
                    }
                  />
                  Por tarefa
                </label>
              )}
              {step.requires?.length ? (
                <p className="form-footnote">
                  Capacidades: {step.requires.join(', ')}
                </p>
              ) : null}
              {step.type === 'implement' && (
                <label>
                  Tentativas para {step.id}
                  <input
                    type="number"
                    aria-label={`Tentativas para ${step.id}`}
                    value={
                      Number.isFinite(step.max_attempts ?? 3)
                        ? (step.max_attempts ?? 3)
                        : ''
                    }
                    min={1}
                    max={20}
                    onChange={(event) =>
                      update(step.id, {
                        max_attempts: event.target.valueAsNumber,
                      })
                    }
                  />
                </label>
              )}
              {step.type === 'review' && (
                <label>
                  Rejeição em {step.id}
                  <select
                    aria-label={`Rejeição em ${step.id}`}
                    value={step.on_reject ?? ''}
                    onChange={(event) =>
                      update(step.id, { on_reject: event.target.value || null })
                    }
                  >
                    <option value="">Bloquear se rejeitar</option>
                    {draft.steps
                      .slice(0, index)
                      .filter(
                        (s) =>
                          s.type === 'implement' &&
                          s.per_task &&
                          draft.steps
                            .slice(draft.steps.indexOf(s), index + 1)
                            .every((item) => item.per_task),
                      )
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          Repetir {s.id}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              {step.type === 'test' && (
                <p>Perfil de testes configurado no servidor.</p>
              )}
            </li>
          ))}
        </ol>
        <div className="workflow-stage-actions">
          <label>
            Etapa opcional
            <select
              aria-label="Etapa opcional"
              value={optional}
              onChange={(event) =>
                setOptional(event.target.value as typeof optional)
              }
            >
              <option value="document">Documentação</option>
              <option value="test">Teste extra</option>
              <option value="human_gate">Aprovação humana</option>
            </select>
          </label>
          <Button
            type="button"
            disabled={draft.steps.length >= 100}
            onClick={() =>
              setDraft({
                ...draft,
                steps: [...draft.steps, optionalStep(optional, draft.steps)],
                approval:
                  optional === 'test'
                    ? { ...approval, require_tests: true }
                    : approval,
              })
            }
          >
            Adicionar etapa
          </Button>
        </div>
        <div className="workflow-limits">
          <label>
            Total de passos
            <input
              type="number"
              value={
                Number.isFinite(limits.max_total_steps)
                  ? limits.max_total_steps
                  : ''
              }
              min={1}
              max={10000}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  limits: {
                    ...limits,
                    max_total_steps: event.target.valueAsNumber,
                  },
                })
              }
            />
          </label>
          <label>
            Duração máxima (segundos)
            <input
              type="number"
              value={
                Number.isFinite(limits.max_duration_s)
                  ? limits.max_duration_s
                  : ''
              }
              min={1}
              max={86400}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  limits: {
                    ...limits,
                    max_duration_s: event.target.valueAsNumber,
                  },
                })
              }
            />
          </label>
          <label>
            Orçamento opcional (USD)
            <input
              type="number"
              min={0}
              step="0.01"
              value={
                limits.budget_usd === null ||
                !Number.isFinite(limits.budget_usd)
                  ? ''
                  : limits.budget_usd
              }
              onChange={(event) =>
                setDraft({
                  ...draft,
                  limits: {
                    ...limits,
                    budget_usd:
                      event.target.value === ''
                        ? null
                        : event.target.valueAsNumber,
                  },
                })
              }
            />
          </label>
        </div>
        <label className="confirmation-checkbox">
          <input
            type="checkbox"
            checked={approval.human_gate_after_plan}
            onChange={(event) =>
              setDraft({
                ...draft,
                approval: {
                  ...approval,
                  human_gate_after_plan: event.target.checked,
                },
              })
            }
          />
          Exigir aprovação humana após o plano
        </label>
        <p className="form-footnote">
          Testes são obrigatórios quando presentes; etapas de revisão exigem
          aprovação.
        </p>
      </fieldset>
      {(approval.human_gate_after_plan ||
        draft.steps.some((s) => s.type === 'human_gate')) && (
        <p className="text-amber">
          Aprovações humanas podem ser modeladas, mas sua execução aguarda
          integração.
        </p>
      )}
      {limits.budget_usd !== null && (
        <p className="text-amber">
          Orçamento pode ser modelado; a execução com limite aguarda
          contabilidade.
        </p>
      )}
      <div className="workflow-validation" aria-live="polite">
        {!numeric && (
          <p role="alert" className="form-error">
            Preencha os campos numéricos com valores válidos.
          </p>
        )}
        {validation.error && (
          <p role="alert" className="form-error">
            {validation.error.message}
          </p>
        )}
        {current && validation.data?.issues.length ? (
          <ul role="alert" className="form-error">
            {validation.data.issues.map((issue, index) => (
              <li key={index}>{issueLabel(issue, draft)}</li>
            ))}
          </ul>
        ) : null}
        {numeric &&
          (!current || validation.isFetching || validation.isPending) && (
            <p role="status">Validando estrutura…</p>
          )}
        {valid && (
          <p role="status" className="text-green">
            Estrutura válida. A confirmação de execução verificará os providers.
          </p>
        )}
      </div>
      {operationError && (
        <p role="alert" className="form-error">
          {operationError}
        </p>
      )}
      {save.error && (
        <p role="alert" className="form-error">
          {save.error.message}
        </p>
      )}
      <div className="form-actions">
        {dirty && !readonly && (
          <Button
            disabled={save.isPending}
            onClick={() => {
              setDraft(copyDefinition(initial))
              setOperationError('')
            }}
          >
            Descartar edição
          </Button>
        )}
        {workflow && (
          <Button
            disabled={!valid || save.isPending}
            onClick={() => save.mutate({ copy: true })}
          >
            Criar cópia
          </Button>
        )}
        {!readonly && (
          <Button
            variant="default"
            disabled={!valid || save.isPending || (!!workflow && !dirty)}
            onClick={() => save.mutate({ copy: false })}
          >
            {save.isPending
              ? 'Salvando…'
              : workflow
                ? 'Salvar nova versão'
                : 'Salvar workflow'}
          </Button>
        )}
      </div>
    </section>
  )
}
