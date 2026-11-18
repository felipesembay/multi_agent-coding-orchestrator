import type { WorkflowDefinition, WorkflowStep } from '../types'
import { sessionToken } from './api'

export type DefinitionIssue = {
  loc: (string | number)[]
  msg: string
  type: string
}
export type DefinitionValidation = { valid: boolean; issues: DefinitionIssue[] }

export function newDefinition(): WorkflowDefinition {
  return {
    schema_version: 1,
    name: 'Novo workflow',
    steps: [
      {
        id: 'plan',
        type: 'plan',
        role: 'planner',
        requires: ['planning', 'structured_output'],
      },
      {
        id: 'impl',
        type: 'implement',
        role: 'implementer',
        requires: ['code_edit'],
        per_task: true,
        max_attempts: 3,
      },
      {
        id: 'tests',
        type: 'test',
        per_task: true,
        command_profile: 'server_default',
      },
      {
        id: 'review',
        type: 'review',
        role: 'reviewer',
        requires: ['review', 'structured_output'],
        per_task: true,
        on_reject: 'impl',
      },
    ],
    limits: { max_total_steps: 200, max_duration_s: 14400, budget_usd: null },
    approval: {
      require_tests: true,
      require_reviewer: true,
      human_gate_after_plan: false,
    },
  }
}

export function copyName(name: string) {
  return Array.from(name).slice(0, 110).join('') + ' (cópia)'
}
export function copyDefinition(
  definition: WorkflowDefinition,
): WorkflowDefinition {
  return structuredClone(definition)
}

export function topologyValid(steps: WorkflowStep[]) {
  if (
    !steps.length ||
    steps[0].type !== 'plan' ||
    steps.slice(1).some((s) => s.type === 'plan')
  )
    return false
  const indices = steps.flatMap((s, index) => (s.per_task ? [index] : []))
  if (indices.length && indices.at(-1)! - indices[0] + 1 !== indices.length)
    return false
  return steps.every((step, index) => {
    if (step.type !== 'review' || !step.on_reject) return true
    const target = steps.findIndex((s) => s.id === step.on_reject)
    return (
      target >= 0 &&
      target < index &&
      steps[target].type === 'implement' &&
      steps.slice(target, index + 1).every((s) => s.per_task)
    )
  })
}

export function movedSteps(steps: WorkflowStep[], from: number, to: number) {
  if (
    from < 0 ||
    to < 0 ||
    from >= steps.length ||
    to >= steps.length ||
    from === to
  )
    return null
  const next = [...steps]
  next.splice(to, 0, ...next.splice(from, 1))
  return topologyValid(next) ? next : null
}

export function optionalStep(
  type: 'document' | 'test' | 'human_gate',
  steps: WorkflowStep[],
): WorkflowStep {
  const prefix = type === 'human_gate' ? 'gate' : type
  let count = 1
  const used = new Set(steps.map((s) => s.id))
  while (used.has(`${prefix}-${count}`)) count++
  const base = { id: `${prefix}-${count}`, type, per_task: false }
  if (type === 'document')
    return { ...base, role: 'documenter', requires: ['text'] }
  if (type === 'test') return { ...base, command_profile: 'server_default' }
  return base
}

export function finiteNumbers(definition: WorkflowDefinition) {
  return (
    definition.steps.every(
      (s) => s.max_attempts === undefined || Number.isFinite(s.max_attempts),
    ) &&
    (!definition.limits ||
      (Number.isFinite(definition.limits.max_total_steps) &&
        Number.isFinite(definition.limits.max_duration_s) &&
        (definition.limits.budget_usd === null ||
          Number.isFinite(definition.limits.budget_usd))))
  )
}

export async function validateDefinition(
  definition: WorkflowDefinition,
  signal: AbortSignal,
): Promise<DefinitionValidation> {
  const token = await sessionToken(signal)
  const response = await fetch('/api/workflows/validate', {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      'X-Orchestrator-CSRF': token,
    },
    body: JSON.stringify({ definition }),
  })
  const data = await response.json()
  if (response.status === 422 && Array.isArray(data.detail)) {
    return {
      valid: false,
      issues: data.detail.map((item: DefinitionIssue) => ({
        loc: item.loc,
        msg: item.msg,
        type: item.type,
      })),
    }
  }
  if (!response.ok || data.valid !== true)
    throw new Error('Não foi possível validar o workflow. Tente novamente.')
  return { valid: true, issues: [] }
}

export function issueLabel(
  issue: DefinitionIssue,
  definition: WorkflowDefinition,
) {
  const labels = new Map<string, string>([
    ['name', 'Nome'],
    ['max_attempts', 'Tentativas'],
    ['max_total_steps', 'Total de passos'],
    ['max_duration_s', 'Duração'],
    ['budget_usd', 'Orçamento'],
    ['per_task', 'Por tarefa'],
    ['on_reject', 'Retorno na rejeição'],
    ['approval', 'Aprovação'],
    ['steps', 'Etapas'],
  ])
  const index = issue.loc.indexOf('steps')
  const stepIndex = index >= 0 ? issue.loc[index + 1] : null
  const prefix =
    typeof stepIndex === 'number'
      ? `Etapa ${definition.steps[stepIndex]?.id ?? stepIndex + 1}: `
      : ''
  const field = [...issue.loc]
    .reverse()
    .find((key) => typeof key === 'string' && labels.has(key))
  return (
    prefix +
    (typeof field === 'string' ? labels.get(field) + ': ' : '') +
    issue.msg
  )
}
