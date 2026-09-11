import React, { useState } from 'react'
import { Modal, Upload, message, Typography, Table, Tag, Button, Form, Input, Switch, Space, Divider } from 'antd'
import { UploadOutlined, InboxOutlined } from '@ant-design/icons'
import { uploadDocument, getStats, AclOptions, extractErrorMessage } from '../api/client'

const { Dragger } = Upload
const { Text } = Typography

interface DocumentUploadProps {
  open: boolean
  onClose: () => void
}

interface UploadResult {
  name: string
  status: 'success' | 'error'
  message?: string
}

const DocumentUpload: React.FC<DocumentUploadProps> = ({ open, onClose }) => {
  const [fileList, setFileList] = useState<any[]>([])
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<UploadResult[]>([])
  const [showResults, setShowResults] = useState(false)
  const [form] = Form.useForm()

  const handleUpload = async () => {
    setUploading(true)
    setShowResults(false)
    setResults([])

    const acl: AclOptions = {
      isPublic: form.getFieldValue('isPublic') === true,
      allowedUsers: form.getFieldValue('allowedUsers')?.trim() || undefined,
      allowedDepartments: form.getFieldValue('allowedDepartments')?.trim() || undefined,
      allowedRoles: form.getFieldValue('allowedRoles')?.trim() || undefined,
    }

    const nextResults: UploadResult[] = []
    for (const file of fileList) {
      const rawFile = file.originFileObj || file
      try {
        const result = await uploadDocument(rawFile, undefined, acl)
        nextResults.push({
          name: file.name,
          status: 'success',
          message: `已解析 ${result.chunks_count} 个片段`,
        })
      } catch (err: any) {
        nextResults.push({
          name: file.name,
          status: 'error',
          message: extractErrorMessage(err, '上传失败'),
        })
      }
    }

    setResults(nextResults)
    setShowResults(true)
    setUploading(false)

    const successCount = nextResults.filter((r) => r.status === 'success').length
    const failCount = nextResults.length - successCount

    if (failCount === 0) {
      message.success(`上传完成: ${successCount} 个文件成功`)
      setFileList([])
      getStats().catch(() => {})
      onClose()
    } else if (successCount === 0) {
      message.error(`上传失败: ${failCount} 个文件`)
    } else {
      message.warning(`${successCount} 成功, ${failCount} 失败`)
    }
  }

  const resultColumns = [
    {
      title: '文件名',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '结果',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={status === 'success' ? 'success' : 'error'}>
          {status === 'success' ? '成功' : '失败'}
        </Tag>
      ),
    },
    {
      title: '说明',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true,
    },
  ]

  return (
    <Modal
      title="上传知识文档"
      open={open}
      onCancel={() => {
        setFileList([])
        setResults([])
        setShowResults(false)
        onClose()
      }}
      footer={[
        <Button
          key="cancel"
          onClick={() => {
            setFileList([])
            setResults([])
            setShowResults(false)
            onClose()
          }}
        >
          取消
        </Button>,
        <Button
          key="upload"
          type="primary"
          onClick={handleUpload}
          loading={uploading}
          disabled={fileList.length === 0}
          icon={<UploadOutlined />}
        >
          上传 ({fileList.length} 个文件)
        </Button>,
      ]}
      width={640}
    >
      <Dragger
        multiple
        accept=".pdf,.txt,.md,.docx,.xlsx,.csv"
        fileList={fileList}
        onChange={(info) => setFileList(info.fileList)}
        beforeUpload={() => false}
      >
        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">支持 PDF、Word、Excel、TXT、Markdown 格式</p>
      </Dragger>

      <Divider />

      <Form form={form} layout="vertical" initialValues={{ isPublic: false }}>
        <Text strong>访问权限配置（ACL）</Text>
        <div style={{ marginTop: 8, marginBottom: 16 }}>
          <Text type="secondary">未配置指定用户/部门/角色时，仅上传者本人可访问。</Text>
        </div>

        <Form.Item
          name="isPublic"
          valuePropName="checked"
          style={{ marginBottom: 12 }}
        >
          <Switch checkedChildren="公开" unCheckedChildren="私有" />
        </Form.Item>

        <Space direction="vertical" style={{ width: '100%' }}>
          <Form.Item
            name="allowedUsers"
            label="指定用户 ID"
            style={{ marginBottom: 8 }}
          >
            <Input placeholder="多个用户用英文逗号分隔，例如：user1,user2" />
          </Form.Item>

          <Form.Item
            name="allowedDepartments"
            label="指定部门"
            style={{ marginBottom: 8 }}
          >
            <Input placeholder="多个部门用英文逗号分隔，例如：研发,产品" />
          </Form.Item>

          <Form.Item
            name="allowedRoles"
            label="指定角色"
            style={{ marginBottom: 0 }}
          >
            <Input placeholder="多个角色用英文逗号分隔，例如：admin,analyst" />
          </Form.Item>
        </Space>
      </Form>

      {showResults && results.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Text strong>上传结果</Text>
          <Table
            dataSource={results}
            columns={resultColumns}
            rowKey="name"
            pagination={false}
            size="small"
            style={{ marginTop: 8 }}
          />
        </div>
      )}
    </Modal>
  )
}

export default DocumentUpload
