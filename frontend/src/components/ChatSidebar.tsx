import React from 'react'
import { List, Spin, Button, Popconfirm, Tooltip } from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  MessageOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { ConversationSummary } from '../api/client'

interface ChatSidebarProps {
  visible: boolean
  conversations: ConversationSummary[]
  loading: boolean
  activeConversationId: string | undefined
  onNewConversation: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
  onToggleSidebar: () => void
  formatDate: (ts: number) => string
}

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  visible,
  conversations,
  loading,
  activeConversationId,
  onNewConversation,
  onSelectConversation,
  onDeleteConversation,
  onToggleSidebar,
  formatDate,
}) => {
  return (
    <div
      style={{
        width: visible ? 280 : 0,
        minWidth: visible ? 280 : 0,
        background: 'var(--color-bg-white)',
        borderRight: visible ? '1px solid var(--color-border)' : 'none',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: 'width var(--transition-normal), min-width var(--transition-normal)',
        position: 'relative',
      }}
    >
      {/* 顶部操作区 */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size="small"
          block
          onClick={onNewConversation}
          className="btn-hover"
        >
          新对话
        </Button>
        <Tooltip title={visible ? '收起侧边栏' : '展开侧边栏'}>
          <Button
            type="text"
            size="small"
            icon={visible ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
            onClick={onToggleSidebar}
            style={{ flexShrink: 0 }}
          />
        </Tooltip>
      </div>

      {/* 对话列表 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 12px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="small" />
          </div>
        ) : conversations.length === 0 ? (
          <div
            style={{
              textAlign: 'center',
              padding: '32px 16px',
              color: 'var(--color-text-tertiary)',
              fontSize: 13,
            }}
          >
            <MessageOutlined style={{ fontSize: 24, marginBottom: 8, display: 'block' }} />
            暂无对话记录
            <br />
            <span style={{ fontSize: 11 }}>点击上方按钮开始新对话</span>
          </div>
        ) : (
          <List
            dataSource={conversations}
            renderItem={(conv) => (
              <div
                key={conv.conversation_id}
                onClick={() => onSelectConversation(conv.conversation_id)}
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  marginBottom: 4,
                  background:
                    activeConversationId === conv.conversation_id
                      ? 'var(--color-primary-light)'
                      : 'transparent',
                  transition: 'all var(--transition-fast)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                }}
                onMouseEnter={(e) => {
                  if (activeConversationId !== conv.conversation_id) {
                    e.currentTarget.style.background = 'var(--color-bg)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (activeConversationId !== conv.conversation_id) {
                    e.currentTarget.style.background = 'transparent'
                  }
                }}
              >
                <MessageOutlined
                  style={{
                    color: 'var(--color-text-tertiary)',
                    marginTop: 2,
                    flexShrink: 0,
                    fontSize: 13,
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 13,
                      color: 'var(--color-text)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      fontWeight: activeConversationId === conv.conversation_id ? 500 : 400,
                    }}
                  >
                    {conv.preview || '新对话'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 2 }}>
                    {formatDate(conv.last_updated)} · {conv.turn_count} 轮
                  </div>
                </div>
                <Popconfirm
                  title="确定删除此对话？"
                  onConfirm={(e) => {
                    e?.stopPropagation()
                    onDeleteConversation(conv.conversation_id)
                  }}
                  onCancel={(e) => e?.stopPropagation()}
                  okText="删除"
                  cancelText="取消"
                >
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined style={{ fontSize: 12 }} />}
                    style={{ color: 'var(--color-text-tertiary)', flexShrink: 0 }}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </div>
            )}
          />
        )}
      </div>

    </div>
  )
}

export default ChatSidebar