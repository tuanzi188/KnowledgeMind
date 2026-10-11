import { useState, useCallback, useRef } from 'react'
import { message } from 'antd'
import { sendChat, sendChatStream, Citation, extractErrorMessage } from '../api/client'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  confidence?: number
  model?: string
  mode?: string
  reasoning_content?: string
  isFallback?: boolean
  timestamp: number
}

export interface UseChatReturn {
  messages: Message[]
  loading: boolean
  streamingContent: string
  conversationId: string | undefined
  setConversationId: (id: string | undefined) => void
  setMessages: (messages: Message[]) => void
  sendMessage: (query: string) => Promise<void>
  stopGeneration: () => void
  loadHistoryMessages: (turns: { query: string; answer: string; timestamp: number }[]) => void
  startNew: () => void
}

export function useChat(
  onConversationUpdate?: () => void,
): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [conversationId, setConversationId] = useState<string | undefined>()
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (query: string) => {
    if (loading) return

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    setStreamingContent('')

    const abortController = new AbortController()
    abortRef.current = abortController

    try {
      const response = await sendChatStream(
        query,
        (token) => {
          setStreamingContent(prev => prev + token)
        },
        (result) => {
          const assistantMsg: Message = {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: result.answer,
            citations: result.citations,
            confidence: result.confidence,
            model: result.model_used,
            mode: result.reasoning_mode_used,
            reasoning_content: result.reasoning_content,
            isFallback: result.is_fallback,
            timestamp: Date.now(),
          }
          setMessages(prev => [...prev, assistantMsg])
          setStreamingContent('')
          setConversationId(result.conversation_id)
          onConversationUpdate?.()
        },
        (error, code) => {
          console.error('流式请求失败:', error, code)
          const detail = extractErrorMessage(error, '请求失败，请检查网络连接或稍后重试')
          const userMsg = code ? `[${code}] ${detail}` : detail
          message.error(userMsg)
          const errMsg: Message = {
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: `抱歉，请求处理失败：${userMsg}`,
            timestamp: Date.now(),
          }
          setMessages(prev => [...prev, errMsg])
          setStreamingContent('')
        },
        conversationId,
        abortController.signal,
      )
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        // 用户主动停止生成，保存当前已流式输出的文本
        setStreamingContent(currentStreaming => {
          if (currentStreaming && currentStreaming.trim()) {
            const stoppedMsg: Message = {
              id: `stopped-${Date.now()}`,
              role: 'assistant',
              content: currentStreaming,
              timestamp: Date.now(),
            }
            setMessages(prev => [...prev, stoppedMsg])
          }
          return ''
        })
      } else {
        console.error('发送消息失败:', err)
        const detail = extractErrorMessage(err, '请求失败，请检查网络连接或稍后重试')
        const code = err?.response?.status
        const userMsg = code ? `[${code}] ${detail}` : detail
        message.error(userMsg)
        const errMsg: Message = {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `抱歉，请求处理失败：${userMsg}`,
          timestamp: Date.now(),
        }
        setMessages(prev => [...prev, errMsg])
        setStreamingContent('')
      }
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }, [loading, conversationId, onConversationUpdate])

  const stopGeneration = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
  }, [])

  const loadHistoryMessages = useCallback(
    (turns: { query: string; answer: string; timestamp: number }[]) => {
      const msgs: Message[] = turns.flatMap((turn, index) => [
        {
          id: `user-${index}`,
          role: 'user' as const,
          content: turn.query,
          timestamp: turn.timestamp,
        },
        {
          id: `assistant-${index}`,
          role: 'assistant' as const,
          content: turn.answer,
          timestamp: turn.timestamp,
        },
      ])
      setMessages(msgs)
    },
    [],
  )

  const startNew = useCallback(() => {
    setMessages([])
    setConversationId(undefined)
    setStreamingContent('')
  }, [])

  return {
    messages,
    loading,
    streamingContent,
    conversationId,
    setConversationId,
    setMessages,
    sendMessage,
    stopGeneration,
    loadHistoryMessages,
    startNew,
  }
}