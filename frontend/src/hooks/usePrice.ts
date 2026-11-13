import { computed, type Ref } from 'vue'
import { toGib } from '../utils/format'

/** 前端只做展示换算：扫描字节 → 费用，单位价格由后端 BudgetPolicy 提供。 */
export function usePrice(costPerGib: Ref<number>) {
  const unit = computed(() => costPerGib.value || 0.3)
  function cost(bytes: number): number {
    return toGib(bytes) * unit.value
  }
  function monthlyCost(bytes: number, days = 30): number {
    return cost(bytes) * days
  }
  return { unit, cost, monthlyCost }
}
