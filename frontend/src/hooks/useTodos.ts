import { useQueryClient } from '@tanstack/react-query'
import {
  useListTodos as useListTodosGenerated,
  useGetTodo as useGetTodoGenerated,
  useCreateTodo as useCreateTodoGenerated,
  useUpdateTodo as useUpdateTodoGenerated,
  useDeleteTodo as useDeleteTodoGenerated,
  getListTodosQueryKey,
} from '@/generated/todos/todos'

export const useTodos = () => {
  return useListTodosGenerated()
}

export const useTodo = (id: string) => {
  return useGetTodoGenerated(id)
}

export const useCreateTodo = () => {
  const queryClient = useQueryClient()

  return useCreateTodoGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTodosQueryKey() })
      },
    },
  })
}

export const useUpdateTodo = () => {
  const queryClient = useQueryClient()

  return useUpdateTodoGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTodosQueryKey() })
      },
    },
  })
}

export const useDeleteTodo = () => {
  const queryClient = useQueryClient()

  return useDeleteTodoGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTodosQueryKey() })
      },
    },
  })
}
