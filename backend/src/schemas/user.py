"""User projection."""
from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    team: str
