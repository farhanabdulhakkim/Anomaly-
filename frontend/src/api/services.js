import api from './client'

// Auth
export const register = (data) => api.post('/api/auth/register', data)
export const login = (email, password) => {
  const form = new URLSearchParams()
  form.append('username', email)
  form.append('password', password)
  return api.post('/api/auth/login', form)
}
export const getMe = () => api.get('/api/auth/me')

// Fields
export const createField = (data) => api.post('/api/fields', data)
export const listFields = () => api.get('/api/fields')
export const getField = (id) => api.get(`/api/fields/${id}`)
export const updateField = (id, data) => api.patch(`/api/fields/${id}`, data)
export const getGridGeoJSON = (fieldId) => api.get(`/api/fields/${fieldId}/grid/geojson`)

// Missions
export const createMission = (fieldId, data) => api.post(`/api/fields/${fieldId}/missions`, data)
export const listMissions = (fieldId) => api.get(`/api/fields/${fieldId}/missions`)
export const getMission = (fieldId, missionId) => api.get(`/api/fields/${fieldId}/missions/${missionId}`)
export const uploadTelemetry = (fieldId, missionId, formData) =>
  api.post(`/api/fields/${fieldId}/missions/${missionId}/upload-telemetry`, formData)
export const uploadMissionPlan = (fieldId, missionId, formData) =>
  api.post(`/api/fields/${fieldId}/missions/${missionId}/upload-plan`, formData)
export const getMissionPlan = (fieldId, missionId) =>
  api.get(`/api/fields/${fieldId}/missions/${missionId}/plan`)
export const getAnalytics = (fieldId, missionId) => api.get(`/api/fields/${fieldId}/missions/${missionId}/analytics`)
export const getAnomalyGeoJSON = (fieldId, missionId) => api.get(`/api/fields/${fieldId}/missions/${missionId}/anomalies/geojson`)
export const compareMissions = (fieldId, aId, bId) => api.get(`/api/fields/${fieldId}/missions/compare/${aId}/${bId}`)

// Analytics
export const getFieldTrend = (fieldId) => api.get(`/api/analytics/fields/${fieldId}/trend`)
