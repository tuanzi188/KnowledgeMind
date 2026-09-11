import React, { useState, useRef, useEffect } from 'react'
import { Input, Button, Tooltip, Popover, Typography } from 'antd'
import {
  SendOutlined,
  ClearOutlined,
  FileSearchOutlined,
  PlusCircleOutlined,
} from '@ant-design/icons'

const { Text } = Typography

interface ChatInputProps {
  loading: boolean
  onSend: (text: string) => void
  onClearContext?: () => void
  onNewConversation?: () => void
  onReferenceDocument?: () => void
}

const ChatInput: React.FC<ChatInputProps> = ({
  loading,
  onSend,
  onClearContext,
  onNewConversation,
  onReferenceDocument,
}) => {
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)
  const textareaRef = useRef<any>(null)

  const isEmpty = value.trim().length === 0

  const handleSend = () => {
    const text = value.trim()
    if (!text || loading) return
    onSend(text)
    setValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClear = () => {
    setValue('')
    textareaRef.current?.focus()
  }

  const shortcutContent = (
    <div style={{ minWidth: 180 }}>
      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 2.2 }}>
        <div><Text keyboard>Enter</Text> 发送消息</div>
        <div><Text keyboard>Shift</Text> + <Text keyboard>Enter</Text> 换行</div>
        <div><Text keyboard>Ctrl</Text> + <Text keyboard>K</Text> 新建对话</div>
        <div><Text keyboard>Esc</Text> 清空输入</div>
      </div>
    </div>
  )

  return (
    <div
      style={{
        padding: '12px 16px 16px',
        borderTop: '1px solid var(--color-border)',
        background: 'var(--color-bg-white)',
        transition: 'background var(--transition-normal)',
      }}
    >
      {/* 输入框容器 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 8,
          padding: '8px 12px',
          borderRadius: 'var(--radius-lg)',
          border: `1.5px solid ${focused ? 'var(--color-primary)' : 'var(--color-border)'}`,
          background: 'var(--color-bg)',
          transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
          boxShadow: focused ? '0 0 0 3px rgba(22, 119, 255, 0.08)' : 'none',
        }}
      >
        {/* 左侧快捷功能栏 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, marginBottom: 2 }}>
          <Tooltip title="新建对话">
            <Button
              type="text"
              size="small"
              icon={<PlusCircleOutlined />}
              onClick={onNewConversation}
              style={{ color: 'var(--color-text-tertiary)' }}
            />
          </Tooltip>
          <Tooltip title="引用文档">
            <Button
              type="text"
              size="small"
              icon={<FileSearchOutlined />}
              onClick={onReferenceDocument}
              style={{ color: 'var(--color-text-tertiary)' }}
            />
          </Tooltip>
          {value && (
            <Tooltip title="清空输入">
              <Button
                type="text"
                size="small"
                icon={<ClearOutlined />}
                onClick={handleClear}
                style={{ color: 'var(--color-text-tertiary)' }}
              />
            </Tooltip>
          )}
        </div>

        {/* 文本输入区 */}
        <Input.TextArea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="输入问题，基于上传文档智能问答"
          autoSize={{ minRows: 1, maxRows: 6 }}
          disabled={loading}
          variant="borderless"
          style={{
            flex: 1,
            padding: '4px 0',
            fontSize: 14,
            lineHeight: 1.6,
            resize: 'none',
          }}
        />

        {/* 发送按钮 */}
        <Tooltip title={isEmpty ? '请输入内容' : '发送 (Enter)'}>
          <Button
            type="primary"
            icon={<SendOutlined />}
            aria-label="发送"
            onClick={handleSend}
            loading={loading}
            disabled={isEmpty || loading}
            className="btn-hover"
            style={{
              minWidth: 36,
              height: 36,
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: isEmpty ? 0.4 : 1,
              transition: 'all var(--transition-fast)',
              flexShrink: 0,
            }}
          />
        </Tooltip>
      </div>

      {/* 底部快捷键提示 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginTop: 6,
        }}
      >
        <Popover
          content={shortcutContent}
          title="快捷键说明"
          trigger="hover"
          placement="topRight"
        >
          <Text
            style={{
              fontSize: 11,
              color: 'var(--color-text-tertiary)',
              cursor: 'help',
              userSelect: 'none',
              transition: 'color var(--transition-fast)',
            }}
          >
            Enter 发送 · Shift+Enter 换行
          </Text>
        </Popover>
      </div>
    </div>
  )
}

export default ChatInput