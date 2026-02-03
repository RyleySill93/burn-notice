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
import { useApiError } from '@/hooks/useApiError'
import { useSendInvitation } from '@/generated/invitations/invitations'

interface InviteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  customerId: string
}

export function InviteDialog({ open, onOpenChange, customerId }: InviteDialogProps) {
  const apiError = useApiError()
  const sendInvitationMutation = useSendInvitation()

  const [emails, setEmails] = useState<string[]>([])

  const resetForm = () => {
    setEmails([])
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

    try {
      // Send invitation for each email
      for (const email of emails) {
        await sendInvitationMutation.mutateAsync({
          data: {
            email,
            customerId,
          },
        })
      }
      handleClose()
    } catch (err) {
      apiError.setError(err)
    }
  }

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
