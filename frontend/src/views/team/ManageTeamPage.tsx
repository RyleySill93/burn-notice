import { useState } from 'react'
import { UserPlus, Users, Mail, MoreHorizontal, Trash2, Send } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { SuperButton } from '@/components/SuperButton'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { InviteDialog } from '@/views/team/InviteDialog'
import { useAuth } from '@/contexts/AuthContext'
import {
  useListInvitations,
  useListTeamMembers,
  useRemoveTeamMember,
  useResendInvitation,
  useRevokeInvitation,
  getListTeamMembersQueryKey,
  getListInvitationsQueryKey,
} from '@/generated/invitations/invitations'
import { useQueryClient } from '@tanstack/react-query'
import type { InvitationRead, MembershipWithUser } from '@/generated/models'

export function ManageTeamPage() {
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false)
  const { currentCustomerId, user } = useAuth()
  const queryClient = useQueryClient()

  const removeTeamMemberMutation = useRemoveTeamMember({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTeamMembersQueryKey({ customer_id: currentCustomerId ?? '' }) })
      },
    },
  })

  const resendInvitationMutation = useResendInvitation({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListInvitationsQueryKey({ customer_id: currentCustomerId ?? '' }) })
      },
    },
  })

  const revokeInvitationMutation = useRevokeInvitation({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListInvitationsQueryKey({ customer_id: currentCustomerId ?? '' }) })
      },
    },
  })

  const handleRemoveMember = async (membershipId: string) => {
    await removeTeamMemberMutation.mutateAsync({ membershipId })
  }

  const handleResendInvitation = async (invitationId: string) => {
    await resendInvitationMutation.mutateAsync({ invitationId })
  }

  const handleRevokeInvitation = async (invitationId: string) => {
    await revokeInvitationMutation.mutateAsync({ invitationId })
  }

  const { data: teamMembers = [], isLoading: teamMembersLoading } = useListTeamMembers(
    { customer_id: currentCustomerId ?? '' },
    { query: { enabled: !!currentCustomerId } }
  )

  const { data: invitations = [], isLoading: invitationsLoading } = useListInvitations(
    { customer_id: currentCustomerId ?? '' },
    { query: { enabled: !!currentCustomerId } }
  )

  const pendingInvitations = invitations.filter(
    (inv: InvitationRead) => inv.status === 'PENDING'
  )

  const getInitials = (email: string) => {
    return email.slice(0, 2).toUpperCase()
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  if (!currentCustomerId) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No team found</p>
          <p className="text-sm">Create or join a team to manage members</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Team members</h1>
            <p className="text-muted-foreground">
              Manage your team and their permissions
            </p>
          </div>
          <SuperButton leftIcon={UserPlus} onClick={() => setInviteDialogOpen(true)}>
            Invite members
          </SuperButton>
        </div>

        {/* Team Members List */}
        <div className="bg-white rounded-lg border shadow-sm">
          <div className="px-4 py-3 border-b">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Users className="h-4 w-4" />
              <span>Team members</span>
            </div>
          </div>

          <div className="divide-y">
            {teamMembersLoading ? (
              <div className="p-8 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
              </div>
            ) : teamMembers.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No team members yet</p>
              </div>
            ) : (
              teamMembers.map((membership: MembershipWithUser) => {
                const memberEmail = membership.user?.email ?? 'Unknown'
                const memberName = membership.user?.firstName && membership.user?.lastName
                  ? `${membership.user.firstName} ${membership.user.lastName}`
                  : null
                const isCurrentUser = membership.userId === user?.id

                return (
                  <div
                    key={membership.id}
                    className="flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Avatar>
                        <AvatarFallback>{getInitials(memberEmail)}</AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="font-medium">
                          {memberName ?? memberEmail}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {memberName ? memberEmail : null}
                          {isCurrentUser && (memberName ? ' · You' : 'You')}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <Badge variant="secondary">Member</Badge>

                      {!isCurrentUser && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="p-1 rounded hover:bg-muted">
                              <MoreHorizontal className="h-4 w-4" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => handleRemoveMember(membership.id)}
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Remove member
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Pending Invitations Section */}
        <div className="bg-white rounded-lg border shadow-sm">
          <div className="px-4 py-3 border-b">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Mail className="h-4 w-4" />
              <span>Pending invitations ({pendingInvitations.length})</span>
            </div>
          </div>

          <div className="divide-y">
            {invitationsLoading ? (
              <div className="p-8 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
              </div>
            ) : pendingInvitations.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <Mail className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No pending invitations</p>
              </div>
            ) : (
              pendingInvitations.map((invitation: InvitationRead) => (
                <div
                  key={invitation.id}
                  className="flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Avatar>
                      <AvatarFallback>{getInitials(invitation.email)}</AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium">{invitation.email}</p>
                      <p className="text-sm text-muted-foreground">
                        Invited {formatDate(invitation.createdAt)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <Badge variant="outline">Pending</Badge>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="p-1 rounded hover:bg-muted">
                          <MoreHorizontal className="h-4 w-4" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => handleResendInvitation(invitation.id)}>
                          <Send className="h-4 w-4 mr-2" />
                          Resend invitation
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => handleRevokeInvitation(invitation.id)}
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Revoke invitation
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <InviteDialog
        open={inviteDialogOpen}
        onOpenChange={setInviteDialogOpen}
        customerId={currentCustomerId}
      />
    </div>
  )
}
