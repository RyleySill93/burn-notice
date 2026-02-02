import { useState, useRef, useEffect } from 'react'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCreateTask } from '@/hooks/useTasks'

interface AddTaskRowProps {
  projectId?: string
  sectionId?: string
  nextDisplayOrder?: number
}

export function AddTaskRow({ projectId, sectionId, nextDisplayOrder }: AddTaskRowProps) {
  const [isAdding, setIsAdding] = useState(false)
  const [title, setTitle] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const createTask = useCreateTask()

  useEffect(() => {
    if (isAdding && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isAdding])

  const handleAddClick = () => {
    setIsAdding(true)
  }

  const handleCancel = () => {
    setTitle('')
    setIsAdding(false)
  }

  const handleSave = async () => {
    if (title.trim() && projectId) {
      await createTask.mutateAsync({
        data: {
          title: title.trim(),
          projectId,
          sectionId,
          completedAt: null,
          displayOrder: nextDisplayOrder ?? 1
        }
      })
      setTitle('')
      // Stay in add mode for quick consecutive additions
      if (inputRef.current) {
        inputRef.current.focus()
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      handleCancel()
    }
  }

  const handleBlur = () => {
    // Save if there's text, otherwise cancel
    if (title.trim()) {
      handleSave()
    } else {
      handleCancel()
    }
  }

  if (!isAdding) {
    return (
      <div
        onClick={handleAddClick}
        className={cn(
          "group flex items-center gap-2 px-2 py-1.5 cursor-pointer transition-colors",
          "border-y border-transparent", // always allocate space for borders
          "hover:bg-accent text-muted-foreground hover:text-foreground"
        )}
      >
        <div className="w-6" /> {/* Spacer for drag handle alignment */}
        <div className="flex items-center justify-center w-4 h-4">
          <Plus className="w-3.5 h-3.5" />
        </div>
        <div className="px-1 py-0.5 text-sm">Add task</div>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 px-2 py-1.5 border-y border-primary/60 relative">
      <div className="w-6" /> {/* Spacer for drag handle alignment */}
      <div className="w-4 h-4" /> {/* Spacer for checkbox alignment */}
      <input
        ref={inputRef}
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        placeholder="Write a task name, press Enter to save"
        className={cn(
          "flex-1 px-1 py-0.5 text-sm outline-none bg-transparent",
          "placeholder:text-muted-foreground/60"
        )}
      />
    </div>
  )
}