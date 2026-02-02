import datetime
from uuid import UUID

from src.core.authentication.domains import ChallengeTokenCreate
from src.core.authentication.models import ChallengeToken


class ChallengeTokenService:
    @classmethod
    def factory(cls) -> 'ChallengeTokenService':
        return cls()

    def record_used_challenge_token(self, jwt_id: UUID, expiration_at: datetime.datetime) -> ChallengeToken:
        create_token = ChallengeTokenCreate(jwt_id=jwt_id, expiration_at=expiration_at)
        token_record = ChallengeToken.create(create_token)
        return token_record
