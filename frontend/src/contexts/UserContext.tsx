import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

export interface UserConfig {
  userId: string
  roles: string[]
  department: string
}

interface UserContextValue extends UserConfig {
  isAdmin: boolean
  updateConfig: (config: Partial<UserConfig>) => void
  resetConfig: () => void
}

const STORAGE_KEY = 'knowledge_mind_user_config'

const DEFAULT_CONFIG: UserConfig = {
  userId: 'anonymous',
  roles: [],
  department: '',
}

function loadConfig(): UserConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_CONFIG
    const parsed = JSON.parse(raw)
    return {
      userId: typeof parsed.userId === 'string' ? parsed.userId : DEFAULT_CONFIG.userId,
      roles: Array.isArray(parsed.roles) ? parsed.roles.map(String) : DEFAULT_CONFIG.roles,
      department: typeof parsed.department === 'string' ? parsed.department : DEFAULT_CONFIG.department,
    }
  } catch {
    return DEFAULT_CONFIG
  }
}

function saveConfig(config: UserConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  } catch {
    // 忽略 localStorage 写入失败（如隐私模式）
  }
}

const UserContext = createContext<UserContextValue | undefined>(undefined)

export const UserProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [config, setConfig] = useState<UserConfig>(loadConfig)

  useEffect(() => {
    saveConfig(config)
  }, [config])

  const updateConfig = useCallback((patch: Partial<UserConfig>) => {
    setConfig((prev) => ({
      ...prev,
      ...patch,
      roles: patch.roles ?? prev.roles,
    }))
  }, [])

  const resetConfig = useCallback(() => {
    setConfig(DEFAULT_CONFIG)
  }, [])

  const isAdmin = useMemo(
    () => config.roles.some((role) => role.toLowerCase() === 'admin'),
    [config.roles],
  )

  const value = useMemo(
    () => ({
      ...config,
      isAdmin,
      updateConfig,
      resetConfig,
    }),
    [config, isAdmin, updateConfig, resetConfig],
  )

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext)
  if (!ctx) {
    throw new Error('useUser must be used within UserProvider')
  }
  return ctx
}
