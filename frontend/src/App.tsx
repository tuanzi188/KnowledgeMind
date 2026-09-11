import React, { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ConfigProvider, theme as antTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { UserProvider } from './contexts/UserContext'
import ChatBox from './components/ChatBox'
import PageShell from './components/PageShell'
import AnalyticsDashboard from './pages/AnalyticsDashboard'
import AuditLogs from './pages/AuditLogs'

const App: React.FC = () => {
  const [isDark, setIsDark] = useState(() => {
    return localStorage.getItem('theme') === 'dark'
  })

  const toggleTheme = () => {
    const next = !isDark
    setIsDark(next)
    localStorage.setItem('theme', next ? 'dark' : 'light')
  }

  return (
    <UserProvider>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
          token: {
            colorPrimary: isDark ? '#597ef7' : '#1677ff',
            borderRadius: 8,
          },
        }}
      >
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<ChatBox isDark={isDark} onToggleTheme={toggleTheme} />} />
            <Route
              path="/analytics"
              element={
                <PageShell isDark={isDark} onToggleTheme={toggleTheme}>
                  <AnalyticsDashboard />
                </PageShell>
              }
            />
            <Route
              path="/audit"
              element={
                <PageShell isDark={isDark} onToggleTheme={toggleTheme}>
                  <AuditLogs />
                </PageShell>
              }
            />
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </UserProvider>
  )
}

export default App
