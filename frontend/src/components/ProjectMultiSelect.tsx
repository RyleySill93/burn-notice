import { Circle } from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'
import type { ProjectRead } from '@/generated/models'

interface ProjectMultiSelectProps {
  projects: ProjectRead[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
  label?: string
  emptyMessage?: string
}

export function ProjectMultiSelect({
  projects,
  selectedIds,
  onChange,
  disabled,
  label,
  emptyMessage = 'No projects available',
}: ProjectMultiSelectProps) {
  const handleToggle = (projectId: string) => {
    if (selectedIds.includes(projectId)) {
      onChange(selectedIds.filter((id) => id !== projectId))
    } else {
      onChange([...selectedIds, projectId])
    }
  }

  return (
    <div className="space-y-2">
      {label && <label className="text-sm font-medium">{label}</label>}
      <div className="border rounded-md divide-y max-h-48 overflow-y-auto">
        {projects.length === 0 ? (
          <div className="p-3 text-sm text-muted-foreground text-center">
            {emptyMessage}
          </div>
        ) : (
          projects.map((project) => (
            <label
              key={project.id}
              className={cn(
                'flex items-center gap-3 p-3 cursor-pointer hover:bg-muted/50 transition-colors',
                disabled && 'opacity-50 cursor-not-allowed'
              )}
            >
              <Checkbox
                checked={selectedIds.includes(project.id)}
                onCheckedChange={() => handleToggle(project.id)}
                disabled={disabled}
              />
              <Circle
                className="h-3 w-3 flex-shrink-0"
                style={{
                  color: project.color || '#6366f1',
                  fill: project.color || '#6366f1',
                }}
              />
              <span className="text-sm truncate">{project.name}</span>
            </label>
          ))
        )}
      </div>
    </div>
  )
}
