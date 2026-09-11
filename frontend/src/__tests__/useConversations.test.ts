import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

// Mock the API client module
vi.mock('../api/client', () => ({
  getConversations: vi.fn().mockResolvedValue({ conversations: [] }),
  getConversation: vi.fn().mockResolvedValue({ turns: [] }),
  deleteConversation: vi.fn().mockResolvedValue({ success: true }),
}))

import { useConversations } from '../hooks/useConversations'
import { getConversations, getConversation, deleteConversation } from '../api/client'

describe('useConversations', () => {

  it('initializes with empty conversations', async () => {
    const { result } = renderHook(() => useConversations())
    await waitFor(() => {
      expect(result.current.conversations).toEqual([])
      expect(result.current.conversationsLoading).toBe(false)
    })
    expect(result.current.activeConversationId).toBeUndefined()
  })

  it('startNewConversation clears active id', () => {
    const { result } = renderHook(() => useConversations())
    act(() => {
      result.current.startNewConversation()
    })
    expect(result.current.activeConversationId).toBeUndefined()
  })

  it('loadConversations fetches and sets conversations', async () => {
    const mockConversations = [
      { conversation_id: '1', preview: '对话1', turn_count: 3, created_at: 1704067200, last_updated: 1704067200 },
      { conversation_id: '2', preview: '对话2', turn_count: 5, created_at: 1704153600, last_updated: 1704153600 },
    ]
    vi.mocked(getConversations).mockResolvedValueOnce({ conversations: mockConversations })

    const { result } = renderHook(() => useConversations())

    await waitFor(() => {
      expect(result.current.conversations).toEqual(mockConversations)
    })
  })

  it('deleteConv removes conversation and reloads', async () => {
    const { result } = renderHook(() => useConversations())

    await act(async () => {
      await result.current.deleteConv('1')
    })

    expect(deleteConversation).toHaveBeenCalledWith('1')
  })
})