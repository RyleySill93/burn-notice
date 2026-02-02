from src.common.enum import BaseEnum

INVITATION_PK_ABBREV = 'invt'


class InvitationStatusEnum(BaseEnum):
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    EXPIRED = 'EXPIRED'
    REVOKED = 'REVOKED'
