import { describe, expect, it } from 'vitest'
import { date, duration, eventSummary, parseEvent } from './events'
const event = (payload: string, stage = 'review') =>
  parseEvent({ at: '2026-11-05 12:00:00', stage, payload })
describe('event protocol', () => {
  it('parses a review without losing the raw payload', () => {
    const parsed = event(
      '{"task":"T1","approved":false,"test_result":{"passed":false}}',
    )
    expect(parsed.data.approved).toBe(false)
    expect(eventSummary(parsed)).toContain('reprovada')
    expect(parsed.raw).toEqual(parsed.data)
  })
  it('preserves malformed, scalar, null and array payloads', () => {
    expect(event('{broken').malformed).toBe(true)
    for (const payload of ['null', '42', '[]', '"text"']) {
      expect(event(payload).data).toEqual({})
      expect(event(payload).malformed).toBe(false)
    }
    expect(event('{broken').raw).toBe('{broken')
  })
  it('does not infer success from finished or approval from missing data', () => {
    expect(eventSummary(event('{}', 'finished'))).toBe(
      'Resultado não registrado',
    )
    expect(eventSummary(event('{"status":"blocked"}', 'finished'))).toBe(
      'Bloqueada',
    )
    expect(eventSummary(event('{}'))).toContain('desconhecido')
  })
  it('handles unknown stages and incomplete plans', () => {
    expect(eventSummary(event('{"new_field":true}', 'new_stage'))).toContain(
      'Evento adicional',
    )
    expect(eventSummary(event('{"tasks":"bad"}', 'plan'))).toContain(
      'sem tarefas',
    )
  })
  it('formats missing and invalid dates and measured durations', () => {
    expect(date(null)).toBe('Não registrado')
    expect(date('invalid')).toBe('invalid')
    expect(duration(null)).toBe('—')
    expect(duration(125)).toBe('2m 5s')
    expect(date('2026-11-05 12:00:00')).not.toContain('Invalid')
  })
})

it('validates known review and task fields without losing the original payload', async () => {
  const { reviewPayload, plannedTasks } = await import('./events')
  const e = event(
    '{"approved":"true","test_result":{"passed":"false","output":42},"findings":null}',
  )
  expect(reviewPayload(e.data)).toEqual({
    task: null,
    approved: null,
    findings: [],
    test_suggestions: [],
    test_result: { passed: null, output: null, error: null },
  })
  expect(
    plannedTasks({ tasks: [null, { id: 42, acceptance: 'wrong' }] }),
  ).toEqual([
    { id: null, title: null, instructions: null, acceptance: [], tests: [] },
    { id: null, title: null, instructions: null, acceptance: [], tests: [] },
  ])
  expect(e.raw).toHaveProperty('approved', 'true')
})
