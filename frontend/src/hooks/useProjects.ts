import { useQueryClient } from '@tanstack/react-query'
import {
  useListProjects as useListProjectsGenerated,
  useGetProject as useGetProjectGenerated,
  useCreateProject as useCreateProjectGenerated,
  useUpdateProject as useUpdateProjectGenerated,
  useDeleteProject as useDeleteProjectGenerated,
  getListProjectsQueryKey,
} from '@/generated/projects/projects'

export const useProjects = (customerId?: string) => {
  return useListProjectsGenerated(
    { customer_id: customerId! },
    { query: { enabled: !!customerId } }
  )
}

export const useProject = (projectId?: string) => {
  return useGetProjectGenerated(projectId!, {
    query: {
      enabled: !!projectId,
    },
  })
}

export const useCreateProject = () => {
  const queryClient = useQueryClient()

  return useCreateProjectGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() })
      },
    },
  })
}

export const useUpdateProject = () => {
  const queryClient = useQueryClient()

  return useUpdateProjectGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() })
      },
    },
  })
}

export const useDeleteProject = () => {
  const queryClient = useQueryClient()

  return useDeleteProjectGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() })
      },
    },
  })
}
