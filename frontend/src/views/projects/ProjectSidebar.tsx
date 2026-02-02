import { useState } from 'react'
import { NavLink } from 'react-router'
import { Plus, Home, ChevronDown, Circle, MoreHorizontal, Users } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { Project } from '@/types/projects'
import { ProjectDialog } from '@/views/projects/ProjectDialog'
import { useCreateProject, useUpdateProject, useDeleteProject } from '@/hooks/useProjects'
import { useAuth } from '@/contexts/AuthContext'

interface ProjectSidebarProps {
  projects: Project[]
  selectedProjectId?: string
}

export function ProjectSidebar({ projects, selectedProjectId }: ProjectSidebarProps) {
  const [isProjectsExpanded, setIsProjectsExpanded] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingProject, setEditingProject] = useState<Project | null>(null)

  const { currentCustomerId } = useAuth()

  const createProject = useCreateProject()
  const updateProject = useUpdateProject()
  const deleteProject = useDeleteProject()

  const handleCreateProject = async (data: { name: string; color: string }) => {
    if (!currentCustomerId) return
    await createProject.mutateAsync({ data: { ...data, customerId: currentCustomerId } })
  }

  const handleUpdateProject = async (data: { name: string; color: string }) => {
    if (!editingProject) return
    await updateProject.mutateAsync({
      projectId: editingProject.id,
      data
    })
  }

  const handleDeleteProject = async () => {
    if (!editingProject) return
    await deleteProject.mutateAsync({ projectId: editingProject.id })
  }

  const openCreateDialog = () => {
    setEditingProject(null)
    setDialogOpen(true)
  }

  const openEditDialog = (project: Project, e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setEditingProject(project)
    setDialogOpen(true)
  }

  return (
    <>
      <div className="w-60 bg-gray-800 border-r border-gray-700 flex flex-col h-full">
        <div className="p-4">
          <NavLink
            to="/projects"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                isActive && !selectedProjectId
                  ? "bg-gray-700 text-white"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              )
            }
          >
            <Home className="h-4 w-4" />
            Home
          </NavLink>
          <NavLink
            to="/team"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-gray-700 text-white"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              )
            }
          >
            <Users className="h-4 w-4" />
            Manage team
          </NavLink>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="px-4 pb-2 flex items-center justify-between group">
            <button
              onClick={() => setIsProjectsExpanded(!isProjectsExpanded)}
              className="flex items-center gap-1 text-xs font-semibold text-gray-400 hover:text-gray-200 uppercase tracking-wide"
            >
              <ChevronDown
                className={cn(
                  "h-3 w-3 transition-transform",
                  isProjectsExpanded ? "" : "-rotate-90"
                )}
              />
              <span>Projects</span>
            </button>
            <button
              onClick={openCreateDialog}
              className="p-1 rounded opacity-0 group-hover:opacity-100 text-gray-400 hover:text-white hover:bg-gray-700 transition-all"
              title="Create project"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>

          {isProjectsExpanded && (
            <ScrollArea className="flex-1 px-2">
              <div className="space-y-0.5 pb-2">
                {projects.map((project) => (
                  <NavLink
                    key={project.id}
                    to={`/projects/${project.id}`}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors group/item",
                        isActive || selectedProjectId === project.id
                          ? "bg-gray-700 text-white"
                          : "text-gray-300 hover:bg-gray-700 hover:text-white"
                      )
                    }
                  >
                    <Circle
                      className="h-2 w-2 flex-shrink-0"
                      style={{ color: project.color || '#6366f1', fill: project.color || '#6366f1' }}
                    />
                    <span className="truncate flex-1">{project.name}</span>
                    <button
                      onClick={(e) => openEditDialog(project, e)}
                      className="p-0.5 rounded opacity-0 group-hover/item:opacity-100 text-gray-400 hover:text-white hover:bg-gray-600 transition-all"
                      title="Edit project"
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </button>
                  </NavLink>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>
      </div>

      <ProjectDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        project={editingProject}
        onSave={editingProject ? handleUpdateProject : handleCreateProject}
        onDelete={editingProject ? handleDeleteProject : undefined}
      />
    </>
  )
}