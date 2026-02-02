import { useState } from 'react'
import { useParams } from 'react-router'
import { SimpleSortableTaskList } from '@/views/projects/SimpleSortableTaskList'
import { TaskDetail } from '@/views/projects/TaskDetail'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { useProjects } from '@/hooks/useProjects'
import { useTasks } from '@/hooks/useTasks'
import { useAuth } from '@/contexts/AuthContext'
import { FolderOpen } from 'lucide-react'

export function ProjectsPage() {
  const { projectId } = useParams<{ projectId?: string }>()
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [isTaskDetailOpen, setIsTaskDetailOpen] = useState(false)
  const { currentCustomerId } = useAuth()

  const { data: projects = [] } = useProjects(currentCustomerId ?? undefined)
  const { data: tasks = [], isLoading } = useTasks(projectId)

  const currentProject = projectId
    ? projects.find(p => p.id === projectId)
    : null

  const selectedTask = selectedTaskId
    ? tasks.find(t => t.id === selectedTaskId)
    : null

  const handleTaskClick = (taskId: string) => {
    setSelectedTaskId(taskId)
    setIsTaskDetailOpen(true)
  }

  const handleTaskDetailClose = () => {
    setIsTaskDetailOpen(false)
    setTimeout(() => setSelectedTaskId(null), 300)
  }

  // Show empty state if no project selected
  if (!projectId || !currentProject) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center h-full bg-background text-muted-foreground">
        <FolderOpen className="w-16 h-16 mb-4 opacity-50" />
        <h2 className="text-xl font-medium mb-2">Select a project</h2>
        <p className="text-sm">Choose a project from the sidebar to view its tasks</p>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-background">
      <div className="bg-card border-b border-border">
        <div className="px-8 py-6">
          <h1 className="text-2xl font-semibold text-gray-900">{currentProject.name}</h1>
          <p className="text-sm text-gray-600 mt-1">Manage tasks in {currentProject.name}</p>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-auto">
          <SimpleSortableTaskList
            tasks={tasks}
            isLoading={isLoading}
            onTaskClick={handleTaskClick}
            selectedTaskId={selectedTaskId}
            projectId={projectId}
          />
        </div>
      </div>

      <Sheet open={isTaskDetailOpen} onOpenChange={handleTaskDetailClose}>
        <SheetContent className="w-[600px] sm:max-w-[600px] p-0" aria-describedby={undefined} hideDefaultCloseButton>
          <SheetTitle className="sr-only">Task Details</SheetTitle>
          {selectedTask && (
            <TaskDetail
              task={selectedTask}
              allTasks={tasks}
              onClose={handleTaskDetailClose}
              onSubtaskClick={handleTaskClick}
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}