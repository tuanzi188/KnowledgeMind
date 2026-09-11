import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import MessageItem from '../components/MessageItem'

describe('MessageItem', () => {
  it('renders user message correctly', () => {
    render(
      <MessageItem
        role="user"
        content="Hello World"
      />
    )
    expect(screen.getByText('Hello World')).toBeTruthy()
    expect(screen.getByText('U')).toBeTruthy()
  })

  it('renders assistant message with markdown', () => {
    render(
      <MessageItem
        role="assistant"
        content="**Bold** text"
      />
    )
    expect(screen.getByText('Bold')).toBeTruthy()
    expect(screen.getByText('K')).toBeTruthy()
  })

  it('renders confidence tag when provided', () => {
    render(
      <MessageItem
        role="assistant"
        content="Answer"
        confidence={0.85}
      />
    )
    expect(screen.getByText('置信度: 85%')).toBeTruthy()
  })

  it('renders fallback tag when isFallback is true', () => {
    render(
      <MessageItem
        role="assistant"
        content="Answer"
        isFallback={true}
      />
    )
    expect(screen.getByText('兜底回答')).toBeTruthy()
  })

  it('renders model and mode info', () => {
    render(
      <MessageItem
        role="assistant"
        content="Answer"
        model="deepseek-chat"
        mode="flash"
      />
    )
    expect(screen.getByText('deepseek-chat')).toBeTruthy()
    expect(screen.getByText('flash')).toBeTruthy()
  })

  it('calls onCopy when copy button clicked', () => {
    const onCopy = vi.fn()
    render(
      <MessageItem
        role="assistant"
        content="Test content"
        onCopy={onCopy}
      />
    )
    const copyButtons = screen.getAllByRole('button')
    const copyBtn = copyButtons.find(btn => btn.querySelector('.anticon-copy'))
    if (copyBtn) {
      fireEvent.click(copyBtn)
      expect(onCopy).toHaveBeenCalledWith('Test content')
    }
  })

  it('renders citation tags when provided', () => {
    render(
      <MessageItem
        role="assistant"
        content="Answer"
        citations={[
          { document_id: '1', document_title: 'Doc One', content: '...', score: 0.9 },
          { document_id: '2', document_title: 'Doc Two', content: '...', score: 0.8 },
        ]}
      />
    )
    expect(screen.getByText('Doc One')).toBeTruthy()
    expect(screen.getByText('Doc Two')).toBeTruthy()
  })
})