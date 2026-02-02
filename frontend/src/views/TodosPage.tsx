import { useState } from 'react'
import { SuperButton } from '@/components/SuperButton'
import { SuperField } from '@/components/SuperField'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Loader2, Plus, Trash2 } from 'lucide-react'
import { useTodos, useCreateTodo, useUpdateTodo, useDeleteTodo } from '@/hooks/useTodos'

export function TodosPage() {
  const [inputValue, setInputValue] = useState('')
  const [description, setDescription] = useState('')

  const { data: todos = [], isLoading, isError } = useTodos()
  const createTodo = useCreateTodo()
  const updateTodo = useUpdateTodo()
  const deleteTodo = useDeleteTodo()

  const handleAddTodo = () => {
    if (inputValue.trim() === '') return

    createTodo.mutate(
      {
        data: {
          title: inputValue,
          description: description.trim() || undefined,
          completed: false,
        },
      },
      {
        onSuccess: () => {
          setInputValue('')
          setDescription('')
        },
      }
    )
  }

  const handleToggleTodo = (id: string, currentCompleted: boolean) => {
    updateTodo.mutate({
      todoId: id,
      data: {
        completed: !currentCompleted,
      },
    })
  }

  const handleDeleteTodo = (id: string) => {
    deleteTodo.mutate({
      todoId: id,
    })
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAddTodo()
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
        <p className="mt-2 text-gray-600">Loading todos...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center">
        <p className="text-red-600">Error loading todos. Please check if the backend is running.</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <h1 className="text-3xl font-bold text-center mb-6">Todo List</h1>

        <div className="space-y-4">
          <SuperField label="New Todo" name="title" isRequired>
            <div className="flex gap-2">
              <Input
                type="text"
                name="title"
                placeholder="Add a new todo..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                className="flex-1"
                disabled={createTodo.isPending}
              />
              <SuperButton
                onClick={async () => handleAddTodo()}
                disabled={inputValue.trim() === ''}
                leftIcon={Plus}
              >
                Add
              </SuperButton>
            </div>
          </SuperField>
          <SuperField label="Description" name="description" helperText="Optional - add more details about your todo">
            <Input
              type="text"
              name="description"
              placeholder="Description..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={createTodo.isPending}
            />
          </SuperField>
        </div>

        <div className="space-y-2 mt-6">
          {todos.length === 0 ? (
            <p className="text-center text-gray-500 py-8">No todos yet. Add one above!</p>
          ) : (
            todos.map((todo) => (
              <div
                key={todo.id}
                className="flex items-center gap-2 p-3 bg-white dark:bg-gray-800 rounded-lg shadow-sm border"
              >
                <Checkbox
                  checked={todo.completed}
                  onCheckedChange={() => handleToggleTodo(todo.id, todo.completed ?? false)}
                  disabled={updateTodo.isPending}
                />
                <div className="flex-1">
                  <span className={`block ${todo.completed ? 'line-through text-gray-500' : ''}`}>
                    {todo.title}
                  </span>
                  {todo.description && (
                    <span className="text-sm text-gray-600 dark:text-gray-400">
                      {todo.description}
                    </span>
                  )}
                </div>
                <SuperButton
                  onClick={async () => handleDeleteTodo(todo.id)}
                  variant="destructive"
                  size="sm"
                  leftIcon={Trash2}
                >
                  Delete
                </SuperButton>
              </div>
            ))
          )}
        </div>

        {todos.length > 0 && (
          <div className="text-sm text-center text-gray-600 dark:text-gray-400 pt-4">
            {todos.filter((t) => !t.completed).length} of {todos.length} tasks remaining
          </div>
        )}
      </div>
    </div>
  )
}