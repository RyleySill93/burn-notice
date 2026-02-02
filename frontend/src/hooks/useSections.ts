import { useQueryClient } from '@tanstack/react-query'
import type { Section } from '@/types/projects'
import {
  useListSections,
  useCreateSection as useCreateSectionGenerated,
  useUpdateSection as useUpdateSectionGenerated,
  useDeleteSection as useDeleteSectionGenerated,
  getListSectionsQueryKey,
} from '@/generated/sections/sections'

export const useSections = (projectId?: string) => {
  return useListSections(projectId ? { project_id: projectId } : undefined)
}

export const useCreateSection = () => {
  const queryClient = useQueryClient()

  return useCreateSectionGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListSectionsQueryKey() })
      },
    },
  })
}

export const useUpdateSection = () => {
  const queryClient = useQueryClient()

  return useUpdateSectionGenerated({
    mutation: {
      onMutate: async ({ sectionId, data }) => {
        // Cancel outgoing refetches
        await queryClient.cancelQueries({ queryKey: getListSectionsQueryKey() })

        // Snapshot previous value
        const previousSections = queryClient.getQueriesData({ queryKey: getListSectionsQueryKey() })

        // Optimistically update all section queries
        queryClient.setQueriesData(
          { queryKey: getListSectionsQueryKey() },
          (old: Section[] | undefined) => {
            if (!old) return old
            return old.map((section) =>
              section.id === sectionId ? { ...section, ...data } : section
            )
          }
        )

        return { previousSections }
      },
      onError: (_err, _variables, context) => {
        // Rollback on error
        if (context?.previousSections) {
          context.previousSections.forEach(([queryKey, data]) => {
            queryClient.setQueryData(queryKey, data)
          })
        }
      },
      onSettled: () => {
        queryClient.invalidateQueries({ queryKey: getListSectionsQueryKey() })
      },
    },
  })
}

export const useDeleteSection = () => {
  const queryClient = useQueryClient()

  return useDeleteSectionGenerated({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListSectionsQueryKey() })
        queryClient.invalidateQueries({ queryKey: ['/api/tasks/list-tasks'] })
      },
    },
  })
}
