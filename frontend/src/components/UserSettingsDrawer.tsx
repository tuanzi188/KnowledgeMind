import React, { useState } from 'react'
import { Alert, Button, Descriptions, Drawer, Form, Input, Tag } from 'antd'
import { LoginOutlined } from '@ant-design/icons'
import { extractErrorMessage } from '../api/client'
import { useUser } from '../contexts/UserContext'

interface UserSettingsDrawerProps {
  open: boolean
  onClose: () => void
}

const UserSettingsDrawer: React.FC<UserSettingsDrawerProps> = ({ open, onClose }) => {
  const { userId, department, roles, login } = useUser()
  const [loginPending, setLoginPending] = useState(false)
  const [loginError, setLoginError] = useState('')

  const submitAccessToken = async (formValues: { accessToken: string }) => {
    setLoginPending(true)
    setLoginError('')
    try {
      await login(formValues.accessToken)
    } catch (loginFailure) {
      setLoginError(extractErrorMessage(loginFailure, '登录失败'))
    } finally {
      setLoginPending(false)
    }
  }

  return (
    <Drawer title="账号" placement="right" width={420} open={open} onClose={onClose} destroyOnClose>
      <Descriptions column={1} size="small" style={{ marginBottom: 24 }}>
        <Descriptions.Item label="用户">{userId}</Descriptions.Item>
        <Descriptions.Item label="部门">{department || '未分配'}</Descriptions.Item>
        <Descriptions.Item label="角色">
          {roles.length ? roles.map((role) => <Tag key={role}>{role}</Tag>) : '未分配'}
        </Descriptions.Item>
      </Descriptions>
      {loginError && <Alert type="error" showIcon message={loginError} style={{ marginBottom: 16 }} />}
      <Form layout="vertical" onFinish={submitAccessToken}>
        <Form.Item name="accessToken" label="访问令牌" rules={[{ required: true, message: '请输入访问令牌' }]}>
          <Input.Password autoComplete="off" />
        </Form.Item>
        <Button type="primary" htmlType="submit" icon={<LoginOutlined />} loading={loginPending}>登录</Button>
      </Form>
    </Drawer>
  )
}

export default UserSettingsDrawer
