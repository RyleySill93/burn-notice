import datetime
from uuid import UUID

from loguru import logger

from src.core.authentication.domains import ChallengeTokenCreate
from src.core.authentication.models import ChallengeToken


class ChallengeTokenService:
    @classmethod
    def factory(cls) -> 'ChallengeTokenService':
        return cls()

    def record_used_challenge_token(self, jwt_id: UUID, expiration_at: datetime.datetime) -> ChallengeToken:
        # Don't include id in the create payload - let the database generate it
        create_token = ChallengeTokenCreate(jwt_id=jwt_id, expiration_at=expiration_at)
        logger.debug('Creating challenge token record', jwt_id=str(jwt_id), payload=create_token.to_dict())
        token_record = ChallengeToken.create(create_token)
        return token_record
