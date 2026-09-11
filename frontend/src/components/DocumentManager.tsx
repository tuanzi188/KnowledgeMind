import React, { useState, useEffect, useCallback } from 'react'
import { Modal, Table, Tag, Button, Popconfirm, message, Typography, Space } from 'antd'
import { DeleteOutlined, ReloadOutlined, FileTextOutlined } from '@ant-design/icons'
import { listDocuments, deleteDocument, DocumentInfo } from '../api/client'

const { Text } = Typography

interface DocumentManagerProps {
  open: boolean
  onClose: () => void
}

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const DocumentManager: React.FC<DocumentManagerProps> = ({ open, onClose }) => {
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [loading, setLoading] = useState(false)

  const loadDocuments = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listDocuments()
      setDocuments(result.documents)
    } catch (err) {
      console.error('加载文档列表失败:', err)
      message.error('加载文档列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      loadDocuments()
    }
  }, [open, loadDocuments])

  const handleDelete = async (docId: string, filename: string) => {
    try {
      await deleteDocument(docId)
      message.success(`已删除 ${filename}`)
      await loadDocuments()
    } catch (err) {
      console.error('删除文档失败:', err)
      message.error('删除失败')
    }
  }

  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (text: string) => (
        <Space>
          <FileTextOutlined style={{ color: '#1677ff' }} />
          <Text>{text}</Text>
        </Space>
      ),
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 80,
      render: (text: string) => <Tag>{text.toUpperCase()}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '分块数',
      dataIndex: 'chunks_count',
      key: 'chunks_count',
      width: 80,
    },
    {
      title: '上传时间',
      dataIndex: 'upload_time',
      key: 'upload_time',
      width: 180,
      render: (text: string) => {
        try {
          return new Date(text).toLocaleString('zh-CN')
        } catch {
          return text
        }
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: DocumentInfo) => (
        <Popconfirm
          title="确定删除此文档？"
          description="删除后相关知识点将不可用"
          onConfirm={() => handleDelete(record.document_id, record.filename)}
          okText="删除"
          cancelText="取消"
        >
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ]

  return (
    <Modal
      title="文档管理"
      open={open}
      onCancel={onClose}
      footer={null}
      width={900}
    >
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text type="secondary">共 {documents.length} 个文档</Text>
        <Button icon={<ReloadOutlined />} onClick={loadDocuments} loading={loading}>
          刷新
        </Button>
      </div>
      <Table
        dataSource={documents}
        columns={columns}
        rowKey="document_id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        size="middle"
      />
    </Modal>
  )
}

export default DocumentManager