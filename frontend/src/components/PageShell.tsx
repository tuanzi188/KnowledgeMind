import React, { useState } from 'react'
import { Button, Dropdown, Tooltip, Tag } from 'antd'
import {
  UserOutlined,
  SettingOutlined,
  SunOutlined,
  MoonOutlined,
  LogoutOutlined,
  MessageOutlined,
  BarChartOutlined,
  SafetyOutlined,
} from '@ant-design/icons'
import { Link, useLocation } from 'react-router-dom'
import { useUser } from '../contexts/UserContext'
import UserSettingsDrawer from './UserSettingsDrawer'

interface PageShellProps {
  children: React.ReactNode
  isDark?: boolean
  onToggleTheme?: () => void
}

const PageShell: React.FC<PageShellProps> = ({ children, isDark, onToggleTheme }) => {
  const location = useLocation()
  const { userId, isAdmin } = useUser()
  const [settingsOpen, setSettingsOpen] = useState(false)

  const navItems = [
    { key: '/', label: '对话', icon: <MessageOutlined />, path: '/' },
    { key: '/analytics', label: '数据分析', icon: <BarChartOutlined />, path: '/analytics' },
    { key: '/audit', label: '审计日志', icon: <SafetyOutlined />, path: '/audit', adminOnly: true },
  ]

  const userMenuItems = [
    { key: 'settings', icon: <SettingOutlined />, label: '个人设置' },
    { type: 'divider' as const },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
  ]

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)' }}>
      <header
        style={{
          padding: '12px 24px',
          background: 'var(--color-bg-white)',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 12, textDecoration: 'none' }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, #1677ff 0%, #0958d9 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontSize: 18,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              K
            </div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text)' }}>KnowledgeMind</div>
          </Link>

          <nav style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {navItems
              .filter((item) => !item.adminOnly || isAdmin)
              .map((item) => {
                const active = location.pathname === item.path
                return (
                  <Link
                    key={item.key}
                    to={item.path}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      textDecoration: 'none',
                      fontSize: 14,
                      fontWeight: active ? 500 : 400,
                      color: active ? 'var(--color-primary)' : 'var(--color-text)',
                      background: active ? 'var(--color-primary-light)' : 'transparent',
                      transition: 'all var(--transition-fast)',
                    }}
                  >
                    {item.icon}
                    {item.label}
                  </Link>
                )
              })}
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isAdmin && (
            <Tag color="red" style={{ marginRight: 8 }}>
              管理员
            </Tag>
          )}

          <Tooltip title={isDark ? '切换亮色模式' : '切换暗色模式'}>
            <Button
              type="text"
              size="small"
              icon={isDark ? <SunOutlined style={{ fontSize: 16 }} /> : <MoonOutlined style={{ fontSize: 16 }} />}
              onClick={onToggleTheme}
              className="btn-hover"
            />
          </Tooltip>

          <Dropdown
            menu={{
              items: userMenuItems,
              onClick: ({ key }) => {
                if (key === 'settings') setSettingsOpen(true)
              },
            }}
            trigger={['click']}
            placement="bottomRight"
          >
            <Button
              type="text"
              size="small"
              icon={<UserOutlined />}
              className="btn-hover"
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <span style={{ fontSize: 13, maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {userId || 'anonymous'}
              </span>
            </Button>
          </Dropdown>
        </div>
      </header>

      <main>{children}</main>

      <UserSettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default PageShell
