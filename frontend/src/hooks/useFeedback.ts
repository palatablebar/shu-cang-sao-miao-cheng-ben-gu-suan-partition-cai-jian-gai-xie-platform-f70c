import { ref } from 'vue'

const message = ref('')
const kind = ref<'ok' | 'bad' | 'info'>('info')
let timer: ReturnType<typeof setTimeout> | null = null

export function useFeedback() {
  function notify(text: string, tone: 'ok' | 'bad' | 'info' = 'info') {
    message.value = text
    kind.value = tone
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      message.value = ''
    }, 4200)
  }
  function clear() {
    message.value = ''
  }
  return { message, kind, notify, clear }
}
