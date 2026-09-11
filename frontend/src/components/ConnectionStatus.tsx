import React from 'react'
import { Tooltip } from 'antd'
import {
  CheckCircleFilled,
  CloseCircleFilled,
  ReloadOutlined,
} from '@ant-design/icons'

export type ConnectionState = 'connecting' | 'connected' | 'disconnected'

interface ConnectionStatusProps {
  state: ConnectionState
  onReconnect?: () => void
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ state, onReconnect }) => {
  if (state === 'connecting') {
    return (
      <Tooltip title="正在连接服务...">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-primary-light)',
            cursor: 'default',
            transition: 'all var(--transition-normal)',
          }}
        >
          {/* 环形加载动效 */}
          <div style={{ position: 'relative', width: 18, height: 18, flexShrink: 0 }}>
            <svg width="18" height="18" viewBox="0 0 18 18" className="connection-ring">
              <circle
                cx="9"
                cy="9"
                r="7"
                fill="none"
                stroke="var(--color-primary)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeDasharray="33"
                strokeDashoffset="10"
              />
            </svg>
          </div>
          <span style={{ fontSize: 12, color: 'var(--color-primary)', fontWeight: 500 }}>
            连接中...
          </span>
        </div>
      </Tooltip>
    )
  }

  if (state === 'connected') {
    return (
      <Tooltip title="服务已连接">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            borderRadius: 'var(--radius-md)',
            background: '#f6ffed',
            transition: 'all var(--transition-normal)',
          }}
        >
          <CheckCircleFilled style={{ color: 'var(--color-success)', fontSize: 16 }} />
          <span style={{ fontSize: 12, color: 'var(--color-success)', fontWeight: 500 }}>
            已连接
          </span>
        </div>
      </Tooltip>
    )
  }

  return (
    <Tooltip title="点击重新连接">
      <div
        onClick={onReconnect}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          borderRadius: 'var(--radius-md)',
          background: '#fff2f0',
          cursor: 'pointer',
          transition: 'all var(--transition-normal)',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#ffdfdc'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#fff2f0'
        }}
      >
        <CloseCircleFilled style={{ color: 'var(--color-error)', fontSize: 16 }} />
        <span style={{ fontSize: 12, color: 'var(--color-error)', fontWeight: 500 }}>
          连接断开，点击重连
        </span>
        <ReloadOutlined style={{ fontSize: 12, color: 'var(--color-error)', marginLeft: 'auto' }} />
      </div>
    </Tooltip>
  )
}

export default ConnectionStatus