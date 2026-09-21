<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const greenhouses = ref([])
const error = ref('')
const editingId = ref(null)
const filterStatus = ref('')

function todayInputValue(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const form = reactive({
  greenhouseId: '',
  workDate: todayInputValue(),
  suitCount: 4,
  maskCount: 8,
  issuer: '',
  status: 'open',
})

const statusLabel = {
  open: '开放',
  closed: '已关',
}

const editingRow = computed(() => list.value.find((r) => r.id === editingId.value))
// 已关单禁止改数量：前端禁用输入，后端同样拦截
const quantitiesLocked = computed(() => editingRow.value?.status === 'closed')

function formatError(e, fallback) {
  const data = e.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  return Object.entries(data)
    .map(([k, v]) => `${k}: ${[].concat(v).join('；')}`)
    .join('；')
}

function resetForm() {
  editingId.value = null
  form.greenhouseId = greenhouses.value[0]?.id || ''
  form.workDate = todayInputValue()
  form.suitCount = 4
  form.maskCount = 8
  form.issuer = ''
  form.status = 'open'
}

async function loadGreenhouses() {
  const { data } = await api.get('/greenhouses/')
  greenhouses.value = data.results || data
  if (!form.greenhouseId && greenhouses.value.length) {
    form.greenhouseId = greenhouses.value[0].id
  }
}

async function load() {
  error.value = ''
  try {
    const params = {}
    if (filterStatus.value) params.status = filterStatus.value
    const { data } = await api.get('/ppe-issues/', { params })
    list.value = data.results || data
  } catch {
    error.value = '加载防护领用失败'
  }
}

function edit(row) {
  editingId.value = row.id
  form.greenhouseId = row.greenhouseId
  form.workDate = row.workDate
  form.suitCount = row.suitCount
  form.maskCount = row.maskCount
  form.issuer = row.issuer
  form.status = row.status
}

async function save() {
  error.value = ''
  const payload = {
    greenhouseId: Number(form.greenhouseId),
    workDate: form.workDate,
    suitCount: form.suitCount,
    maskCount: form.maskCount,
    issuer: form.issuer,
    status: form.status,
  }
  try {
    if (editingId.value) {
      await api.put(`/ppe-issues/${editingId.value}/`, payload)
    } else {
      await api.post('/ppe-issues/', payload)
    }
    resetForm()
    await load()
  } catch (e) {
    error.value = formatError(e, '保存失败')
  }
}

async function closeIssue(row) {
  if (!confirm(`确认关闭 ${row.greenhouseName} ${row.workDate} 的防护领用单？关闭后数量不可再改。`)) return
  error.value = ''
  try {
    await api.patch(`/ppe-issues/${row.id}/`, { status: 'closed' })
    await load()
  } catch (e) {
    error.value = formatError(e, '关单失败')
  }
}

async function remove(id) {
  if (!confirm('确认删除该防护领用单？')) return
  await api.delete(`/ppe-issues/${id}/`)
  await load()
}

onMounted(async () => {
  await loadGreenhouses()
  await load()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>喷药日防护领用</h1>
        <p>按温室登记喷药作业日防护物资领用；开放期间该温室分区禁止新建轮灌</p>
      </div>
      <div class="actions">
        <select v-model="filterStatus" @change="load">
          <option value="">全部状态</option>
          <option value="open">开放</option>
          <option value="closed">已关</option>
        </select>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑领用单' : '新建领用单' }}</h3>
      <div class="form-grid">
        <label>
          所属温室
          <select v-model="form.greenhouseId">
            <option v-for="g in greenhouses" :key="g.id" :value="g.id">
              {{ g.name }}
            </option>
          </select>
        </label>
        <label>作业日<input v-model="form.workDate" type="date" /></label>
        <label>
          防护服件数
          <input v-model.number="form.suitCount" type="number" min="1" step="1" :disabled="quantitiesLocked" />
        </label>
        <label>
          口罩件数
          <input v-model.number="form.maskCount" type="number" min="1" step="1" :disabled="quantitiesLocked" />
        </label>
        <label>发放人<input v-model="form.issuer" required placeholder="姓名" /></label>
        <label>
          状态
          <select v-model="form.status">
            <option value="open">开放</option>
            <option value="closed">已关</option>
          </select>
        </label>
      </div>
      <p v-if="quantitiesLocked" class="hint" style="margin:8px 0 0">该单已关，数量已锁定，仅可调整温室/作业日/发放人/状态。</p>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="save">保存</button>
        <button v-if="editingId" class="btn ghost" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>作业日</th>
            <th>温室</th>
            <th>防护服</th>
            <th>口罩</th>
            <th>发放人</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>{{ row.workDate }}</td>
            <td>{{ row.greenhouseName }}</td>
            <td>{{ row.suitCount }} 件</td>
            <td>{{ row.maskCount }} 件</td>
            <td>{{ row.issuer }}</td>
            <td>
              <span class="badge" :class="row.status === 'open' ? 'running' : 'done'">
                {{ statusLabel[row.status] || row.status }}
              </span>
            </td>
            <td class="actions">
              <button class="btn ghost" @click="edit(row)">编辑</button>
              <button v-if="row.status === 'open'" class="btn secondary" @click="closeIssue(row)">关单</button>
              <button class="btn danger" @click="remove(row.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
