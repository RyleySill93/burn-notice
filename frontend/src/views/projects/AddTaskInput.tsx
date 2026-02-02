import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { useCreateTask } from '@/hooks/useTasks'
import { cn } from '@/lib/utils'

interface AddTaskInputProps {
  projectId?: string
}

export function AddTaskInput({ projectId }: AddTaskInputProps) {
  const [title, setTitle] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const createTask = useCreateTask()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !projectId) return

    await createTask.mutateAsync({
      data: {
        title: title.trim(),
        projectId,
        completedAt: null
      }
    })

    setTitle('')
  }

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className={cn(
        "flex items-center gap-2 border rounded-lg px-3 transition-all",
        isFocused 
          ? "border-primary shadow-sm" 
          : "border-input hover:border-muted-foreground"
      )}>
        <Plus className={cn(
          "h-5 w-5 transition-colors",
          isFocused ? "text-primary" : "text-muted-foreground"
        )} />
        <Input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Add task..."
          className="flex-1 border-none shadow-none focus-visible:ring-0 px-0 py-2"
          disabled={createTask.isPending}
        />
        {title && (
          <button
            type="submit"
            className="text-xs font-medium text-primary hover:text-primary/80 transition-colors"
            disabled={createTask.isPending}
          >
            Add Task
          </button>
        )}
      </div>
    </form>
  )
}