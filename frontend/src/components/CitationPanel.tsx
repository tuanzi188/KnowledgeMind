import React from 'react'
import { Drawer, Typography, Tag, Space, Button } from 'antd'
import { CloseOutlined, FileTextOutlined, LinkOutlined } from '@ant-design/icons'
import { Citation } from '../api/client'

const { Text, Title, Paragraph } = Typography

interface CitationPanelProps {
  citation: Citation | null
  onClose: () => void
}

const CitationPanel: React.FC<CitationPanelProps> = ({ citation, onClose }) => {
  return (
    <Drawer
      title={
        <Space>
          <FileTextOutlined />
          <span>引用详情</span>
        </Space>
      }
      placement="right"
      width={400}
      onClose={onClose}
      open={!!citation}
      extra={<Button type="text" icon={<CloseOutlined />} onClick={onClose} />}
    >
      {citation && (
        <div>
          <Title level={5}>{citation.document_title}</Title>
          <Space wrap style={{ marginBottom: 16 }}>
            {citation.page && <Tag color="blue">页码: {citation.page}</Tag>}
            {citation.paragraph && <Tag color="green">段落: {citation.paragraph}</Tag>}
            <Tag color="orange">相关度: {(citation.score * 100).toFixed(0)}%</Tag>
          </Space>
          <div style={{
            background: '#f6f8fa',
            borderRadius: 8,
            padding: 12,
            marginBottom: 16,
          }}>
            <Text type="secondary" style={{ fontSize: 12 }}>引用内容</Text>
            <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
              {citation.content}
            </Paragraph>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button icon={<LinkOutlined />} size="small">查看原文</Button>
            <Button icon={<FileTextOutlined />} size="small">下载文档</Button>
          </div>
        </div>
      )}
    </Drawer>
  )
}

export default CitationPanel