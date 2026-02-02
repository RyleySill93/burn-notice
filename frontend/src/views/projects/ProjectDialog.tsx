import { useState, useEffect } from 'react'
import { Check } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { SuperButton } from '@/components/SuperButton'
import { SuperField } from '@/components/SuperField'
import { cn } from '@/lib/utils'
import type { Project } from '@/types/projects'

const PROJECT_COLORS = [
  '#ef4444', // red
  '#f97316', // orange
  '#f59e0b', // amber
  '#eab308', // yellow
  '#84cc16', // lime
  '#22c55e', // green
  '#10b981', // emerald
  '#14b8a6', // teal
  '#06b6d4', // cyan
  '#0ea5e9', // sky
  '#3b82f6', // blue
  '#6366f1', // indigo
  '#8b5cf6', // violet
  '#a855f7', // purple
  '#d946ef', // fuchsia
  '#ec4899', // pink
]

interface ProjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  project?: Project | null
  onSave: (data: { name: string; color: string }) => Promise<void>
  onDelete?: () => Promise<void>
}

export function ProjectDialog({
  open,
  onOpenChange,
  project,
  onSave,
  onDelete,
}: ProjectDialogProps) {
  const [name, setName] = useState('')
  const [color, setColor] = useState(PROJECT_COLORS[0])
  const [isDeleting, setIsDeleting] = useState(false)

  const isEditing = !!project

  useEffect(() => {
    if (open) {
      if (project) {
        setName(project.name)
        setColor(project.color || PROJECT_COLORS[0])
      } else {
        setName('')
        setColor(PROJECT_COLORS[Math.floor(Math.random() * PROJECT_COLORS.length)])
      }
      setIsDeleting(false)
    }
  }, [open, project])

  const handleSave = async () => {
    if (!name.trim()) return
    await onSave({ name: name.trim(), color })
    onOpenChange(false)
  }

  const handleDelete = async () => {
    if (!onDelete) return
    setIsDeleting(true)
    await onDelete()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Project' : 'Create Project'}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <SuperField label="Project Name" name="name">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter project name"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && name.trim()) {
                  handleSave()
                }
              }}
            />
          </SuperField>

          <div className="space-y-2">
            <label className="text-sm font-medium">Color</label>
            <div className="grid grid-cols-8 gap-2">
              {PROJECT_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={cn(
                    "w-7 h-7 rounded-full transition-all flex items-center justify-center",
                    color === c && "ring-2 ring-offset-2 ring-offset-background ring-foreground"
                  )}
                  style={{ backgroundColor: c }}
                >
                  {color === c && <Check className="w-3.5 h-3.5 text-white" />}
                </button>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter className="flex-row justify-between sm:justify-between">
          {isEditing && onDelete ? (
            <SuperButton
              variant="ghost"
              onClick={handleDelete}
              className="text-destructive hover:text-destructive hover:bg-destructive/10"
              disabled={isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Delete Project'}
            </SuperButton>
          ) : (
            <div />
          )}
          <div className="flex gap-2">
            <SuperButton variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </SuperButton>
            <SuperButton onClick={handleSave} disabled={!name.trim()}>
              {isEditing ? 'Save' : 'Create'}
            </SuperButton>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
