<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const greenhouses = ref([])
const openCheck = ref(null)
const error = ref('')
const editingId = ref(null)
const filterGreenhouseId = ref('')
const filterStatus = ref('')

function todayInputValue() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const form = reactive({
  greenhouseId: '',
  workDate: todayInputValue(),
  suitCount: 1,
  maskCount: 1,
  issuer: '',
  status: 'open',
})

const statusLabel = { open: '开放', closed: '已关' }
const editingRow = computed(() => list.value.find((r) => r.id === editingId.value))
const editingClosed = computed(() => editingRow.value?.status === 'closed')

function resetForm() {
  editingId.value = null
  form.greenhouseId = greenhouses.value[0]?.id || ''
  form.workDate = todayInputValue()
  form.suitCount = 1
  form.maskCount = 1
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
    if (filterGreenhouseId.value) params.greenhouseId = filterGreenhouseId.value
    if (filterStatus.value) params.status = filterStatus.value
    const { data } = await api.get('/ppe-issues/', { params })
    list.value = data.results || data
  } catch {
    error.value = '加载防护领用失败'
  }
}

async function loadOpenCheck() {
  const { data } = await api.get('/ppe-issues/open-check/')
  openCheck.value = data
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
    await Promise.all([load(), loadOpenCheck()])
  } catch (e) {
    error.value = JSON.stringify(e.response?.data || '保存失败')
  }
}

async function closeIssue(row) {
  if (!confirm(`确认关闭 ${row.greenhouseName} ${row.workDate} 的领用单？关闭后数量不可再改。`)) return
  error.value = ''
  try {
    await api.patch(`/ppe-issues/${row.id}/`, { status: 'closed' })
    if (editingId.value === row.id) resetForm()
    await Promise.all([load(), loadOpenCheck()])
  } catch (e) {
    error.value = JSON.stringify(e.response?.data || '关闭失败')
  }
}

async function remove(id) {
  if (!confirm('确认删除该领用单？')) return
  await api.delete(`/ppe-issues/${id}/`)
  if (editingId.value === id) resetForm()
  await Promise.all([load(), loadOpenCheck()])
}

onMounted(async () => {
  await loadGreenhouses()
  await Promise.all([load(), loadOpenCheck()])
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>喷药日防护领用</h1>
        <p>开放领用期间，所属温室的分区禁止新建轮灌；同温室同日只许一张开放单</p>
      </div>
      <div class="actions">
        <select v-model="filterGreenhouseId" @change="load">
          <option value="">全部温室</option>
          <option v-for="g in greenhouses" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
        <select v-model="filterStatus" @change="load">
          <option value="">全部状态</option>
          <option value="open">开放</option>
          <option value="closed">已关</option>
        </select>
      </div>
    </div>

    <div v-if="openCheck" class="stats" style="margin-bottom: 18px">
      <div class="stat">
        <div class="label">开放领用单（核对）</div>
        <div class="value">{{ openCheck.openIssueCount }}</div>
      </div>
      <div class="stat">
        <div class="label">涉及温室（与温室列表标记一致）</div>
        <div class="value">{{ openCheck.openGreenhouseCount }}</div>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑领用单' : '新建领用单' }}</h3>
      <div class="form-grid">
        <label>
          所属温室
          <select v-model="form.greenhouseId">
            <option v-for="g in greenhouses" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </label>
        <label>作业日<input v-model="form.workDate" type="date" required /></label>
        <label>
          防护服件数
          <input v-model.number="form.suitCount" type="number" min="1" step="1" :disabled="editingClosed" />
        </label>
        <label>
          口罩件数
          <input v-model.number="form.maskCount" type="number" min="1" step="1" :disabled="editingClosed" />
        </label>
        <label>发放人<input v-model="form.issuer" required /></label>
        <label>
          状态
          <select v-model="form.status" :disabled="editingClosed">
            <option value="open">开放</option>
            <option value="closed">已关</option>
          </select>
        </label>
      </div>
      <p v-if="editingClosed" class="hint" style="margin:8px 0 0">该单已关闭，数量与状态不可再改。</p>
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
            <th>ID</th>
            <th>所属温室</th>
            <th>作业日</th>
            <th>防护服</th>
            <th>口罩</th>
            <th>发放人</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.greenhouseName }}</td>
            <td>{{ row.workDate }}</td>
            <td>{{ row.suitCount }}</td>
            <td>{{ row.maskCount }}</td>
            <td>{{ row.issuer }}</td>
            <td>
              <span class="badge" :class="row.status">{{ statusLabel[row.status] || row.status }}</span>
            </td>
            <td class="actions">
              <button class="btn ghost" @click="edit(row)">编辑</button>
              <button v-if="row.status === 'open'" class="btn secondary" @click="closeIssue(row)">关闭</button>
              <button class="btn danger" @click="remove(row.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
