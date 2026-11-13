import { ref, type Ref } from 'vue'

export interface AsyncState<T> {
  data: Ref<T | null>
  loading: Ref<boolean>
  error: Ref<string>
  run: (...args: unknown[]) => Promise<T | null>
}

export function useAsync<T>(loader: () => Promise<T>): AsyncState<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref('')
  let lastRequest = 0

  async function run(): Promise<T | null> {
    const request = ++lastRequest
    loading.value = true
    error.value = ''
    try {
      const result = await loader()
      if (request === lastRequest) data.value = result
      return result
    } catch (err) {
      if (request === lastRequest) error.value = (err as Error).message
      return null
    } finally {
      if (request === lastRequest) loading.value = false
    }
  }

  return { data, loading, error, run }
}
