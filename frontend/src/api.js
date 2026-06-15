import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ── auth ──────────────────────────────────────────────────────────────
const TOKEN_KEY = 'vesta_operator_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

// Attach the operator token to every request.
api.interceptors.request.use((config) => {
  const t = getToken()
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

// On 401, drop the token so the app falls back to the login screen.
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) clearToken()
    return Promise.reject(err)
  }
)

export const login = async (password) => {
  const { data } = await api.post('/auth/login', { password })
  setToken(data.token)
  return data
}
export const logout = () => clearToken()

// ── issuance ──────────────────────────────────────────────────────────
export const getOfferingCandidates = () => api.get('/offerings/candidates')
export const getDeployConfig = (payload) => api.post('/offerings/deploy-config', payload)
export const createOffering = (payload) => api.post('/offerings/', payload)
export const getOfferings = (liveOnly = false) =>
  api.get('/offerings/', { params: { live_only: liveOnly } })

export const getLeads = (params = {}) => api.get('/leads/', { params })
export const getLead = (id) => api.get(`/leads/${id}`)
export const moveToPipeline = (id) => api.post(`/leads/${id}/to-pipeline`)

export const getPipeline = () => api.get('/pipeline/')
export const updateStage = (pipelineId, stage, notes, dealValue) =>
  api.patch(`/pipeline/${pipelineId}/stage`, { stage, notes, deal_value: dealValue })

export const generateEmail = (leadId) => api.get(`/outreach/generate/${leadId}`)
export const sendEmail = (leadId) => api.post(`/outreach/send/${leadId}`)
export const getOutreachHistory = (leadId) => api.get(`/outreach/history/${leadId}`)

export const getAnalytics = () => api.get('/analytics/')
