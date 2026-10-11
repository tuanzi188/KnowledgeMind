import React from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import KanbanBoard from '../components/KanbanBoard'

const createKanbanDataTransfer = (): DataTransfer => {
  const payloads = new Map<string, string>()

  return {
    effectAllowed: 'none',
    dropEffect: 'none',
    clearData: (format?: string) => {
      if (format) payloads.delete(format)
      else payloads.clear()
    },
    getData: (format: string) => payloads.get(format) ?? '',
    setData: (format: string, value: string) => payloads.set(format, value),
    get types() {
      return Array.from(payloads.keys())
    },
    files: [] as unknown as FileList,
    items: [] as unknown as DataTransferItemList,
    setDragImage: () => undefined,
  } as DataTransfer
}

const dropKanbanTask = (taskCard: HTMLElement, destinationColumn: HTMLElement) => {
  const sharedTransfer = createKanbanDataTransfer()
  fireEvent.dragStart(taskCard, { dataTransfer: sharedTransfer })
  fireEvent.dragOver(destinationColumn, { dataTransfer: sharedTransfer })
  fireEvent.drop(destinationColumn, { dataTransfer: sharedTransfer })
  fireEvent.dragEnd(taskCard, { dataTransfer: sharedTransfer })
}

const chooseKanbanSelectOption = (accessibleName: string, optionText: string) => {
  fireEvent.mouseDown(screen.getByRole('combobox', { name: accessibleName }))
  fireEvent.click(screen.getByText(optionText))
}

describe('KanbanBoard', () => {
  it('按目标列添加任务，并在优先级筛选时保持真实列计数', () => {
    render(<KanbanBoard />)

    fireEvent.change(screen.getByLabelText('新任务标题'), {
      target: { value: '新增知识整理任务' },
    })
    chooseKanbanSelectOption('新任务所在列', '放入已完成')
    fireEvent.click(screen.getByRole('button', { name: /添加任务/ }))

    const completedColumn = screen.getByLabelText('已完成任务列')
    expect(screen.getByLabelText('任务卡片：新增知识整理任务')).toBeInTheDocument()
    expect(within(completedColumn).getByLabelText('3 个任务')).toBeInTheDocument()

    chooseKanbanSelectOption('按优先级筛选任务', '高优先级')

    expect(screen.queryByLabelText('任务卡片：新增知识整理任务')).not.toBeInTheDocument()
    expect(within(completedColumn).getByLabelText('3 个任务')).toBeInTheDocument()
    expect(screen.getByText('没有符合筛选条件的任务')).toBeInTheDocument()
  })

  it('筛选期间可拖拽任务跨列，完成后同步更新列计数', () => {
    render(<KanbanBoard />)
    chooseKanbanSelectOption('按优先级筛选任务', '高优先级')

    const taskCard = screen.getByLabelText('任务卡片：优化检索结果排序')
    const completedColumn = screen.getByLabelText('已完成任务列')
    dropKanbanTask(taskCard, completedColumn)

    expect(screen.getByLabelText('任务卡片：优化检索结果排序')).toBeInTheDocument()
    expect(within(screen.getByLabelText('进行中任务列')).getByLabelText('1 个任务')).toBeInTheDocument()
    expect(within(completedColumn).getByLabelText('3 个任务')).toBeInTheDocument()
    expect(screen.getByText('没有符合筛选条件的任务')).toBeInTheDocument()
  })

  it('双击编辑标题，Enter 保存且 Esc 取消', () => {
    render(<KanbanBoard />)

    fireEvent.doubleClick(screen.getByText('整理用户访谈纪要'))
    const firstEditor = screen.getByLabelText('编辑任务标题')
    fireEvent.change(firstEditor, { target: { value: '已更新的访谈纪要' } })
    fireEvent.keyDown(firstEditor, { key: 'Enter', code: 'Enter' })

    expect(screen.getByText('已更新的访谈纪要')).toBeInTheDocument()

    fireEvent.doubleClick(screen.getByText('已更新的访谈纪要'))
    const secondEditor = screen.getByLabelText('编辑任务标题')
    fireEvent.change(secondEditor, { target: { value: '这项修改应取消' } })
    fireEvent.keyDown(secondEditor, { key: 'Escape', code: 'Escape' })

    expect(screen.getByText('已更新的访谈纪要')).toBeInTheDocument()
    expect(screen.queryByText('这项修改应取消')).not.toBeInTheDocument()
  })

  it('非法释放不移动任务，清空一列后显示空态', () => {
    render(<KanbanBoard />)

    const board = screen.getByLabelText('任务看板')
    const firstTaskCard = screen.getByLabelText('任务卡片：补充空状态文案')
    const invalidDropTransfer = createKanbanDataTransfer()
    fireEvent.dragStart(firstTaskCard, { dataTransfer: invalidDropTransfer })
    fireEvent.drop(board, { dataTransfer: invalidDropTransfer })
    fireEvent.dragEnd(firstTaskCard, { dataTransfer: invalidDropTransfer })

    expect(screen.getByLabelText('任务卡片：补充空状态文案')).toBeInTheDocument()
    const completedColumn = screen.getByLabelText('已完成任务列')
    expect(within(completedColumn).getByLabelText('2 个任务')).toBeInTheDocument()

    const todoColumn = screen.getByLabelText('待办任务列')
    dropKanbanTask(screen.getByLabelText('任务卡片：补充空状态文案'), todoColumn)
    dropKanbanTask(screen.getByLabelText('任务卡片：整理版本发布清单'), todoColumn)

    expect(within(completedColumn).getByLabelText('0 个任务')).toBeInTheDocument()
    expect(screen.getByText('暂无任务')).toBeInTheDocument()
  })
})
