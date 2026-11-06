import type { ParsedEvent, Payload, RawEvent } from '../types'
export function object(value: unknown): Payload {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Payload)
    : {}
}
export function parseEvent(event: RawEvent): ParsedEvent {
  try {
    const raw: unknown =
      typeof event.payload === 'string'
        ? JSON.parse(event.payload)
        : event.payload
    return { ...event, data: object(raw), raw, malformed: false }
  } catch {
    return { ...event, data: {}, raw: event.payload, malformed: true }
  }
}
export function text(value: unknown, fallback = 'Não registrado'): string {
  return typeof value === 'string' || typeof value === 'number'
    ? String(value)
    : fallback
}
export function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}
export function date(value: string | null) {
  if (!value) return 'Não registrado'
  const parsed = new Date(
    /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value.replace(' ', 'T') + 'Z',
  )
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat('pt-BR', {
        dateStyle: 'short',
        timeStyle: 'medium',
      }).format(parsed)
}
export function duration(seconds: number | null) {
  if (seconds === null || !Number.isFinite(seconds)) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.floor(seconds / 3600) ? `${Math.floor(seconds / 3600)}h ` : ''}${Math.floor(seconds / 60) % 60}m ${Math.round(seconds % 60)}s`
}
export const statusLabels: Record<string, string> = {
  queued: 'Na fila',
  interrupted: 'Interrompida',
  running: 'Em andamento',
  blocked: 'Bloqueada',
  error: 'Erro',
  ready_for_human_review: 'Revisão humana',
  completed: 'Concluída',
  success: 'Concluída',
  succeeded: 'Concluída',
  failed: 'Falhou',
  unknown: 'Desconhecido',
}
export const stageLabels: Record<string, string> = {
  stage_started: 'Etapa iniciada',
  manager_error: 'Falha do gerenciador',
  started: 'Execução iniciada',
  plan: 'Planejamento',
  implementation: 'Implementação',
  review: 'Revisão e testes',
  finished: 'Workflow finalizado',
  blocked: 'Execução bloqueada',
  error: 'Falha registrada',
  resumed: 'Execução retomada',
  agent_fallback: 'Troca de provider',
}
export function eventSummary(event: ParsedEvent): string {
  const p = event.data
  if (event.malformed) return 'Payload inválido · conteúdo original preservado'
  switch (event.stage) {
    case 'stage_started':
      return `${text(p.role)} · ${text(p.stage)}`
    case 'manager_error':
      return text(p.message)
    case 'started':
      return text(p.repo)
    case 'plan':
      return Array.isArray(p.tasks)
        ? `${p.tasks.length} tarefas planejadas`
        : 'Plano sem tarefas registradas'
    case 'implementation':
      return `${text(p.task, 'Tarefa desconhecida')} · tentativa ${text(p.attempt, 'não registrada')}`
    case 'review':
      return `${text(p.task, 'Tarefa desconhecida')} · ${p.approved === true ? 'revisão aprovada' : p.approved === false ? 'revisão reprovada' : 'resultado desconhecido'}`
    case 'finished':
      return (
        statusLabels[text(p.status)] ??
        text(p.status, 'Resultado não registrado')
      )
    case 'error':
      return text(p.message)
    case 'blocked':
      return 'Requer intervenção do operador'
    case 'resumed':
      return `${text(p.task)} · entrada em ${text(p.entry_point)}`
    case 'agent_fallback':
      return `${text(p.primary)} → ${text(p.fallback)}`
    default:
      return 'Evento adicional · consulte os dados originais'
  }
}

export function reviewPayload(data: Payload): import('../types').ReviewPayload {
  const result = object(data.test_result)
  const string = (value: unknown) => (typeof value === 'string' ? value : null)
  const boolean = (value: unknown) =>
    typeof value === 'boolean' ? value : null
  return {
    task: string(data.task),
    approved: boolean(data.approved),
    findings: list(data.findings),
    test_suggestions: list(data.test_suggestions),
    test_result: {
      passed: boolean(result.passed),
      output: string(result.output),
      error: string(result.error),
    },
  }
}
export function plannedTasks(data: Payload): import('../types').Task[] {
  const string = (value: unknown) => (typeof value === 'string' ? value : null)
  return list(data.tasks).map((raw) => {
    const task = object(raw)
    return {
      id: string(task.id),
      title: string(task.title),
      instructions: string(task.instructions),
      acceptance: list(task.acceptance),
      tests: list(task.tests),
    }
  })
}
