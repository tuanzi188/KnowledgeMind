import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'
import WelcomeScreen from '../components/WelcomeScreen'

describe('WelcomeScreen', () => {
  it('renders welcome message', () => {
    render(<WelcomeScreen onUpload={vi.fn()} />)
    expect(screen.getByText('欢迎使用 KnowledgeMind')).toBeTruthy()
    expect(screen.getByText('上传企业文档，即刻获得基于 AI 的智能知识检索与问答')).toBeTruthy()
  })
})
