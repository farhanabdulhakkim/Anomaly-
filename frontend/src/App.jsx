import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import FieldDetail from './pages/FieldDetail'
import MissionMap from './pages/MissionMap'

const PrivateRoute = ({ children }) => {
  return localStorage.getItem('token') ? children : <Navigate to="/login" />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/fields/:fieldId" element={<PrivateRoute><FieldDetail /></PrivateRoute>} />
        <Route path="/fields/:fieldId/missions/:missionId" element={<PrivateRoute><MissionMap /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  )
}
