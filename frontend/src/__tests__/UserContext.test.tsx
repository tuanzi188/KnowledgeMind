import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('../api/client', () => ({
  getAuthenticatedProfile: vi.fn(),
  verifyAccessToken: vi.fn(),
  clearAccessToken: vi.fn(),
}))

import { getAuthenticatedProfile } from '../api/client'
import { UserProvider, useUser } from '../contexts/UserContext'

describe('服务端可信身份', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('忽略浏览器中自行填写的管理员角色', async () => {
    localStorage.setItem('knowledge_mind_user_config', JSON.stringify({ userId: 'root', roles: ['admin'] }))
    vi.mocked(getAuthenticatedProfile).mockResolvedValue({ userId: 'alice', roles: ['user'], department: '研发' })
    const profileHook = renderHook(() => useUser(), { wrapper: UserProvider })
    await waitFor(() => expect(profileHook.result.current.userId).toBe('alice'))
    expect(profileHook.result.current.isAdmin).toBe(false)
    expect(profileHook.result.current.department).toBe('研发')
  })

  it('只展示后端确认的管理员角色', async () => {
    vi.mocked(getAuthenticatedProfile).mockResolvedValue({ userId: 'operator', roles: ['admin'], department: '' })
    const profileHook = renderHook(() => useUser(), { wrapper: UserProvider })
    await waitFor(() => expect(profileHook.result.current.isAdmin).toBe(true))
  })

  it('认证失败时不保留本地伪造身份', async () => {
    localStorage.setItem('knowledge_mind_user_config', JSON.stringify({ roles: ['admin'] }))
    vi.mocked(getAuthenticatedProfile).mockRejectedValue(new Error('认证失败'))
    const profileHook = renderHook(() => useUser(), { wrapper: UserProvider })
    await waitFor(() => expect(getAuthenticatedProfile).toHaveBeenCalled())
    expect(profileHook.result.current.isAdmin).toBe(false)
    expect(profileHook.result.current.userId).toBe('anonymous')
  })
})
