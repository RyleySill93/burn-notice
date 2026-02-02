class InvitationException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class InvitationNotFound(InvitationException):
    pass


class InvitationExpired(InvitationException):
    pass


class InvitationAlreadyAccepted(InvitationException):
    pass


class InvitationRevoked(InvitationException):
    pass


class UserAlreadyMember(InvitationException):
    pass
