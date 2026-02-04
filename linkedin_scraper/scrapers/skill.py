"""Skill scraper for LinkedIn profiles."""

import logging
from typing import Optional
from playwright.async_api import Page

from .base import BaseScraper
from ..models.person import Skill
from ..callbacks import ProgressCallback, SilentCallback
from ..core.exceptions import ScrapingError

logger = logging.getLogger(__name__)


class SkillScraper(BaseScraper):
    """Async scraper for LinkedIn profile skills."""
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize skill scraper.
        
        Args:
            page: Playwright page object
            callback: Progress callback
        """
        super().__init__(page, callback)
    
    async def scrape(self, linkedin_url: str) -> list[Skill]:
        """
        Scrape skills from a LinkedIn profile.
        
        Args:
            linkedin_url: LinkedIn profile URL
            
        Returns:
            List of Skill objects
            
        Raises:
            AuthenticationError: If not logged in
            ScrapingError: If scraping fails
        """
        await self.callback.on_start("skills", linkedin_url)
        
        try:
            # Navigate to skills page
            skills_url = f"{linkedin_url.rstrip('/')}/details/skills/"
            await self.navigate_and_wait(skills_url)
            await self.callback.on_progress("Navigated to skills page", 20)
            
            # Check authentication
            await self.ensure_logged_in()
            
            # Wait for main content
            await self.page.wait_for_selector('main', timeout=10000)
            await self.wait_and_focus(1)
            
            # Scroll to load all skills
            await self.scroll_page_to_bottom(pause_time=0.5, max_scrolls=3)
            await self.callback.on_progress("Scrolled to load skills", 50)
            
            # Get skills
            skills = await self._get_skills()
            await self.callback.on_progress(f"Got {len(skills)} skills", 100)
            
            await self.callback.on_complete("skills", skills)
            
            return skills
            
        except Exception as e:
            await self.callback.on_error(e)
            raise ScrapingError(f"Failed to scrape skills: {e}")
    
    async def _get_skills(self) -> list[Skill]:
        """
        Extract all skills from the skills page.
        
        Returns:
            List of Skill objects
        """
        skills = []
        
        try:
            # Find all skill items
            skill_items = await self.page.locator('[data-view-name="profile-component-entity"]').all()
            
            for item in skill_items:
                try:
                    # Get skill name from the main skill link (has data-field="skill_page_skill_topic")
                    skill_link = item.locator('a[data-field="skill_page_skill_topic"]')
                    if await skill_link.count() == 0:
                        continue
                    
                    # Extract skill name from the link
                    name_span = skill_link.locator('span[aria-hidden="true"]').first
                    name = await name_span.inner_text()
                    name = name.strip()
                    
                    if not name:
                        continue
                    
                    # Try to get endorsement count - two-stage approach
                    endorsements = None
                    try:
                        # Stage 1: Try to get from endorsers link (has /endorsers in href)
                        endorsers_link = item.locator('a[href*="/endorsers"]')
                        if await endorsers_link.count() > 0:
                            endorsement_text = await endorsers_link.inner_text()
                            if endorsement_text and "endorsement" in endorsement_text.lower():
                                endorsements = int(endorsement_text.strip().split()[0])
                        
                        # Stage 2: If no endorsers link found, search all text for "endorsement"
                        if endorsements is None:
                            item_text = await item.inner_text()
                            # Look for pattern like "5 endorsements" or "1 endorsement"
                            words = item_text.lower().split()
                            for i, word in enumerate(words):
                                if "endorsement" in word and i > 0:
                                    # Check if previous word is a number
                                    try:
                                        endorsements = int(words[i-1])
                                        break
                                    except ValueError:
                                        continue
                    except (ValueError, IndexError, Exception) as e:
                        logger.debug(f"Could not parse endorsements: {e}")
                    
                    skills.append(Skill(
                        name=name,
                        endorsements=endorsements
                    ))
                    
                except Exception as e:
                    logger.debug(f"Error parsing skill item: {e}")
                    continue
            
            logger.info(f"Extracted {len(skills)} skills")
            return skills
            
        except Exception as e:
            logger.warning(f"Error getting skills: {e}")
            return []
