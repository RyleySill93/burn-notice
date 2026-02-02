import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, Plus } from 'lucide-react'
import type { Task, Section } from '@/types/projects'
import { TaskRowDraggable } from '@/views/projects/TaskRowDraggable'
import { SectionContainer } from '@/views/projects/SectionContainer'
import { SectionHeader } from '@/views/projects/SectionHeader'
import { useSections, useCreateSection, useUpdateSection } from '@/hooks/useSections'
import { useUpdateTask, useCreateTask, useDeleteTask } from '@/hooks/useTasks'
import { AddTaskRow } from '@/views/projects/AddTaskRow'
import { AddSubtaskRow } from '@/views/projects/AddSubtaskRow'

interface SimpleSortableTaskListProps {
  tasks: Task[]
  isLoading: boolean
  onTaskClick: (taskId: string) => void
  selectedTaskId?: string | null
  projectId?: string
}

interface TaskDragState {
  taskId: string
  task: Task
  startX: number
  startY: number
  currentX: number
  currentY: number
  dropTargetId: string | null
  dropPosition: 'before' | 'after' | null
  // For dropping into empty sections
  dropTargetSectionId: string | null
}

interface SectionDragState {
  sectionId: string
  section: Section
  startX: number
  startY: number
  currentX: number
  currentY: number
  dropTargetId: string | null
  dropPosition: 'before' | 'after' | null
}

export function SimpleSortableTaskList({
  tasks,
  isLoading,
  onTaskClick,
  selectedTaskId,
  projectId
}: SimpleSortableTaskListProps) {
  const [newSectionId, setNewSectionId] = useState<string | null>(null)
  const [newTaskId, setNewTaskId] = useState<string | null>(null)
  const [taskDragState, setTaskDragState] = useState<TaskDragState | null>(null)
  const [sectionDragState, setSectionDragState] = useState<SectionDragState | null>(null)
  // Local UI state for expanded tasks (tasks with subtasks default to collapsed)
  const [expandedTaskIds, setExpandedTaskIds] = useState<Set<string>>(new Set())
  // Local UI state for collapsed sections (sections default to expanded)
  const [collapsedSectionIds, setCollapsedSectionIds] = useState<Set<string>>(new Set())
  const taskRowRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const sectionHeaderRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const sectionDropZoneRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  const { data: sectionsData = [], isLoading: sectionsLoading } = useSections(projectId)
  const updateTask = useUpdateTask()
  const updateSection = useUpdateSection()
  const createSection = useCreateSection()
  const createTask = useCreateTask()
  const deleteTask = useDeleteTask()

  // Sort sections by displayOrder (memoized to prevent unnecessary re-renders)
  const sections = useMemo(
    () => [...sectionsData].sort((a, b) => a.displayOrder - b.displayOrder),
    [sectionsData]
  )

  const handleClearNewSection = () => {
    setNewSectionId(null)
  }

  const handleCreateTaskBelow = useCallback(async (afterTask: Task) => {
    const newDisplayOrder = (afterTask.displayOrder ?? 0) + 1

    // Get sibling tasks that need to be shifted (same section/parent, displayOrder >= newDisplayOrder)
    const siblingsToShift = tasks.filter(t => {
      // Must be at the same level (same parentTaskId)
      if (t.parentTaskId !== afterTask.parentTaskId) return false
      // If it's a parent task, must be in the same section
      if (!afterTask.parentTaskId && t.sectionId !== afterTask.sectionId) return false
      // Must have displayOrder >= newDisplayOrder
      return t.displayOrder >= newDisplayOrder
    })

    // Shift existing tasks up by 1
    for (const task of siblingsToShift) {
      updateTask.mutate({
        taskId: task.id,
        data: { displayOrder: task.displayOrder + 1 }
      })
    }

    const newTask = await createTask.mutateAsync({
      data: {
        title: '',
        projectId: afterTask.projectId,
        sectionId: afterTask.sectionId,
        parentTaskId: afterTask.parentTaskId, // Preserve parent if creating below a subtask
        completedAt: null,
        displayOrder: newDisplayOrder
      }
    })

    setNewTaskId(newTask.id)
  }, [createTask, tasks, updateTask])

  const handleClearNewTask = useCallback(() => {
    setNewTaskId(null)
  }, [])

  const handleDeleteTask = useCallback((taskId: string) => {
    deleteTask.mutate({ taskId })
  }, [deleteTask])

  // Get all tasks in display order for navigation
  const getAllTasksInOrder = useCallback(() => {
    const unsectioned = tasks
      .filter(t => !t.sectionId)
      .sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0))

    const sectioned = sections
      .filter(section => !collapsedSectionIds.has(section.id))
      .flatMap(section =>
        tasks
          .filter(t => t.sectionId === section.id)
          .sort((a, b) => a.displayOrder - b.displayOrder)
      )

    return [...unsectioned, ...sectioned]
  }, [tasks, sections, collapsedSectionIds])

  const handleNavigateUp = useCallback((currentTaskId: string) => {
    const allTasks = getAllTasksInOrder()
    const currentIndex = allTasks.findIndex(t => t.id === currentTaskId)
    if (currentIndex > 0) {
      setNewTaskId(allTasks[currentIndex - 1].id)
    }
  }, [getAllTasksInOrder])

  const handleNavigateDown = useCallback((currentTaskId: string) => {
    const allTasks = getAllTasksInOrder()
    const currentIndex = allTasks.findIndex(t => t.id === currentTaskId)
    if (currentIndex < allTasks.length - 1) {
      setNewTaskId(allTasks[currentIndex + 1].id)
    }
  }, [getAllTasksInOrder])

  // Task drag handlers
  const handleTaskDragStart = useCallback((taskId: string, task: Task, startX: number, startY: number) => {
    setTaskDragState({
      taskId,
      task,
      startX,
      startY,
      currentX: startX,
      currentY: startY,
      dropTargetId: null,
      dropPosition: null,
      dropTargetSectionId: null
    })
  }, [])

  const handleTaskDragMove = useCallback((currentX: number, currentY: number) => {
    if (!taskDragState) return

    const draggedTask = taskDragState.task
    const isSubtask = !!draggedTask.parentTaskId

    // Find which task we're over
    let dropTargetId: string | null = null
    let dropPosition: 'before' | 'after' | null = null
    let dropTargetSectionId: string | null = null

    for (const task of tasks) {
      if (task.id === taskDragState.taskId) continue

      // If dragging a subtask, allow dropping on:
      // 1. Siblings (same parent) - reorder within subtasks
      // 2. Parent tasks (no parentTaskId) - promote to parent task
      if (isSubtask) {
        const isSibling = task.parentTaskId === draggedTask.parentTaskId
        const isParentTask = !task.parentTaskId
        if (!isSibling && !isParentTask) continue
      }

      // If dragging a parent task, allow dropping on:
      // 1. Other parent tasks - reorder within section
      // 2. Subtasks - demote to become a subtask of that parent
      // (no restrictions needed - allow all targets)

      const el = taskRowRefs.current.get(task.id)
      if (!el) continue

      const rect = el.getBoundingClientRect()
      const midY = rect.top + rect.height / 2

      if (currentY < midY && currentY > rect.top - 20) {
        dropTargetId = task.id
        dropPosition = 'before'
        break
      } else if (currentY >= midY && currentY < rect.bottom + 20) {
        dropTargetId = task.id
        dropPosition = 'after'
      }
    }

    // If not over a task, check if we're over a section drop zone (for empty sections or dropping at end)
    // Allow this for both parent tasks and subtasks (subtasks get promoted)
    if (!dropTargetId) {
      for (const section of sections) {
        const el = sectionDropZoneRefs.current.get(section.id)
        if (!el) continue

        const rect = el.getBoundingClientRect()
        if (currentX >= rect.left && currentX <= rect.right &&
            currentY >= rect.top && currentY <= rect.bottom) {
          dropTargetSectionId = section.id
          break
        }
      }
    }

    setTaskDragState(prev => prev ? {
      ...prev,
      currentX,
      currentY,
      dropTargetId,
      dropPosition,
      dropTargetSectionId
    } : null)
  }, [taskDragState, tasks, sections])

  const handleTaskDragEnd = useCallback(() => {
    if (!taskDragState) {
      setTaskDragState(null)
      return
    }

    const { taskId, task, dropTargetId, dropPosition, dropTargetSectionId } = taskDragState

    // Handle dropping into an empty section or section drop zone
    if (dropTargetSectionId && !dropTargetId) {
      const isSubtask = !!task.parentTaskId
      const targetSectionTasks = tasks
        .filter(t => t.sectionId === dropTargetSectionId && !t.parentTaskId)
        .sort((a, b) => a.displayOrder - b.displayOrder)

      // Calculate the new display order (add at the end of the section)
      const newDisplayOrder = targetSectionTasks.length > 0
        ? Math.max(...targetSectionTasks.map(t => t.displayOrder)) + 1
        : 1

      // Update the dragged task (clear parentTaskId if promoting a subtask)
      updateTask.mutate({
        taskId: task.id,
        data: {
          sectionId: dropTargetSectionId,
          displayOrder: newDisplayOrder,
          ...(isSubtask && { parentTaskId: null })
        }
      })

      // If subtask was promoted, reorder remaining subtasks
      if (isSubtask && task.parentTaskId) {
        const remainingSubtasks = tasks
          .filter(t => t.parentTaskId === task.parentTaskId && t.id !== taskId)
          .sort((a, b) => a.displayOrder - b.displayOrder)

        remainingSubtasks.forEach((t, index) => {
          const newOrder = index + 1
          if (t.displayOrder !== newOrder) {
            updateTask.mutate({ taskId: t.id, data: { displayOrder: newOrder } })
          }
        })
      }

      // If task was moved from another section, reorder that section
      if (!isSubtask && task.sectionId && task.sectionId !== dropTargetSectionId) {
        const sourceSectionTasks = tasks
          .filter(t => t.sectionId === task.sectionId && t.id !== taskId && !t.parentTaskId)
          .sort((a, b) => a.displayOrder - b.displayOrder)

        sourceSectionTasks.forEach((t, index) => {
          const newOrder = index + 1
          if (t.displayOrder !== newOrder) {
            updateTask.mutate({ taskId: t.id, data: { displayOrder: newOrder } })
          }
        })
      }

      setTaskDragState(null)
      return
    }

    // Original logic for dropping onto a task
    if (!dropTargetId || !dropPosition) {
      setTaskDragState(null)
      return
    }

    const targetTask = tasks.find(t => t.id === dropTargetId)

    if (!targetTask) {
      setTaskDragState(null)
      return
    }

    const isSubtask = !!task.parentTaskId
    const isTargetParentTask = !targetTask.parentTaskId

    // Handle subtask being promoted to parent task level
    if (isSubtask && isTargetParentTask) {
      const targetSectionId = targetTask.sectionId

      // Get parent tasks in the target section (excluding the dragged task which will be promoted)
      const targetSectionTasks = tasks
        .filter(t => t.sectionId === targetSectionId && !t.parentTaskId && t.id !== taskId)
        .sort((a, b) => a.displayOrder - b.displayOrder)

      // Find where to insert
      let targetIndex = targetSectionTasks.findIndex(t => t.id === dropTargetId)

      if (targetIndex === -1) {
        setTaskDragState(null)
        return
      }

      if (dropPosition === 'after') {
        targetIndex += 1
      }

      // Insert the promoted task
      const newOrder = [...targetSectionTasks]
      newOrder.splice(targetIndex, 0, task)

      // Update display orders for all tasks in target section
      newOrder.forEach((t, index) => {
        const newDisplayOrder = index + 1
        if (t.id === taskId) {
          // Promote the subtask: clear parentTaskId, set sectionId and displayOrder
          updateTask.mutate({
            taskId: t.id,
            data: {
              parentTaskId: null,
              sectionId: targetSectionId,
              displayOrder: newDisplayOrder
            }
          })
        } else if (t.displayOrder !== newDisplayOrder) {
          updateTask.mutate({ taskId: t.id, data: { displayOrder: newDisplayOrder } })
        }
      })

      // Reorder remaining subtasks in the original parent
      const remainingSubtasks = tasks
        .filter(t => t.parentTaskId === task.parentTaskId && t.id !== taskId)
        .sort((a, b) => a.displayOrder - b.displayOrder)

      remainingSubtasks.forEach((t, index) => {
        const newDisplayOrder = index + 1
        if (t.displayOrder !== newDisplayOrder) {
          updateTask.mutate({ taskId: t.id, data: { displayOrder: newDisplayOrder } })
        }
      })

      setTaskDragState(null)
      return
    }

    // Handle subtask reordering within same parent
    if (isSubtask) {
      // Get all subtasks of the same parent (excluding the dragged one)
      const siblingSubtasks = tasks
        .filter(t => t.parentTaskId === task.parentTaskId && t.id !== taskId)
        .sort((a, b) => a.displayOrder - b.displayOrder)

      let targetIndex = siblingSubtasks.findIndex(t => t.id === dropTargetId)

      if (targetIndex === -1) {
        setTaskDragState(null)
        return
      }

      if (dropPosition === 'after') {
        targetIndex += 1
      }

      const newOrder = [...siblingSubtasks]
      newOrder.splice(targetIndex, 0, task)

      newOrder.forEach((t, index) => {
        const newDisplayOrder = index + 1
        if (t.displayOrder !== newDisplayOrder) {
          updateTask.mutate({ taskId: t.id, data: { displayOrder: newDisplayOrder } })
        }
      })

      setTaskDragState(null)
      return
    }

    // Handle parent task being demoted to subtask
    const isTargetSubtask = !!targetTask.parentTaskId
    if (!isSubtask && isTargetSubtask) {
      const newParentTaskId = targetTask.parentTaskId

      // Get all subtasks of the target's parent (excluding the dragged task)
      const siblingSubtasks = tasks
        .filter(t => t.parentTaskId === newParentTaskId && t.id !== taskId)
        .sort((a, b) => a.displayOrder - b.displayOrder)

      // Find where to insert
      let targetIndex = siblingSubtasks.findIndex(t => t.id === dropTargetId)

      if (targetIndex === -1) {
        setTaskDragState(null)
        return
      }

      if (dropPosition === 'after') {
        targetIndex += 1
      }

      // Insert the demoted task
      const newOrder = [...siblingSubtasks]
      newOrder.splice(targetIndex, 0, task)

      // Update display orders for all subtasks
      newOrder.forEach((t, index) => {
        const newDisplayOrder = index + 1
        if (t.id === taskId) {
          // Demote the parent task: set parentTaskId, clear sectionId, set displayOrder
          updateTask.mutate({
            taskId: t.id,
            data: {
              parentTaskId: newParentTaskId,
              sectionId: null,
              displayOrder: newDisplayOrder
            }
          })
        } else if (t.displayOrder !== newDisplayOrder) {
          updateTask.mutate({ taskId: t.id, data: { displayOrder: newDisplayOrder } })
        }
      })

      // Reorder remaining parent tasks in the original section
      const remainingParentTasks = tasks
        .filter(t => t.sectionId === task.sectionId && !t.parentTaskId && t.id !== taskId)
        .sort((a, b) => a.displayOrder - b.displayOrder)

      remainingParentTasks.forEach((t, index) => {
        const newDisplayOrder = index + 1
        if (t.displayOrder !== newDisplayOrder) {
          updateTask.mutate({ taskId: t.id, data: { displayOrder: newDisplayOrder } })
        }
      })

      setTaskDragState(null)
      return
    }

    // Handle parent task reordering (existing logic)
    const targetSectionId = targetTask.sectionId
    const isCrossSection = task.sectionId !== targetSectionId

    // Get parent tasks in the TARGET section (excluding the dragged task)
    const targetSectionTasks = tasks
      .filter(t => t.sectionId === targetSectionId && t.id !== taskId && !t.parentTaskId)
      .sort((a, b) => a.displayOrder - b.displayOrder)

    // Find where to insert in the target section
    let targetIndex = targetSectionTasks.findIndex(t => t.id === dropTargetId)

    if (targetIndex === -1) {
      setTaskDragState(null)
      return
    }

    // Adjust target index based on position
    if (dropPosition === 'after') {
      targetIndex += 1
    }

    // Insert dragged task at new position
    const newOrder = [...targetSectionTasks]
    newOrder.splice(targetIndex, 0, task)

    // Update display orders and sectionId if needed
    newOrder.forEach((t, index) => {
      const newDisplayOrder = index + 1
      const needsUpdate = t.id === taskId
        ? (isCrossSection || t.displayOrder !== newDisplayOrder)
        : t.displayOrder !== newDisplayOrder

      if (needsUpdate) {
        const data: { displayOrder: number; sectionId?: string | null } = { displayOrder: newDisplayOrder }
        if (t.id === taskId && isCrossSection) {
          data.sectionId = targetSectionId
        }
        updateTask.mutate({ taskId: t.id, data })
      }
    })

    // If cross-section, also update the source section's display orders
    if (isCrossSection) {
      const sourceSectionTasks = tasks
        .filter(t => t.sectionId === task.sectionId && t.id !== taskId && !t.parentTaskId)
        .sort((a, b) => a.displayOrder - b.displayOrder)

      sourceSectionTasks.forEach((t, index) => {
        const newDisplayOrder = index + 1
        if (t.displayOrder !== newDisplayOrder) {
          updateTask.mutate({ taskId: t.id, data: { displayOrder: newDisplayOrder } })
        }
      })
    }

    setTaskDragState(null)
  }, [taskDragState, tasks, updateTask])

  // Section drag handlers
  const handleSectionDragStart = useCallback((sectionId: string, section: Section, startX: number, startY: number) => {
    setSectionDragState({
      sectionId,
      section,
      startX,
      startY,
      currentX: startX,
      currentY: startY,
      dropTargetId: null,
      dropPosition: null
    })
  }, [])

  const handleSectionDragMove = useCallback((currentX: number, currentY: number) => {
    if (!sectionDragState) return

    let dropTargetId: string | null = null
    let dropPosition: 'before' | 'after' | null = null

    for (const section of sections) {
      if (section.id === sectionDragState.sectionId) continue

      const el = sectionHeaderRefs.current.get(section.id)
      if (!el) continue

      const rect = el.getBoundingClientRect()
      const midY = rect.top + rect.height / 2

      if (currentY < midY && currentY > rect.top - 20) {
        dropTargetId = section.id
        dropPosition = 'before'
        break
      } else if (currentY >= midY && currentY < rect.bottom + 20) {
        dropTargetId = section.id
        dropPosition = 'after'
      }
    }

    setSectionDragState(prev => prev ? {
      ...prev,
      currentX,
      currentY,
      dropTargetId,
      dropPosition
    } : null)
  }, [sectionDragState, sections])

  const handleSectionDragEnd = useCallback(() => {
    if (!sectionDragState || !sectionDragState.dropTargetId || !sectionDragState.dropPosition) {
      setSectionDragState(null)
      return
    }

    const { sectionId, section, dropTargetId, dropPosition } = sectionDragState
    const targetSection = sections.find(s => s.id === dropTargetId)

    if (!targetSection) {
      setSectionDragState(null)
      return
    }

    // Get all sections except the dragged one, sorted by display order
    const otherSections = sections
      .filter(s => s.id !== sectionId)
      .sort((a, b) => a.displayOrder - b.displayOrder)

    // Find target index
    let targetIndex = otherSections.findIndex(s => s.id === dropTargetId)

    if (targetIndex === -1) {
      setSectionDragState(null)
      return
    }

    // Adjust for drop position
    if (dropPosition === 'after') {
      targetIndex += 1
    }

    // Create new order
    const newOrder = [...otherSections]
    newOrder.splice(targetIndex, 0, section)

    // Update display orders
    newOrder.forEach((s, index) => {
      const newDisplayOrder = index + 1
      if (s.displayOrder !== newDisplayOrder) {
        updateSection.mutate({ sectionId: s.id, data: { displayOrder: newDisplayOrder } })
      }
    })

    setSectionDragState(null)
  }, [sectionDragState, sections, updateSection])

  // Global mouse move/up handlers for task drag
  useEffect(() => {
    if (!taskDragState) return

    const handleMouseMove = (e: MouseEvent) => {
      handleTaskDragMove(e.clientX, e.clientY)
    }

    const handleMouseUp = () => {
      handleTaskDragEnd()
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [taskDragState, handleTaskDragMove, handleTaskDragEnd])

  // Global mouse move/up handlers for section drag
  useEffect(() => {
    if (!sectionDragState) return

    const handleMouseMove = (e: MouseEvent) => {
      handleSectionDragMove(e.clientX, e.clientY)
    }

    const handleMouseUp = () => {
      handleSectionDragEnd()
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [sectionDragState, handleSectionDragMove, handleSectionDragEnd])

  const registerTaskRef = useCallback((taskId: string, el: HTMLDivElement | null) => {
    if (el) {
      taskRowRefs.current.set(taskId, el)
    } else {
      taskRowRefs.current.delete(taskId)
    }
  }, [])

  const registerSectionRef = useCallback((sectionId: string, el: HTMLDivElement | null) => {
    if (el) {
      sectionHeaderRefs.current.set(sectionId, el)
    } else {
      sectionHeaderRefs.current.delete(sectionId)
    }
  }, [])

  const registerSectionDropZoneRef = useCallback((sectionId: string, el: HTMLDivElement | null) => {
    if (el) {
      sectionDropZoneRefs.current.set(sectionId, el)
    } else {
      sectionDropZoneRefs.current.delete(sectionId)
    }
  }, [])

  // Handle toggle expand for tasks with subtasks (local UI state only)
  const handleToggleExpand = useCallback((taskId: string) => {
    setExpandedTaskIds(prev => {
      const next = new Set(prev)
      if (next.has(taskId)) {
        next.delete(taskId)
      } else {
        next.add(taskId)
      }
      return next
    })
  }, [])

  if (isLoading || sectionsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  const handleCreateFirstSection = async () => {
    if (!projectId) return
    const newSection = await createSection.mutateAsync({
      data: {
        name: 'New Section',
        projectId,
        displayOrder: sections.length > 0 ? Math.max(...sections.map(s => s.displayOrder)) + 1 : 1
      }
    })
    setNewSectionId(newSection.id)
  }

  // Separate parent tasks from subtasks
  const parentTasks = tasks.filter(t => !t.parentTaskId)
  const subtasksByParent = tasks.reduce((acc, task) => {
    if (task.parentTaskId) {
      if (!acc[task.parentTaskId]) {
        acc[task.parentTaskId] = []
      }
      acc[task.parentTaskId].push(task)
    }
    return acc
  }, {} as Record<string, Task[]>)

  // Sort subtasks by displayOrder
  Object.keys(subtasksByParent).forEach(parentId => {
    subtasksByParent[parentId].sort((a, b) => a.displayOrder - b.displayOrder)
  })

  // Group tasks by section (only parent tasks)
  const tasksWithoutSection = parentTasks
    .filter(t => !t.sectionId)
    .sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0))

  const tasksBySection = sections.reduce((acc, section) => {
    acc[section.id] = parentTasks
      .filter(t => t.sectionId === section.id)
      .sort((a, b) => a.displayOrder - b.displayOrder)
    return acc
  }, {} as Record<string, Task[]>)

  const renderTaskRow = (task: Task, index: number, isSubtask = false) => {
    const isDragging = taskDragState?.taskId === task.id
    const isDropTarget = taskDragState?.dropTargetId === task.id
    const dropPosition = isDropTarget ? taskDragState?.dropPosition : null
    const subtasks = subtasksByParent[task.id] || []
    const hasSubtasks = subtasks.length > 0
    const isExpanded = expandedTaskIds.has(task.id)

    return (
      <div key={task.id}>
        <TaskRowDraggable
          task={task}
          onClick={() => onTaskClick(task.id)}
          isSelected={selectedTaskId === task.id}
          isFirst={index === 0 && !isSubtask}
          autoFocus={task.id === newTaskId}
          onAutoFocusHandled={handleClearNewTask}
          onCreateTaskBelow={() => handleCreateTaskBelow(task)}
          onNavigateUp={() => handleNavigateUp(task.id)}
          onNavigateDown={() => handleNavigateDown(task.id)}
          onDelete={() => handleDeleteTask(task.id)}
          onDragStart={(startX, startY) => handleTaskDragStart(task.id, task, startX, startY)}
          isDragging={isDragging}
          dropIndicator={dropPosition}
          registerRef={(el) => registerTaskRef(task.id, el)}
          // Subtask props
          hasSubtasks={hasSubtasks}
          subtaskCount={subtasks.length}
          isSubtask={isSubtask}
          isExpanded={isExpanded}
          onToggleExpand={() => handleToggleExpand(task.id)}
        />
        {/* Render subtasks if expanded */}
        {hasSubtasks && isExpanded && (
          <>
            {subtasks.map((subtask, subIndex) => renderTaskRow(subtask, subIndex, true))}
            <AddSubtaskRow parentTaskId={task.id} projectId={projectId} />
          </>
        )}
      </div>
    )
  }

  // Task drag overlay (the floating task that follows cursor)
  const taskDragOverlay = taskDragState && createPortal(
    <div
      className="fixed pointer-events-none z-50 max-w-[400px]"
      style={{
        top: taskDragState.currentY - 8,
        left: taskDragState.currentX - 8,
      }}
    >
      <TaskRowDraggable
        task={taskDragState.task}
        onClick={() => {}}
        isOverlay
      />
    </div>,
    document.body
  )

  // Section drag overlay (the floating section header that follows cursor)
  const sectionDragOverlay = sectionDragState && createPortal(
    <div
      className="fixed pointer-events-none z-50 min-w-[300px]"
      style={{
        top: sectionDragState.currentY - 8,
        left: sectionDragState.currentX - 8,
      }}
    >
      <SectionHeader
        section={sectionDragState.section}
        onToggleExpand={() => {}}
        isOverlay
      />
    </div>,
    document.body
  )

  // If no sections
  if (sections.length === 0) {
    return (
      <div className="bg-card">
        {tasksWithoutSection.length > 0 && (
          <div>
            {tasksWithoutSection.map((task, index) => renderTaskRow(task, index))}
          </div>
        )}

        <div className="border-t border-border">
          <AddTaskRow
            projectId={projectId}
            nextDisplayOrder={tasksWithoutSection.length > 0 ? Math.max(...tasksWithoutSection.map(t => t.displayOrder)) + 1 : 1}
          />
        </div>

        {projectId && (
          <div
            onClick={handleCreateFirstSection}
            className="px-2 py-3 cursor-pointer hover:bg-accent/50 transition-colors flex items-center gap-2 text-muted-foreground hover:text-foreground"
          >
            <div className="w-6" />
            <div className="flex items-center justify-center w-6 h-6">
              <Plus className="w-4 h-4" />
            </div>
            <span className="text-base font-semibold">Add section</span>
          </div>
        )}

        {taskDragOverlay}
      </div>
    )
  }

  return (
    <div className="bg-card">
      {/* Tasks without sections */}
      {tasksWithoutSection.length > 0 && (
        <div className="mb-4">
          <div>
            {tasksWithoutSection.map((task, index) => renderTaskRow(task, index))}
            <AddTaskRow
              projectId={projectId}
              nextDisplayOrder={tasksWithoutSection.length > 0 ? Math.max(...tasksWithoutSection.map(t => t.displayOrder)) + 1 : 1}
            />
          </div>
        </div>
      )}

      {/* Sections with their tasks */}
      {sections.map((section) => (
        <SectionContainer
          key={section.id}
          section={section}
          tasks={tasksBySection[section.id] || []}
          onTaskClick={onTaskClick}
          selectedTaskId={selectedTaskId}
          projectId={projectId}
          autoFocus={section.id === newSectionId}
          onAutoFocusHandled={handleClearNewSection}
          onSectionCreated={setNewSectionId}
          newTaskId={newTaskId}
          onClearNewTask={handleClearNewTask}
          onCreateTaskBelow={handleCreateTaskBelow}
          onNavigateUp={handleNavigateUp}
          onNavigateDown={handleNavigateDown}
          onDeleteTask={handleDeleteTask}
          onDragStart={handleTaskDragStart}
          dragState={taskDragState}
          registerTaskRef={registerTaskRef}
          onSectionDragStart={handleSectionDragStart}
          sectionDragState={sectionDragState}
          registerSectionRef={registerSectionRef}
          registerSectionDropZoneRef={registerSectionDropZoneRef}
          isSectionDropTarget={taskDragState?.dropTargetSectionId === section.id}
          subtasksByParent={subtasksByParent}
          expandedTaskIds={expandedTaskIds}
          onToggleTaskExpand={handleToggleExpand}
          isSectionExpanded={!collapsedSectionIds.has(section.id)}
          onToggleSectionExpand={() => {
            setCollapsedSectionIds(prev => {
              const next = new Set(prev)
              if (next.has(section.id)) {
                next.delete(section.id)
              } else {
                next.add(section.id)
              }
              return next
            })
          }}
        />
      ))}

      {/* Add new section button */}
      {projectId && (
        <div
          onClick={handleCreateFirstSection}
          className="px-2 py-3 cursor-pointer hover:bg-accent/50 transition-colors flex items-center gap-2 text-muted-foreground hover:text-foreground"
        >
          <div className="w-6" />
          <div className="flex items-center justify-center w-6 h-6">
            <Plus className="w-4 h-4" />
          </div>
          <span className="text-base font-semibold">Add section</span>
        </div>
      )}

      {taskDragOverlay}
      {sectionDragOverlay}
    </div>
  )
}
