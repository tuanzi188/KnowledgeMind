import React from 'react'
import { Button, Typography, Space, Tag } from 'antd'
import { CopyOutlined, LikeOutlined, DislikeOutlined, PaperClipOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import { Citation } from '../api/client'

const { Text } = Typography

interface MessageItemProps {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  confidence?: number
  model?: string
  mode?: string
  isFallback?: boolean
  onCitationClick?: (citation: Citation) => void
  onCopy?: (text: string) => void
}

const getConfidenceColor = (score: number): string => {
  if (score >= 0.7) return 'green'
  if (score >= 0.4) return 'orange'
  return 'red'
}

const MessageItem: React.FC<MessageItemProps> = ({
  role,
  content,
  citations,
  confidence,
  model,
  mode,
  isFallback,
  onCitationClick,
  onCopy,
}) => {
  const isUser = role === 'user'

  return (
    <div style={{
      display: 'flex',
      flexDirection: isUser ? 'row-reverse' : 'row',
      marginBottom: 16,
      gap: 8,
    }}>
      <div style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        background: isUser ? '#1677ff' : '#52c41a',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontSize: 14,
        flexShrink: 0,
      }}>
        {isUser ? 'U' : 'K'}
      </div>
      <div style={{
        maxWidth: '85%',
        background: isUser ? '#1677ff' : '#fff',
        color: isUser ? '#fff' : '#333',
        borderRadius: '12px',
        padding: '12px 16px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
      }}>
        {isUser ? (
          <div>{content}</div>
        ) : (
          <>
            <div className="markdown-body">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
            {citations && citations.length > 0 && (
              <div style={{ marginTop: 12, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
                <Space wrap size={[4, 4]}>
                  {citations.slice(0, 3).map((cit, idx) => (
                    <Tag
                      key={idx}
                      color="blue"
                      style={{ cursor: 'pointer', margin: 0 }}
                      onClick={() => onCitationClick?.(cit)}
                    >
                      <PaperClipOutlined />{' '}
                      {cit.document_title.length > 20
                        ? cit.document_title.slice(0, 20) + '...'
                        : cit.document_title}
                    </Tag>
                  ))}
                  {citations.length > 3 && (
                    <Tag color="default">+{citations.length - 3} 更多</Tag>
                  )}
                </Space>
              </div>
            )}
            <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8, opacity: 0.6 }}>
              {isFallback && <Tag color="orange" style={{ fontSize: 11 }}>兜底回答</Tag>}
              {confidence !== undefined && (
                <Tag color={getConfidenceColor(confidence)} style={{ fontSize: 11 }}>
                  置信度: {(confidence * 100).toFixed(0)}%
                </Tag>
              )}
              {model && <Text style={{ fontSize: 11, color: '#999' }}>{model}</Text>}
              {mode && <Text style={{ fontSize: 11, color: '#999' }}>{mode}</Text>}
              <Button type="text" size="small" icon={<CopyOutlined />} onClick={() => onCopy?.(content)} />
              <Button type="text" size="small" icon={<LikeOutlined />} />
              <Button type="text" size="small" icon={<DislikeOutlined />} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default MessageItem