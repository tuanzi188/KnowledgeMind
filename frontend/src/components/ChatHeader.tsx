import React, { useState } from 'react'
import { Button, Dropdown, Badge, Tooltip, Popover, Typography, Tag } from 'antd'
import {
  UploadOutlined,
  FileTextOutlined,
  UserOutlined,
  QuestionCircleOutlined,
  BellOutlined,
  SettingOutlined,
  LogoutOutlined,
  SunOutlined,
  MoonOutlined,
  ReloadOutlined,
  BarChartOutlined,
  SafetyOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { Link, useLocation } from 'react-router-dom'
import { ConnectionState } from './ConnectionStatus'
import { useUser } from '../contexts/UserContext'
import UserSettingsDrawer from './UserSettingsDrawer'

const { Text } = Typography

interface ChatHeaderProps {
  isDark: boolean
  stats: { total_chunks: number } | null
  connectionState: ConnectionState
  onToggleTheme: () => void
  onOpenUpload: () => void
  onOpenDocumentManager: () => void
  onReconnect: () => void
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  isDark,
  stats,
  connectionState,
  onToggleTheme,
  onOpenUpload,
  onOpenDocumentManager,
  onReconnect,
}) => {
  const [notificationCount] = useState(0)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { userId, isAdmin } = useUser()
  const location = useLocation()

  const userMenuItems = [
    { key: 'settings', icon: <SettingOutlined />, label: '个人设置' },
    { type: 'divider' as const },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
  ]

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') console.log('退出登录')
    else if (key === 'settings') setSettingsOpen(true)
  }

  const navItems = [
    { key: '/', label: '对话', icon: <MessageOutlined />, path: '/' },
    { key: '/analytics', label: '数据分析', icon: <BarChartOutlined />, path: '/analytics' },
    { key: '/audit', label: '审计日志', icon: <SafetyOutlined />, path: '/audit', adminOnly: true },
  ]

  const helpContent = (
    <div style={{ maxWidth: 240 }}>
      <div style={{ marginBottom: 8 }}>
        <Text strong>快捷键</Text>
      </div>
      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 2 }}>
        <div>Enter 发送消息</div>
        <div>Shift + Enter 换行</div>
        <div>Ctrl + K 新建对话</div>
        <div>Ctrl + / 查看快捷键</div>
      </div>
      <div style={{ marginTop: 8, marginBottom: 4 }}>
        <Text strong>支持格式</Text>
      </div>
      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
        PDF · Word · Excel · TXT · Markdown
      </div>
    </div>
  )

  const baseBadgeStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '5px 10px',
    borderRadius: 'var(--radius-md)',
    fontSize: 12,
    fontWeight: 500,
    transition: 'all var(--transition-fast)',
    cursor: 'default',
    userSelect: 'none',
  }

  const renderConnectionBadge = () => {
    if (connectionState === 'connecting') {
      return (
        <Tooltip title="正在检查后端服务...">
          <div style={{ ...baseBadgeStyle, background: 'var(--color-primary-light)', color: 'var(--color-primary)' }}>
            <div style={{ position: 'relative', width: 14, height: 14, flexShrink: 0 }}>
              <svg width="14" height="14" viewBox="0 0 14 14" className="connection-ring">
                <circle
                  cx="7" cy="7" r="5.5"
                  fill="none"
                  stroke="var(--color-primary)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeDasharray="26"
                  strokeDashoffset="8"
                />
              </svg>
            </div>
            <span>连接中</span>
          </div>
        </Tooltip>
      )
    }

    if (connectionState === 'connected') {
      return (
        <Tooltip title="后端服务已连接">
          <div style={{ ...baseBadgeStyle, background: '#f6ffed', color: 'var(--color-success)' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-success)', flexShrink: 0 }} />
            <span>已连接</span>
          </div>
        </Tooltip>
      )
    }

    return (
      <Tooltip title="后端服务不可用，点击重试">
        <div
          onClick={onReconnect}
          style={{
            ...baseBadgeStyle,
            background: '#fff2f0',
            color: 'var(--color-error)',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#ffdfdc' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = '#fff2f0' }}
        >
          <ReloadOutlined style={{ fontSize: 11, flexShrink: 0 }} />
          <span>连接断开</span>
        </div>
      </Tooltip>
    )
  }

  return (
    <div
      className="chat-header"
      style={{
        padding: '12px 24px',
        background: 'var(--color-bg-white)',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        transition: 'background var(--transition-normal)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: 36, height: 36,
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, #1677ff 0%, #0958d9 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: 18, fontWeight: 700, flexShrink: 0,
          }}
        >
          K
        </div>
        <div style={{ lineHeight: 1.3 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text)' }}>
            KnowledgeMind
          </div>
          <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', letterSpacing: 1.2 }}>
            ENTERPRISE INTELLIGENCE
            {stats && (
              <span style={{ marginLeft: 8, color: 'var(--color-text-secondary)' }}>
                · {stats.total_chunks} 片段
              </span>
            )}
          </div>
        </div>

        <div style={{ width: 1, height: 24, background: 'var(--color-border)', margin: '0 8px' }} />

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
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-md)',
                    textDecoration: 'none',
                    fontSize: 13,
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
        {renderConnectionBadge()}

        <div style={{ width: 1, height: 20, background: 'var(--color-border)', margin: '0 4px' }} />

        <Button
          type="primary"
          icon={<UploadOutlined />}
          size="small"
          className="btn-hover"
          onClick={onOpenUpload}
        >
          上传文档
        </Button>

        <Button
          size="small"
          icon={<FileTextOutlined />}
          onClick={onOpenDocumentManager}
          className="btn-hover"
        >
          文档管理
        </Button>

        <div style={{ width: 1, height: 20, background: 'var(--color-border)', margin: '0 4px' }} />

        <Tooltip title="消息通知">
          <Badge count={notificationCount} size="small" offset={[-2, 2]}>
            <Button type="text" size="small" icon={<BellOutlined style={{ fontSize: 16 }} />} className="btn-hover" />
          </Badge>
        </Tooltip>

        <Popover content={helpContent} title="帮助中心" trigger="click" placement="bottomRight">
          <Tooltip title="帮助中心">
            <Button type="text" size="small" icon={<QuestionCircleOutlined style={{ fontSize: 16 }} />} className="btn-hover" />
          </Tooltip>
        </Popover>

        <Tooltip title={isDark ? '切换亮色模式' : '切换暗色模式'}>
          <Button
            type="text" size="small"
            icon={isDark ? <SunOutlined style={{ fontSize: 16 }} /> : <MoonOutlined style={{ fontSize: 16 }} />}
            onClick={onToggleTheme}
            className="btn-hover"
          />
        </Tooltip>

        {isAdmin && (
          <Tag color="red" style={{ marginRight: 4 }}>
            管理员
          </Tag>
        )}

        <Dropdown
          menu={{ items: userMenuItems, onClick: handleUserMenuClick }}
          trigger={['click']}
          placement="bottomRight"
        >
          <Button
            type="text" size="small"
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

      <UserSettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default ChatHeader
