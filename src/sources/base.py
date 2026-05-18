from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from src.config import Config


@dataclass
class JobPosting:
    source: str
    company_name: str
    job_title: str
    location: str
    application_link: str
    description: str
    company_website: Optional[str] = None
    posted_date: Optional[date] = None
    experience_required: Optional[str] = None
    salary: Optional[str] = None
    employment_type: Optional[str] = None
    role_category: Optional[str] = None


class JobSource(ABC):
    @abstractmethod
    def fetch_jobs(self, config: Config) -> Iterable[JobPosting]: ...
