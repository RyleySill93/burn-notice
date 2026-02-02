import { useQueryClient } from '@tanstack/react-query'
import type { Task } from '@/types/projects'
import {
  useListTasks,
  useGetTask as useGetTaskGenerated,
  useCreateTask as useCreateTaskGenerated,
  useUpdateTask as useUpdateTaskGenerated,
  useDeleteTask as useDeleteTaskGenerated,
  getListTasksQueryKey,
} from '@/generated/tasks/tasks'

export const useTasks = (projectId?: string) => {
  return useListTasks(projectId ? { project_id: projectId } : undefined)
}

export const useTask = (taskId: string) => {
  return useGetTaskGenerated(taskId)
}

export const useCreateTask = () => {
  const queryClient = useQueryClient()

  return useCreateTaskGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTasksQueryKey() })
      },
    },
  })
}

export const useUpdateTask = () => {
  const queryClient = useQueryClient()

  return useUpdateTaskGenerated({
    mutation: {
      onMutate: async ({ taskId, data }) => {
        // Cancel any outgoing refetches
        await queryClient.cancelQueries({ queryKey: getListTasksQueryKey() })

        // Snapshot the previous value
        const previousTasks = queryClient.getQueriesData({ queryKey: getListTasksQueryKey() })

        // Optimistically update to the new value
        queryClient.setQueriesData(
          { queryKey: getListTasksQueryKey() },
          (old: Task[] | undefined) => {
            if (!old) return old
            return old.map((task) =>
              task.id === taskId ? { ...task, ...data } : task
            )
          }
        )

        // Return a context object with the snapshotted value
        return { previousTasks }
      },
      onError: (_err, _variables, context) => {
        // If the mutation fails, use the context returned from onMutate to roll back
        if (context?.previousTasks) {
          context.previousTasks.forEach(([queryKey, data]) => {
            queryClient.setQueryData(queryKey, data)
          })
        }
      },
      onSettled: () => {
        // Always refetch after error or success
        queryClient.invalidateQueries({ queryKey: getListTasksQueryKey() })
      },
    },
  })
}

export const useDeleteTask = () => {
  const queryClient = useQueryClient()

  return useDeleteTaskGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTasksQueryKey() })
      },
    },
  })
}
