import React, { FormEvent, KeyboardEvent, useRef, useState } from 'react'
import { Button, Input, Select } from 'antd'
import type { InputRef } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import './KanbanBoard.css'

type TaskPriority = 'high' | 'medium' | 'low'
type PriorityFilter = 'all' | TaskPriority

const KANBAN_COLUMNS = [
  { id: 'todo', title: '待办', accent: 'todo' },
  { id: 'in-progress', title: '进行中', accent: 'progress' },
  { id: 'done', title: '已完成', accent: 'done' },
] as const

type KanbanStatus = (typeof KANBAN_COLUMNS)[number]['id']

interface KanbanTask {
  id: string
  title: string
  assignee: string
  priority: TaskPriority
  status: KanbanStatus
}

interface KanbanTaskCardProps {
  task: KanbanTask
  isEditing: boolean
  isDragging: boolean
  draftTitle: string
  onTitleChange: (value: string) => void
  onBeginEditing: (task: KanbanTask) => void
  onSaveEditing: (taskId: string) => void
  onCancelEditing: (taskId: string) => void
  onDragStart: (event: React.DragEvent<HTMLElement>, taskId: string) => void
  onDragEnd: () => void
}

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

const PRIORITY_FILTER_OPTIONS = [
  { value: 'all', label: '全部优先级' },
  { value: 'high', label: '高优先级' },
  { value: 'medium', label: '中优先级' },
  { value: 'low', label: '低优先级' },
]

const NEW_TASK_STATUS_OPTIONS = KANBAN_COLUMNS.map(({ id, title }) => ({
  value: id,
  label: `放入${title}`,
}))

const INITIAL_TASKS: KanbanTask[] = [
  { id: 'task-brief', title: '整理用户访谈纪要', assignee: '林静', priority: 'high', status: 'todo' },
  { id: 'task-flow', title: '梳理知识库导入流程', assignee: '周明', priority: 'medium', status: 'todo' },
  { id: 'task-permission', title: '确认文档访问权限', assignee: '陈可', priority: 'low', status: 'todo' },
  { id: 'task-search', title: '优化检索结果排序', assignee: '周明', priority: 'high', status: 'in-progress' },
  { id: 'task-prototype', title: '完成设置页原型', assignee: '林静', priority: 'medium', status: 'in-progress' },
  { id: 'task-empty', title: '补充空状态文案', assignee: '陈可', priority: 'low', status: 'done' },
  { id: 'task-release', title: '整理版本发布清单', assignee: '林静', priority: 'medium', status: 'done' },
]

const TASK_DRAG_TYPE = 'application/x-kanban-task-id'

const KanbanTaskCard: React.FC<KanbanTaskCardProps> = ({
  task,
  isEditing,
  isDragging,
  draftTitle,
  onTitleChange,
  onBeginEditing,
  onSaveEditing,
  onCancelEditing,
  onDragStart,
  onDragEnd,
}) => {
  const handleTitleKeyDown = (event: KeyboardEvent<HTMLHeadingElement>) => {
    if (event.key === 'Enter' || event.key === 'F2') {
      event.preventDefault()
      onBeginEditing(task)
    }
  }

  const handleEditorKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
      event.preventDefault()
      onSaveEditing(task.id)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      onCancelEditing(task.id)
    }
  }

  return (
    <article
      className={`kanban-task-card${isEditing ? ' kanban-task-card--editing' : ''}${isDragging ? ' kanban-task-card--dragging' : ''}`}
      aria-label={`任务卡片：${task.title}`}
      draggable={!isEditing}
      onDragStart={(event) => onDragStart(event, task.id)}
      onDragEnd={onDragEnd}
    >
      <div className="kanban-task-card__topline">
        <span className={`kanban-priority kanban-priority--${task.priority}`}>
          <span className="kanban-priority__dot" aria-hidden="true" />
          {PRIORITY_LABELS[task.priority]}
        </span>
      </div>

      {isEditing ? (
        <Input
          autoFocus
          maxLength={100}
          aria-label="编辑任务标题"
          className="kanban-task-editor"
          value={draftTitle}
          onChange={(event) => onTitleChange(event.target.value)}
          onBlur={() => onSaveEditing(task.id)}
          onKeyDown={handleEditorKeyDown}
        />
      ) : (
        <h3
          className="kanban-task-card__title"
          tabIndex={0}
          aria-label={`任务标题：${task.title}，按 Enter 键编辑`}
          onDoubleClick={() => onBeginEditing(task)}
          onKeyDown={handleTitleKeyDown}
        >
          {task.title}
        </h3>
      )}

      <div className="kanban-task-card__footer">
        <span className={`kanban-assignee${task.assignee === '未分配' ? ' kanban-assignee--unassigned' : ''}`}>
          <span className="kanban-assignee__avatar" aria-hidden="true">
            {task.assignee === '未分配' ? '未' : task.assignee.slice(0, 1)}
          </span>
          <span>{task.assignee}</span>
        </span>
      </div>
    </article>
  )
}

const KanbanBoard: React.FC = () => {
  const [tasks, setTasks] = useState<KanbanTask[]>(INITIAL_TASKS)
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all')
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [newTaskStatus, setNewTaskStatus] = useState<KanbanStatus>('todo')
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null)
  const [dragOverStatus, setDragOverStatus] = useState<KanbanStatus | null>(null)
  const taskIdCounter = useRef(0)
  const cancelledBlurTaskId = useRef<string | null>(null)
  const newTaskInputRef = useRef<InputRef>(null)

  const handleAddTask = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const title = newTaskTitle.trim()
    if (!title) {
      newTaskInputRef.current?.focus()
      return
    }

    const taskId = `task-${Date.now().toString(36)}-${taskIdCounter.current.toString(36)}`
    taskIdCounter.current += 1
    setTasks((currentTasks) => [
      ...currentTasks,
      {
        id: taskId,
        title,
        assignee: '未分配',
        priority: 'medium',
        status: newTaskStatus,
      },
    ])
    setNewTaskTitle('')
    newTaskInputRef.current?.focus()
  }

  const handleBeginEditing = (task: KanbanTask) => {
    cancelledBlurTaskId.current = null
    setEditingTaskId(task.id)
    setDraftTitle(task.title)
  }

  const handleSaveEditing = (taskId: string) => {
    if (cancelledBlurTaskId.current === taskId) {
      cancelledBlurTaskId.current = null
      return
    }

    const nextTitle = draftTitle.trim()
    if (nextTitle) {
      setTasks((currentTasks) =>
        currentTasks.map((task) => (task.id === taskId ? { ...task, title: nextTitle } : task)),
      )
    }
    setEditingTaskId(null)
    setDraftTitle('')
  }

  const handleCancelEditing = (taskId: string) => {
    cancelledBlurTaskId.current = taskId
    setEditingTaskId(null)
    setDraftTitle('')
  }

  const handleDragStart = (event: React.DragEvent<HTMLElement>, taskId: string) => {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData(TASK_DRAG_TYPE, taskId)
    setDraggedTaskId(taskId)
  }

  const handleDragEnd = () => {
    setDraggedTaskId(null)
    setDragOverStatus(null)
  }

  const handleColumnDragOver = (event: React.DragEvent<HTMLElement>, status: KanbanStatus) => {
    const hasInternalTask = Array.from(event.dataTransfer.types).includes(TASK_DRAG_TYPE)
    if (!hasInternalTask) {
      event.dataTransfer.dropEffect = 'none'
      return
    }

    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    setDragOverStatus(status)
  }

  const handleColumnDrop = (event: React.DragEvent<HTMLElement>, status: KanbanStatus) => {
    const taskId = event.dataTransfer.getData(TASK_DRAG_TYPE)
    if (!taskId) {
      setDragOverStatus(null)
      return
    }

    event.preventDefault()
    setTasks((currentTasks) => {
      const taskExists = currentTasks.some((task) => task.id === taskId)
      if (!taskExists) return currentTasks
      return currentTasks.map((task) => (task.id === taskId ? { ...task, status } : task))
    })
    setDraggedTaskId(null)
    setDragOverStatus(null)
  }

  const filteredTasks = tasks.filter(
    (task) => priorityFilter === 'all' || task.priority === priorityFilter,
  )

  return (
    <main className="kanban-page">
      <div className="kanban-page__inner">
        <header className="kanban-page__header">
          <div>
            <p className="kanban-page__eyebrow">任务管理</p>
            <h1>看板任务</h1>
          </div>
          <label className="kanban-filter">
            <span>优先级筛选</span>
            <Select<PriorityFilter>
              aria-label="按优先级筛选任务"
              value={priorityFilter}
              options={PRIORITY_FILTER_OPTIONS}
              onChange={setPriorityFilter}
            />
          </label>
        </header>

        <form className="kanban-add-form" onSubmit={handleAddTask}>
          <Input
            ref={newTaskInputRef}
            aria-label="新任务标题"
            placeholder="输入任务标题"
            maxLength={100}
            value={newTaskTitle}
            onChange={(event) => setNewTaskTitle(event.target.value)}
          />
          <Select<KanbanStatus>
            aria-label="新任务所在列"
            value={newTaskStatus}
            options={NEW_TASK_STATUS_OPTIONS}
            onChange={setNewTaskStatus}
          />
          <Button type="primary" htmlType="submit" icon={<PlusOutlined />} disabled={!newTaskTitle.trim()}>
            添加任务
          </Button>
        </form>

        <div className="kanban-board-scroll">
          <div className="kanban-board" aria-label="任务看板">
            {KANBAN_COLUMNS.map((column) => {
              const columnTasks = tasks.filter((task) => task.status === column.id)
              const visibleColumnTasks = filteredTasks.filter((task) => task.status === column.id)
              const isFilteredEmpty = columnTasks.length > 0 && visibleColumnTasks.length === 0

              return (
                <section
                  key={column.id}
                  className={`kanban-column kanban-column--${column.accent}${dragOverStatus === column.id ? ' kanban-column--drop-target' : ''}`}
                  aria-label={`${column.title}任务列`}
                  onDragOver={(event) => handleColumnDragOver(event, column.id)}
                  onDragLeave={() => setDragOverStatus((currentStatus) => currentStatus === column.id ? null : currentStatus)}
                  onDrop={(event) => handleColumnDrop(event, column.id)}
                >
                  <div className="kanban-column__header">
                    <div className="kanban-column__heading">
                      <span className="kanban-column__marker" aria-hidden="true" />
                      <h2>{column.title}</h2>
                    </div>
                    <span className="kanban-column__count" aria-label={`${columnTasks.length} 个任务`} aria-live="polite">
                      {columnTasks.length}
                    </span>
                  </div>

                  <div className="kanban-column__content">
                    {visibleColumnTasks.map((task) => (
                      <KanbanTaskCard
                        key={task.id}
                        task={task}
                        isEditing={editingTaskId === task.id}
                        isDragging={draggedTaskId === task.id}
                        draftTitle={draftTitle}
                        onTitleChange={setDraftTitle}
                        onBeginEditing={handleBeginEditing}
                        onSaveEditing={handleSaveEditing}
                        onCancelEditing={handleCancelEditing}
                        onDragStart={handleDragStart}
                        onDragEnd={handleDragEnd}
                      />
                    ))}

                    {visibleColumnTasks.length === 0 && (
                      <div className="kanban-empty-state" role="status">
                        <span className="kanban-empty-state__symbol" aria-hidden="true">—</span>
                        <span>{isFilteredEmpty ? '没有符合筛选条件的任务' : '暂无任务'}</span>
                      </div>
                    )}
                  </div>
                </section>
              )
            })}
          </div>
        </div>
      </div>
    </main>
  )
}

export default KanbanBoard
