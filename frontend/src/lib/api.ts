import { useQuery } from '@tanstack/react-query'
import type { Overview, RunDetail, RunPage, Settings } from '../types'
export async function request<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`/api${path}`, { signal })
  if (!response.ok)
    throw new Error(
      response.status === 404
        ? 'Recurso não encontrado. Verifique se a API foi reiniciada com a versão atual.'
        : `A API retornou um erro (${response.status}).`,
    )
  try {
    return (await response.json()) as T
  } catch {
    throw new Error(
      'Resposta inválida da API. Verifique o proxy /api e o backend.',
    )
  }
}
export function useRuns(params: URLSearchParams, interval: number) {
  const query = params.toString()
  return useQuery({
    queryKey: ['runs', query],
    queryFn: ({ signal }) =>
      request<RunPage>(`/runs?paginated=true&${query}`, signal),
    refetchInterval: interval || false,
  })
}
export function useOverview(interval: number) {
  return useQuery({
    queryKey: ['overview'],
    queryFn: ({ signal }) => request<Overview>('/overview', signal),
    refetchInterval: interval || false,
  })
}
export function useRun(id: string, interval: number) {
  return useQuery({
    queryKey: ['run', id],
    queryFn: ({ signal }) =>
      request<RunDetail>(`/runs/${encodeURIComponent(id)}`, signal),
    enabled: !!id,
    refetchInterval: (query) =>
      ['queued', 'running'].includes(query.state.data?.manager_status ?? '')
        ? 3000
        : interval || false,
  })
}
export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: ({ signal }) => request<Settings>('/settings', signal),
    staleTime: 60_000,
  })
}
