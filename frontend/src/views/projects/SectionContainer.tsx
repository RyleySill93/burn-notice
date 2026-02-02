import { useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { Section, Task } from '@/types/projects'
import { SectionHeader } from '@/views/projects/SectionHeader'
import { TaskRowDraggable } from '@/views/projects/TaskRowDraggable'
import { AddTaskRow } from '@/views/projects/AddTaskRow'
import { AddSubtaskRow } from '@/views/projects/AddSubtaskRow'
import { useCreateSection } from '@/hooks/useSections'
import { cn } from '@/lib/utils'

interface TaskDragState {
  taskId: string
  task: Task
  startX: number
  startY: number
  currentX: number
  currentY: number
  dropTargetId: string | null
  dropPosition: 'before' | 'after' | null
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

interface SectionContainerProps {
  section: Section
  tasks: Task[]
  onTaskClick: (taskId: string) => void
  selectedTaskId?: string | null
  projectId?: string
  autoFocus?: boolean
  onAutoFocusHandled?: () => void
  onSectionCreated?: (sectionId: string) => void
  newTaskId?: string | null
  onClearNewTask?: () => void
  onCreateTaskBelow?: (afterTask: Task) => void
  onNavigateUp?: (taskId: string) => void
  onNavigateDown?: (taskId: string) => void
  onDeleteTask?: (taskId: string) => void
  onDragStart?: (taskId: string, task: Task, startX: number, startY: number) => void
  dragState?: TaskDragState | null
  registerTaskRef?: (taskId: string, el: HTMLDivElement | null) => void
  // Section drag props
  onSectionDragStart?: (sectionId: string, section: Section, startX: number, startY: number) => void
  sectionDragState?: SectionDragState | null
  registerSectionRef?: (sectionId: string, el: HTMLDivElement | null) => void
  // Section drop zone props
  registerSectionDropZoneRef?: (sectionId: string, el: HTMLDivElement | null) => void
  isSectionDropTarget?: boolean
  // Subtask props
  subtasksByParent?: Record<string, Task[]>
  expandedTaskIds?: Set<string>
  onToggleTaskExpand?: (taskId: string) => void
  // Section expand props
  isSectionExpanded?: boolean
  onToggleSectionExpand?: () => void
}

export function SectionContainer({
  section,
  tasks,
  onTaskClick,
  selectedTaskId,
  projectId,
  autoFocus,
  onAutoFocusHandled,
  onSectionCreated,
  newTaskId,
  onClearNewTask,
  onCreateTaskBelow,
  onNavigateUp,
  onNavigateDown,
  onDeleteTask,
  onDragStart,
  dragState,
  registerTaskRef,
  onSectionDragStart,
  sectionDragState,
  registerSectionRef,
  registerSectionDropZoneRef,
  isSectionDropTarget: isTaskDropTargetSection,
  subtasksByParent = {},
  expandedTaskIds = new Set(),
  onToggleTaskExpand,
  isSectionExpanded = true,
  onToggleSectionExpand
}: SectionContainerProps) {
  const createSection = useCreateSection()

  const isSectionDragging = sectionDragState?.sectionId === section.id
  const isSectionDropTarget = sectionDragState?.dropTargetId === section.id
  const sectionDropPosition = isSectionDropTarget ? sectionDragState?.dropPosition : null

  // Callback ref for registering the container element
  const containerRefCallback = useCallback((el: HTMLDivElement | null) => {
    registerSectionRef?.(section.id, el)
  }, [section.id, registerSectionRef])

  // Callback ref for registering the drop zone element
  const dropZoneRefCallback = useCallback((el: HTMLDivElement | null) => {
    registerSectionDropZoneRef?.(section.id, el)
  }, [section.id, registerSectionDropZoneRef])

  const handleAddSection = async () => {
    const newSection = await createSection.mutateAsync({
      data: {
        name: 'New Section',
        projectId: section.projectId,
        displayOrder: section.displayOrder + 1
      }
    })
    onSectionCreated?.(newSection.id)
  }

  return (
    <div
      ref={containerRefCallback}
      className={cn(
        "mb-4 relative",
        isSectionDragging && "opacity-30"
      )}
    >
      {/* Section drop indicator - before */}
      {sectionDropPosition === 'before' && (
        <div className="absolute -top-[2px] left-0 right-0 h-[4px] bg-primary z-20 rounded-full" />
      )}

      {/* Section drop indicator - after */}
      {sectionDropPosition === 'after' && (
        <div className="absolute -bottom-[2px] left-0 right-0 h-[4px] bg-primary z-20 rounded-full" />
      )}

      <SectionHeader
        section={section}
        isExpanded={isSectionExpanded}
        onToggleExpand={onToggleSectionExpand}
        onAddSection={handleAddSection}
        autoFocus={autoFocus}
        onAutoFocusHandled={onAutoFocusHandled}
        onDragStart={(startX, startY) => onSectionDragStart?.(section.id, section, startX, startY)}
        isDragging={false}
      />

      <AnimatePresence>
        {isSectionExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            {/* Drop zone for the entire section task area */}
            <div
              ref={dropZoneRefCallback}
              className={cn(
                "relative transition-colors",
                isTaskDropTargetSection && "bg-primary/10"
              )}
            >
              {/* Drop indicator line at top of section when targeting empty section */}
              {isTaskDropTargetSection && tasks.length === 0 && (
                <div className="absolute top-0 left-0 right-0 h-[3px] bg-primary z-20 rounded-full" />
              )}
              {tasks.map((task, index) => {
                const isDragging = dragState?.taskId === task.id
                const isDropTarget = dragState?.dropTargetId === task.id
                const dropPosition = isDropTarget ? dragState?.dropPosition : null
                const subtasks = subtasksByParent[task.id] || []
                const hasSubtasks = subtasks.length > 0
                const isExpanded = expandedTaskIds.has(task.id)

                return (
                  <div key={task.id}>
                    <TaskRowDraggable
                      task={task}
                      onClick={() => onTaskClick(task.id)}
                      isSelected={selectedTaskId === task.id}
                      isFirst={index === 0}
                      autoFocus={task.id === newTaskId}
                      onAutoFocusHandled={onClearNewTask}
                      onCreateTaskBelow={() => onCreateTaskBelow?.(task)}
                      onNavigateUp={() => onNavigateUp?.(task.id)}
                      onNavigateDown={() => onNavigateDown?.(task.id)}
                      onDelete={() => onDeleteTask?.(task.id)}
                      onDragStart={(startX, startY) => onDragStart?.(task.id, task, startX, startY)}
                      isDragging={isDragging}
                      dropIndicator={dropPosition}
                      registerRef={(el) => registerTaskRef?.(task.id, el)}
                      hasSubtasks={hasSubtasks}
                      subtaskCount={subtasks.length}
                      isExpanded={isExpanded}
                      onToggleExpand={() => onToggleTaskExpand?.(task.id)}
                    />
                    {/* Render subtasks if expanded */}
                    {hasSubtasks && isExpanded && (
                      <>
                        {subtasks.map((subtask) => {
                          const isSubtaskDragging = dragState?.taskId === subtask.id
                          const isSubtaskDropTarget = dragState?.dropTargetId === subtask.id
                          const subtaskDropPosition = isSubtaskDropTarget ? dragState?.dropPosition : null

                          return (
                            <TaskRowDraggable
                              key={subtask.id}
                              task={subtask}
                              onClick={() => onTaskClick(subtask.id)}
                              isSelected={selectedTaskId === subtask.id}
                              autoFocus={subtask.id === newTaskId}
                              onAutoFocusHandled={onClearNewTask}
                              onCreateTaskBelow={() => onCreateTaskBelow?.(subtask)}
                              onNavigateUp={() => onNavigateUp?.(subtask.id)}
                              onNavigateDown={() => onNavigateDown?.(subtask.id)}
                              onDelete={() => onDeleteTask?.(subtask.id)}
                              onDragStart={(startX, startY) => onDragStart?.(subtask.id, subtask, startX, startY)}
                              isDragging={isSubtaskDragging}
                              dropIndicator={subtaskDropPosition}
                              registerRef={(el) => registerTaskRef?.(subtask.id, el)}
                              isSubtask
                            />
                          )
                        })}
                        <AddSubtaskRow parentTaskId={task.id} projectId={projectId} />
                      </>
                    )}
                  </div>
                )
              })}
              <AddTaskRow
                projectId={projectId}
                sectionId={section.id}
                nextDisplayOrder={tasks.length > 0 ? Math.max(...tasks.map(t => t.displayOrder)) + 1 : 1}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
