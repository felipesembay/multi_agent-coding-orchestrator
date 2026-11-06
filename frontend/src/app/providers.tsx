import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
const client = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 2000, retry: 1, refetchOnWindowFocus: true },
  },
})
export function Providers({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
