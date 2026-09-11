import React, { useEffect } from 'react'
import { Drawer, Form, Input, Select, Tag, Button, Space, Typography, Divider, Alert } from 'antd'
import { useUser } from '../contexts/UserContext'

const { Text } = Typography

interface UserSettingsDrawerProps {
  open: boolean
  onClose: () => void
}

const ROLE_OPTIONS = [
  { value: 'admin', label: '管理员 (admin)' },
  { value: 'user', label: '普通用户 (user)' },
  { value: 'analyst', label: '分析师 (analyst)' },
  { value: 'operator', label: '运维 (operator)' },
]

const UserSettingsDrawer: React.FC<UserSettingsDrawerProps> = ({ open, onClose }) => {
  const { userId, department, roles, isAdmin, updateConfig } = useUser()
  const [form] = Form.useForm()

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        userId,
        department,
        roles,
      })
    }
  }, [open, form, userId, department, roles])

  const handleSave = () => {
    const values = form.getFieldsValue()
    updateConfig({
      userId: values.userId?.trim() || 'anonymous',
      department: values.department?.trim() || '',
      roles: Array.isArray(values.roles) ? values.roles.map(String) : [],
    })
    onClose()
  }

  return (
    <Drawer
      title="用户身份配置"
      placement="right"
      width={420}
      onClose={onClose}
      open={open}
      footer={
        <Space style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={handleSave}>
            保存
          </Button>
        </Space>
      }
    >
      <Alert
        message="身份信息会随每次 API 请求发送到后端，用于权限控制和审计。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Form form={form} layout="vertical">
        <Form.Item
          name="userId"
          label="用户 ID"
          rules={[{ required: true, message: '请输入用户 ID' }]}
        >
          <Input placeholder="例如：zhangsan" />
        </Form.Item>

        <Form.Item name="department" label="所属部门">
          <Input placeholder="例如：研发中心" />
        </Form.Item>

        <Form.Item name="roles" label="角色">
          <Select
            mode="tags"
            placeholder="输入或选择角色"
            options={ROLE_OPTIONS}
            allowClear
          />
        </Form.Item>
      </Form>

      <Divider />

      <div>
        <Text type="secondary">当前身份摘要</Text>
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>
            <Text>用户：</Text>
            <Text strong>{userId || 'anonymous'}</Text>
          </div>
          <div>
            <Text>部门：</Text>
            <Text strong>{department || '未设置'}</Text>
          </div>
          <div>
            <Text>角色：</Text>
            {roles.length > 0 ? (
              roles.map((role) => (
                <Tag key={role} color={role.toLowerCase() === 'admin' ? 'red' : 'blue'}>
                  {role}
                </Tag>
              ))
            ) : (
              <Text type="secondary">未设置</Text>
            )}
          </div>
          <div>
            <Text>管理员权限：</Text>
            <Tag color={isAdmin ? 'success' : 'default'}>{isAdmin ? '已开启' : '未开启'}</Tag>
          </div>
        </div>
      </div>
    </Drawer>
  )
}

export default UserSettingsDrawer
