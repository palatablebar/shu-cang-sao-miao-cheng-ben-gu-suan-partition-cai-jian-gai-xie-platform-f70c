import { ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchTable, fetchTables, updateTable } from '../api/tables'
import type { TableDetail, TableListItem } from '../types/table'

export const useTableStore = defineStore('tables', () => {
  const items = ref<TableListItem[]>([])
  const detail = ref<TableDetail | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      items.value = await fetchTables()
      if (!detail.value && items.value.length) await select(items.value[0].id)
      else if (detail.value) await select(detail.value.id)
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function select(id: number) {
    loading.value = true
    try {
      detail.value = await fetchTable(id)
      return detail.value
    } catch (err) {
      error.value = (err as Error).message
      return null
    } finally {
      loading.value = false
    }
  }

  async function save(id: number, payload: { owner?: string; description?: string; suggested_columns?: string[] }) {
    const updated = await updateTable(id, payload)
    detail.value = updated
    const index = items.value.findIndex((item) => item.id === id)
    if (index >= 0) items.value[index] = { ...items.value[index], ...updated }
    return updated
  }

  return { items, detail, loading, error, load, select, save }
})
