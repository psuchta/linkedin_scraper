"""Pydantic models for LinkedIn Person Preview data."""

from typing import Optional
from pydantic import BaseModel, field_validator


class PersonPreview(BaseModel):
    """
    LinkedIn Person Preview model with validation.

    Represents a simplified preview of a LinkedIn profile,
    typically used in search results or listings.
    """
    linkedin_url: str
    open_to_work: bool = False
    name: Optional[str] = None
    position: Optional[str] = None
    location: Optional[str] = None

    @field_validator('linkedin_url')
    @classmethod
    def validate_linkedin_url(cls, v: str) -> str:
        """Validate that URL is a LinkedIn profile URL."""
        if 'linkedin.com/in/' not in v:
            raise ValueError('Must be a valid LinkedIn profile URL (contains /in/)')
        return v

    def to_dict(self) -> dict:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation of the person preview
        """
        return self.model_dump()

    def to_json(self, **kwargs) -> str:
        """
        Convert to JSON string.

        Args:
            **kwargs: Additional arguments for model_dump_json (e.g., indent=2)

        Returns:
            JSON string representation
        """
        return self.model_dump_json(**kwargs)

    def __repr__(self) -> str:
        """String representation."""
        name_str = f"  Name: {self.name}\n" if self.name else ""
        position_str = f"  Position: {self.position}\n" if self.position else ""
        location_str = f"  Location: {self.location}\n" if self.location else ""
        return (
            f"<PersonPreview\n"
            f"{name_str}"
            f"{position_str}"
            f"{location_str}"
            f"  URL: {self.linkedin_url}\n"
            f"  Open to Work: {self.open_to_work}>"
        )
