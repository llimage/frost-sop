"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { useEventSource } from "@/hooks/useEventSource";
import { ErrorBoundary } from "@/components/ErrorBoundary";

function SSEProvider({ children }: { children: React.ReactNode }) {
  useEventSource(true);
  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 1000, // 5s cache (缩短以配合SSE实时更新)
            retry: 1,
            refetchOnWindowFocus: true,
          },
        },
      })
  );

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SSEProvider>{children}</SSEProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
