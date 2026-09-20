import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { AuthenticatedProfile, clearAccessToken, getAuthenticatedProfile, verifyAccessToken } from '../api/client'

interface UserContextValue extends AuthenticatedProfile {
  isAdmin: boolean
  login: (accessToken: string) => Promise<void>
  logout: () => void
}

const EMPTY_PROFILE: AuthenticatedProfile = { userId: 'anonymous', roles: [], department: '' }
const UserContext = createContext<UserContextValue | undefined>(undefined)

export const UserProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [profile, setProfile] = useState<AuthenticatedProfile>(EMPTY_PROFILE)

  useEffect(() => {
    let profileRequestActive = true
    getAuthenticatedProfile()
      .then((verifiedProfile) => { if (profileRequestActive) setProfile(verifiedProfile) })
      .catch(() => { if (profileRequestActive) setProfile(EMPTY_PROFILE) })
    return () => { profileRequestActive = false }
  }, [])

  const login = useCallback(async (accessToken: string) => {
    await verifyAccessToken(accessToken.trim())
    // 切换身份时清除页面内的旧会话、文档和流式请求状态。
    window.location.reload()
  }, [])

  const logout = useCallback(() => {
    clearAccessToken()
    window.location.reload()
  }, [])

  const value = useMemo(() => ({
    ...profile,
    isAdmin: profile.roles.includes('admin'),
    login,
    logout,
  }), [profile, login, logout])

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>
}

export function useUser(): UserContextValue {
  const userContextValue = useContext(UserContext)
  if (!userContextValue) throw new Error('用户上下文必须位于 UserProvider 内')
  return userContextValue
}
