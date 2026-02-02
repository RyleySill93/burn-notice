import { useState, useRef, useEffect } from 'react'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCreateTask } from '@/hooks/useTasks'

interface AddSubtaskRowProps {
  parentTaskId: string
  projectId?: string
  compact?: boolean
}

export function AddSubtaskRow({ parentTaskId, projectId, compact }: AddSubtaskRowProps) {
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
          parentTaskId,
          completedAt: null
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
          "group flex items-center px-2 py-1.5 cursor-pointer transition-colors",
          compact ? "gap-1" : "gap-2",
          "border-y border-transparent",
          "hover:bg-accent text-muted-foreground hover:text-foreground"
        )}
      >
        {!compact && <div className="w-6" />} {/* Spacer for drag handle alignment */}
        {!compact && <div className="w-5" />} {/* Subtask indent spacer */}
        {!compact && <div className="w-5" />} {/* Spacer for expand/collapse toggle */}
        <div className="flex items-center justify-center w-4 h-4">
          <Plus className="w-3.5 h-3.5" />
        </div>
        <div className="px-1 py-0.5 text-sm">Add subtask</div>
      </div>
    )
  }

  return (
    <div className={cn(
      "flex items-center px-2 py-1.5 border-y border-primary/60 relative",
      compact ? "gap-1" : "gap-2"
    )}>
      {!compact && <div className="w-6" />} {/* Spacer for drag handle alignment */}
      {!compact && <div className="w-5" />} {/* Subtask indent spacer */}
      {!compact && <div className="w-5" />} {/* Spacer for expand/collapse toggle */}
      <div className="w-4 h-4" /> {/* Spacer for checkbox alignment */}
      <input
        ref={inputRef}
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        placeholder="Write a subtask name, press Enter to save"
        className={cn(
          "flex-1 px-1 py-0.5 text-sm outline-none bg-transparent",
          "placeholder:text-muted-foreground/60"
        )}
      />
    </div>
  )
}
