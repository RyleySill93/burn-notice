from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID

from src.common.model import BaseModel
from src.network.queue.domains import JobStatusDomain


class JobStatus(BaseModel[JobStatusDomain, JobStatusDomain]):
    job_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String, nullable=False)
    message = Column(String, nullable=True)

    __pk_abbrev__ = 'jstt'
    __read_domain__ = JobStatusDomain
    __create_domain__ = JobStatusDomain
