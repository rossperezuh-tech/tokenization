import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

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
