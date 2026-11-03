import { useEffect, useState } from 'react';

// Keyed results keep stale responses out of a newer filter's loading state.
export function useRemote<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const [result, setResult] = useState<{ key: string; data?: T; error?: string }>();
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then(data => {
      if (!controller.signal.aborted) setResult({ key, data });
    }).catch(error => {
      if (!controller.signal.aborted) setResult({ key, error: error instanceof Error ? error.message : '기록을 불러오지 못했어요.' });
    });
    return () => controller.abort();
  }, [key, load]);
  return result?.key === key ? { loading: false, ...result } : { loading: true, data: undefined, error: undefined };
}
