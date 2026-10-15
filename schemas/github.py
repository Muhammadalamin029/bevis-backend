"""GitHub and project-repository shapes."""

from pydantic import BaseModel, Field


class RepositoryAttach(BaseModel):
    github_repo_id: int
    role: str = Field(default="other", max_length=32)
    tracked_branch: str = Field(default="main", max_length=120)


class RepositoryOut(BaseModel):
    id: str
    project_id: str
    github_repo_id: int
    full_name: str
    role: str
    tracked_branch: str

    model_config = {"from_attributes": True}


class RepositoryAttachOut(RepositoryOut):
    notice: str


class AvailableRepository(BaseModel):
    github_repo_id: int
    full_name: str
    private: bool = False


class InstallationLink(BaseModel):
    installation_id: int = Field(gt=0)
