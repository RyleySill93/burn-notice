import { useState, useRef, useEffect } from 'react'
import { Check, ChevronRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { Task } from '@/types/projects'
import { DragHandle } from '@/components/DragHandle'
import { useUpdateTask } from '@/hooks/useTasks'

interface TaskRowDraggableProps {
  task: Task
  onClick: () => void
  isSelected?: boolean
  isOverlay?: boolean
  isFirst?: boolean
  autoFocus?: boolean
  onAutoFocusHandled?: () => void
  onCreateTaskBelow?: () => void
  onNavigateUp?: () => void
  onNavigateDown?: () => void
  onDelete?: () => void
  onDragStart?: (startX: number, startY: number) => void
  isDragging?: boolean
  dropIndicator?: 'before' | 'after' | null
  registerRef?: (el: HTMLDivElement | null) => void
  // Subtask props
  hasSubtasks?: boolean
  subtaskCount?: number
  isSubtask?: boolean
  isExpanded?: boolean
  onToggleExpand?: () => void
  // Layout props
  compact?: boolean
}

export function TaskRowDraggable({
  task,
  onClick,
  isSelected,
  isOverlay,
  isFirst,
  autoFocus,
  onAutoFocusHandled,
  onCreateTaskBelow,
  onNavigateUp,
  onNavigateDown,
  onDelete,
  onDragStart,
  isDragging,
  dropIndicator,
  registerRef,
  // Subtask props
  hasSubtasks,
  subtaskCount,
  isSubtask,
  isExpanded,
  onToggleExpand,
  // Layout props
  compact
}: TaskRowDraggableProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isFocused, setIsFocused] = useState(false)
  const [title, setTitle] = useState(task.title)
  const inputRef = useRef<HTMLInputElement>(null)
  const rowRef = useRef<HTMLDivElement>(null)

  const updateTask = useUpdateTask()

  useEffect(() => {
    setTitle(task.title)
  }, [task.title])

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isEditing])

  useEffect(() => {
    if (autoFocus && !isEditing) {
      setIsEditing(true)
      setIsFocused(true)
      onAutoFocusHandled?.()
    }
  }, [autoFocus, isEditing, onAutoFocusHandled])

  // Register ref with parent
  useEffect(() => {
    registerRef?.(rowRef.current)
    return () => registerRef?.(null)
  }, [registerRef])

  const handleToggleComplete = (e: React.MouseEvent) => {
    e.stopPropagation()
    updateTask.mutate({
      taskId: task.id,
      data: {
        completedAt: task.completedAt ? null : new Date().toISOString()
      }
    })
  }

  const handleTitleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsEditing(true)
  }

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTitle(e.target.value)
  }

  const handleTitleBlur = () => {
    if (title !== task.title) {
      updateTask.mutate({
        taskId: task.id,
        data: { title: title.trim() }
      })
    }
    setIsEditing(false)
    setIsFocused(false)
  }

  const handleTitleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (title !== task.title && title.trim()) {
        updateTask.mutate({
          taskId: task.id,
          data: { title: title.trim() }
        })
      }
      setIsEditing(false)
      setIsFocused(false)
      onCreateTaskBelow?.()
    } else if (e.key === 'Escape') {
      setTitle(task.title)
      setIsEditing(false)
      setIsFocused(false)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (title !== task.title) {
        updateTask.mutate({
          taskId: task.id,
          data: { title: title.trim() }
        })
      }
      setIsEditing(false)
      setIsFocused(false)
      onNavigateUp?.()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (title !== task.title) {
        updateTask.mutate({
          taskId: task.id,
          data: { title: title.trim() }
        })
      }
      setIsEditing(false)
      setIsFocused(false)
      onNavigateDown?.()
    } else if (e.key === 'Backspace' && title === '') {
      e.preventDefault()
      onNavigateUp?.()
      onDelete?.()
    }
  }

  const handleRowClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    if (!target.closest('input') && !target.closest('button') && !target.closest('[data-drag-handle]')) {
      onClick()
    }
  }

  const handleDragHandleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    onDragStart?.(e.clientX, e.clientY)
  }

  return (
    <div
      ref={rowRef}
      className={cn(
        "group flex items-center cursor-pointer transition-colors relative",
        isOverlay ? "gap-1 px-2 py-1.5 shadow-xl bg-card border-2 border-primary rounded-md" : [
          "px-2 py-1.5",
          compact ? "gap-1" : "gap-2",
          "border-y",
          isFocused
            ? "border-primary/60"
            : isFirst
              ? "border-border"
              : "border-t-transparent border-b-border",
          isSelected && "bg-accent",
          task.completedAt && "opacity-60",
          isDragging && "opacity-30 bg-accent/50"
        ]
      )}
      onClick={handleRowClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Drop indicator - before */}
      {dropIndicator === 'before' && (
        <div className="absolute -top-[1.5px] left-0 right-0 h-[3px] bg-primary z-20 rounded-full" />
      )}

      {/* Drop indicator - after */}
      {dropIndicator === 'after' && (
        <div className="absolute -bottom-[1.5px] left-0 right-0 h-[3px] bg-primary z-20 rounded-full" />
      )}

      {/* Background hover effect */}
      {isHovered && !isEditing && !isFocused && !isDragging && (
        <div className="absolute inset-0 bg-accent pointer-events-none" />
      )}

      {/* Drag Handle - show static for overlay, interactive otherwise */}
      {isOverlay ? (
        <DragHandle isHovered={true} />
      ) : onDragStart ? (
        <div
          data-drag-handle
          onMouseDown={handleDragHandleMouseDown}
          className="cursor-grab active:cursor-grabbing self-stretch"
        >
          <DragHandle isHovered={isHovered} />
        </div>
      ) : null}

      {/* Subtask indent spacer - after drag handle, only in main list (not compact) */}
      {isSubtask && !compact && !isOverlay && <div className="w-5" />}

      {/* Expand/Collapse toggle and Checkbox - hidden in overlay */}
      {!isOverlay && (
        <>
          {/* Expand/Collapse toggle for tasks with subtasks - before checkbox */}
          {hasSubtasks ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onToggleExpand?.()
              }}
              className={cn(
                "flex items-center justify-center w-5 h-5 rounded transition-colors z-10 cursor-pointer",
                "hover:bg-accent border border-transparent hover:border-border"
              )}
            >
              <motion.div
                animate={{ rotate: isExpanded ? 90 : 0 }}
                transition={{ duration: 0.15 }}
              >
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
              </motion.div>
              {subtaskCount !== undefined && subtaskCount > 0 && (
                <span className="sr-only">{subtaskCount} subtasks</span>
              )}
            </button>
          ) : !compact ? (
            <div className="w-5 h-5 flex-shrink-0" />
          ) : null}

          {/* Checkbox with animation */}
          <button
            onClick={handleToggleComplete}
            className={cn(
              "relative flex items-center justify-center w-4 h-4 rounded-full border-[1.5px] transition-all flex-shrink-0 z-10 cursor-pointer",
              task.completedAt
                ? "bg-green-600 border-green-600"
                : "border-muted-foreground/60 hover:border-foreground"
            )}
          >
            <AnimatePresence>
              {task.completedAt && (
                <motion.div
                  initial={{ scale: 0, rotate: -180 }}
                  animate={{ scale: 1, rotate: 0 }}
                  exit={{ scale: 0, rotate: 180 }}
                  transition={{
                    type: "spring",
                    stiffness: 300,
                    damping: 20
                  }}
                >
                  <Check className="w-2.5 h-2.5 text-white" />
                </motion.div>
              )}
            </AnimatePresence>
          </button>
        </>
      )}

      {/* Editable Title */}
      <div className="flex-1 min-w-0 z-10">
        {isEditing ? (
          <input
            ref={inputRef}
            type="text"
            value={title}
            onChange={handleTitleChange}
            onFocus={() => setIsFocused(true)}
            onBlur={() => {
              setIsFocused(false)
              handleTitleBlur()
            }}
            onKeyDown={handleTitleKeyDown}
            onClick={(e) => e.stopPropagation()}
            className="px-1 py-0.5 text-sm outline-none bg-transparent min-w-[100px]"
            style={{ width: `${Math.max(100, title.length * 8)}px` }}
          />
        ) : (
          <div
            onClick={handleTitleClick}
            className={cn(
              "inline-block px-1 py-0.5 text-sm rounded cursor-text relative",
              isHovered && "ring-1 ring-border bg-background",
              task.completedAt && "line-through text-muted-foreground",
              !task.title && "min-w-[100px]"
            )}
          >
            {task.title || "\u00A0"}
          </div>
        )}
      </div>
    </div>
  )
}
