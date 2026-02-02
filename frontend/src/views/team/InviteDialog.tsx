import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog'
import { SuperButton } from '@/components/SuperButton'
import { SuperField } from '@/components/SuperField'
import { EmailTagInput } from '@/components/EmailTagInput'
import { ProjectMultiSelect } from '@/components/ProjectMultiSelect'
import { useApiError } from '@/hooks/useApiError'
import { useSendInvitation } from '@/generated/invitations/invitations'
import { useListProjects } from '@/generated/projects/projects'
import type { ProjectPermissionGrant } from '@/generated/models'

interface InviteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  customerId: string
}

export function InviteDialog({ open, onOpenChange, customerId }: InviteDialogProps) {
  const apiError = useApiError()
  const sendInvitationMutation = useSendInvitation()
  const { data: projects = [] } = useListProjects({ customer_id: customerId })

  const [emails, setEmails] = useState<string[]>([])
  const [readOnlyProjectIds, setReadOnlyProjectIds] = useState<string[]>([])
  const [editProjectIds, setEditProjectIds] = useState<string[]>([])

  const resetForm = () => {
    setEmails([])
    setReadOnlyProjectIds([])
    setEditProjectIds([])
    apiError.clearError()
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (newOpen) {
      resetForm()
    }
    onOpenChange(newOpen)
  }

  const handleClose = () => {
    onOpenChange(false)
  }

  const handleSubmit = async () => {
    if (emails.length === 0) {
      apiError.setError({ message: 'Please enter at least one email address' })
      return
    }

    apiError.clearError()

    // Build project permissions
    const permissions: ProjectPermissionGrant[] = [
      ...readOnlyProjectIds.map((projectId) => ({
        projectId,
        permissionType: 'READ' as const,
      })),
      ...editProjectIds.map((projectId) => ({
        projectId,
        permissionType: 'WRITE' as const,
      })),
    ]

    try {
      // Send invitation for each email
      for (const email of emails) {
        await sendInvitationMutation.mutateAsync({
          data: {
            email,
            customerId,
            projectPermissions: permissions,
          },
        })
      }
      handleClose()
    } catch (err) {
      apiError.setError(err)
    }
  }

  // Filter out projects that are already selected in the other list
  const availableReadOnlyProjects = projects.filter(
    (p) => !editProjectIds.includes(p.id)
  )
  const availableEditProjects = projects.filter(
    (p) => !readOnlyProjectIds.includes(p.id)
  )

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Invite team members</DialogTitle>
          <DialogDescription>
            Send invitations to add new members to your team
          </DialogDescription>
        </DialogHeader>

        {apiError.ErrorAlert}

        <div className="space-y-4 py-2">
          <SuperField
            label="Email addresses"
            name="emails"
            helperText="Press Enter, comma, or space to add multiple emails"
          >
            <EmailTagInput
              value={emails}
              onChange={setEmails}
              placeholder="Enter email addresses"
            />
          </SuperField>

          <ProjectMultiSelect
            label="Read-only access to projects"
            projects={availableReadOnlyProjects}
            selectedIds={readOnlyProjectIds}
            onChange={setReadOnlyProjectIds}
            emptyMessage={
              projects.length === 0 ? 'No projects yet' : 'All projects assigned to edit'
            }
          />

          <ProjectMultiSelect
            label="Edit access to projects"
            projects={availableEditProjects}
            selectedIds={editProjectIds}
            onChange={setEditProjectIds}
            emptyMessage={
              projects.length === 0 ? 'No projects yet' : 'All projects assigned to read-only'
            }
          />
        </div>

        <DialogFooter>
          <SuperButton variant="outline" onClick={handleClose}>
            Cancel
          </SuperButton>
          <SuperButton
            onClick={handleSubmit}
            disabled={emails.length === 0}
          >
            Send invitations
          </SuperButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
