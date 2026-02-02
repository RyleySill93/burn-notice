import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { PanelRightClose, Check, ChevronRight } from 'lucide-react'
import type { Task } from '@/types/projects'
import { SuperButton } from '@/components/SuperButton'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { useUpdateTask, useDeleteTask } from '@/hooks/useTasks'
import { cn } from '@/lib/utils'
import { TaskRowDraggable } from '@/views/projects/TaskRowDraggable'
import { AddSubtaskRow } from '@/views/projects/AddSubtaskRow'

interface SubtaskDragState {
  taskId: string
  task: Task
  startX: number
  startY: number
  currentX: number
  currentY: number
  dropTargetId: string | null
  dropPosition: 'before' | 'after' | null
}

interface TaskDetailProps {
  task: Task
  allTasks: Task[]
  onClose: () => void
  onSubtaskClick?: (taskId: string) => void
}

export function TaskDetail({ task, allTasks, onClose, onSubtaskClick }: TaskDetailProps) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description || '')
  const [subtaskDragState, setSubtaskDragState] = useState<SubtaskDragState | null>(null)

  const subtaskRowRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  const updateTask = useUpdateTask()
  const deleteTask = useDeleteTask()

  // Get subtasks for this task
  const subtasks = useMemo(() => {
    return allTasks
      .filter(t => t.parentTaskId === task.id)
      .sort((a, b) => a.displayOrder - b.displayOrder)
  }, [allTasks, task.id])

  // Don't show subtasks section if this is a subtask itself
  const isSubtask = !!task.parentTaskId

  // Get parent task if this is a subtask
  const parentTask = useMemo(() => {
    if (!task.parentTaskId) return null
    return allTasks.find(t => t.id === task.parentTaskId) || null
  }, [allTasks, task.parentTaskId])

  // Register subtask row refs for hit detection
  const registerSubtaskRef = useCallback((taskId: string, el: HTMLDivElement | null) => {
    if (el) {
      subtaskRowRefs.current.set(taskId, el)
    } else {
      subtaskRowRefs.current.delete(taskId)
    }
  }, [])

  // Subtask drag handlers
  const handleSubtaskDragStart = useCallback((taskId: string, subtask: Task, startX: number, startY: number) => {
    setSubtaskDragState({
      taskId,
      task: subtask,
      startX,
      startY,
      currentX: startX,
      currentY: startY,
      dropTargetId: null,
      dropPosition: null
    })
  }, [])

  const handleSubtaskDragMove = useCallback((clientX: number, clientY: number) => {
    if (!subtaskDragState) return

    let dropTargetId: string | null = null
    let dropPosition: 'before' | 'after' | null = null

    // Check each subtask row for hit detection
    for (const subtask of subtasks) {
      if (subtask.id === subtaskDragState.taskId) continue

      const el = subtaskRowRefs.current.get(subtask.id)
      if (!el) continue

      const rect = el.getBoundingClientRect()
      if (clientX >= rect.left && clientX <= rect.right &&
          clientY >= rect.top && clientY <= rect.bottom) {
        dropTargetId = subtask.id
        const midY = rect.top + rect.height / 2
        dropPosition = clientY < midY ? 'before' : 'after'
        break
      }
    }

    setSubtaskDragState(prev => prev ? {
      ...prev,
      currentX: clientX,
      currentY: clientY,
      dropTargetId,
      dropPosition
    } : null)
  }, [subtaskDragState, subtasks])

  const handleSubtaskDragEnd = useCallback(() => {
    if (!subtaskDragState || !subtaskDragState.dropTargetId || !subtaskDragState.dropPosition) {
      setSubtaskDragState(null)
      return
    }

    const { taskId, task: draggedTask, dropTargetId, dropPosition } = subtaskDragState

    // Get all subtasks excluding the dragged one
    const siblingSubtasks = subtasks.filter(t => t.id !== taskId)

    let targetIndex = siblingSubtasks.findIndex(t => t.id === dropTargetId)

    if (targetIndex === -1) {
      setSubtaskDragState(null)
      return
    }

    if (dropPosition === 'after') {
      targetIndex += 1
    }

    // Build new order array
    const newOrder = [...siblingSubtasks]
    newOrder.splice(targetIndex, 0, draggedTask)

    // Update all tasks with sequential integer display orders
    newOrder.forEach((t, index) => {
      const newDisplayOrder = index + 1
      if (t.displayOrder !== newDisplayOrder) {
        updateTask.mutate({ taskId: t.id, data: { displayOrder: newDisplayOrder } })
      }
    })

    setSubtaskDragState(null)
  }, [subtaskDragState, subtasks, updateTask])

  // Mouse event handlers for subtask dragging
  useEffect(() => {
    if (!subtaskDragState) return

    const handleMouseMove = (e: MouseEvent) => {
      handleSubtaskDragMove(e.clientX, e.clientY)
    }

    const handleMouseUp = () => {
      handleSubtaskDragEnd()
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [subtaskDragState, handleSubtaskDragMove, handleSubtaskDragEnd])

  useEffect(() => {
    setTitle(task.title)
    setDescription(task.description || '')
  }, [task])

  const handleTitleBlur = () => {
    if (title !== task.title) {
      updateTask.mutate({
        taskId: task.id,
        data: { title }
      })
    }
  }

  const handleDescriptionBlur = () => {
    if (description !== (task.description || '')) {
      updateTask.mutate({
        taskId: task.id,
        data: { description: description || undefined }
      })
    }
  }

  const handleDelete = async () => {
    await deleteTask.mutateAsync({ taskId: task.id })
    onClose()
  }

  const handleToggleComplete = () => {
    updateTask.mutate({
      taskId: task.id,
      data: {
        completedAt: task.completedAt ? null : new Date().toISOString()
      }
    })
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-3 border-b">
        <SuperButton
          variant="outline"
          size="sm"
          leftIcon={Check}
          onClick={handleToggleComplete}
          className={cn(
            "h-7 text-xs",
            task.completedAt
              ? "bg-green-50 border-green-200 text-green-700 hover:bg-green-100"
              : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
          )}
        >
          {task.completedAt ? "Completed" : "Mark complete"}
        </SuperButton>
        <SuperButton
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="h-8 w-8 p-0"
        >
          <PanelRightClose className="h-5 w-5" />
        </SuperButton>
      </div>

      <div className="flex-1 overflow-auto px-6 pb-6 pt-2">
        <div className="space-y-6">
          <div>
            {parentTask && (
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  onSubtaskClick?.(parentTask.id)
                }}
                className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline transition-colors mb-1"
              >
                {parentTask.title}
                <ChevronRight className="h-4 w-4" />
              </a>
            )}
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={handleTitleBlur}
              className="!text-2xl font-semibold border-none px-1 shadow-none h-auto py-2 rounded hover:ring-1 hover:ring-border focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Task title"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-muted-foreground">
              Description
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onBlur={handleDescriptionBlur}
              placeholder="What is this task about?"
              className="min-h-[120px] resize-none"
            />
          </div>

          {/* Subtasks section - only show for parent tasks */}
          {!isSubtask && (
            <div className="pt-4">
              <label className="text-sm font-medium text-muted-foreground">
                Subtasks
              </label>

              <div className="mt-2 -mx-2">
                {subtasks.map((subtask, index) => {
                  const isDragging = subtaskDragState?.taskId === subtask.id
                  const isDropTarget = subtaskDragState?.dropTargetId === subtask.id
                  const dropPosition = isDropTarget ? subtaskDragState?.dropPosition : null

                  return (
                    <TaskRowDraggable
                      key={subtask.id}
                      task={subtask}
                      onClick={() => onSubtaskClick?.(subtask.id)}
                      isFirst={index === 0}
                      onDelete={() => deleteTask.mutate({ taskId: subtask.id })}
                      onDragStart={(startX, startY) => handleSubtaskDragStart(subtask.id, subtask, startX, startY)}
                      isDragging={isDragging}
                      dropIndicator={dropPosition}
                      registerRef={(el) => registerSubtaskRef(subtask.id, el)}
                      compact
                    />
                  )
                })}
                <AddSubtaskRow parentTaskId={task.id} projectId={task.projectId} compact />
              </div>
            </div>
          )}

          {task.createdAt && (
            <div className="pt-4 text-xs text-gray-500">
              Created {new Date(task.createdAt).toLocaleDateString()}
            </div>
          )}
        </div>
      </div>

      <div className="px-6 py-4 border-t bg-muted flex items-center">
        <SuperButton
          variant="destructive"
          size="sm"
          onClick={handleDelete}
        >
          Delete Task
        </SuperButton>

      </div>

      {/* Drag overlay for subtasks */}
      {subtaskDragState && createPortal(
        <div
          className="fixed pointer-events-none z-50"
          style={{
            left: subtaskDragState.currentX - 150,
            top: subtaskDragState.currentY - 16,
            width: '300px'
          }}
        >
          <TaskRowDraggable
            task={subtaskDragState.task}
            onClick={() => {}}
            isOverlay
            isSubtask
          />
        </div>,
        document.body
      )}
    </div>
  )
}