"""
People search scraper for LinkedIn.

Searches for people on LinkedIn and extracts their URLs.
"""
import asyncio
import logging
import random
from typing import Optional, List
from urllib.parse import urlencode
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..models.person_preview import PersonPreview
from .base import BaseScraper

logger = logging.getLogger(__name__)


class PeopleSearchScraper(BaseScraper):
    """
    Scraper for LinkedIn people search results.

    Example:
        async with BrowserManager() as browser:
            scraper = PeopleSearchScraper(browser.page)
            profile_urls = await scraper.search(
                keywords="python",
                location="Poland",
                pages_limit=10
            )
    """

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize people search scraper.

        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())

    async def search(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        pages_limit: int = 1
    ) -> List[PersonPreview]:
        """
        Search for people on LinkedIn.

        Args:
            keywords: Search keywords (e.g., "python developer")
            location: Location filter (e.g., "Poland")
            pages_limit:  Maximum number of result people pages to process.

        Returns:
            List of PersonPreview objects
        """
        logger.info(f"Starting people search: keywords='{keywords}', location='{location}'")

        # Init current page
        current_page = 1
        profiles = []

        # Build search URL
        search_url = self._build_search_url(keywords, location)
        await self.callback.on_start("PeopleSearch", search_url)

        # Navigate to search results
        await self.navigate_and_wait(search_url)
        while current_page <= pages_limit:
            if current_page != 1:
                # Click Next button in pagination
                next_button = self.page.locator('button[aria-label="Next"]')
                try:
                    await next_button.click(timeout=5000)
                except Exception as e:
                    print(await self.page.content())
                    logger.warning(f"Next button not found or not clickable, stopping pagination: {e}")
                    break
                await self.wait_and_focus(2)

            page_profiles = await self._iterate_search(current_page, pages_limit)
            profiles.extend(page_profiles)
            current_page += 1
            print(f"--------------------------------Completed page {current_page}")
            await asyncio.sleep(random.uniform(0, 2))

        await self.callback.on_progress("Search complete", 100)
        await self.callback.on_complete("PeopleSearch", profiles)

        logger.info(f"People search complete: found {len(profiles)} profiles")
        return profiles

    async def _iterate_search(self, current_page, pages_limit):
        """
        Process a single page of search results.

        Args:
            current_page: Current page number being processed
            pages_limit: Maximum number of pages to process (used for progress calculation)

        Returns:
            List of PersonPreview objects extracted from the current page
        """
        search_progress = current_page/pages_limit * 100 - 10

        await self.callback.on_progress("Navigated to search results", search_progress)

        # Wait for people search results to load
        await self.page.wait_for_selector('.search-results-container', timeout=10000)
        await self.wait_and_focus(1)

       # Extract profiles
        return await self._extract_profiles()


    def _build_search_url(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None
    ) -> str:
        """Build LinkedIn people search URL with parameters."""
        base_url = "https://www.linkedin.com/search/results/people/"

        params = {
            'profileLanguage': '["pl"]'
        }
        if keywords:
            params['keywords'] = keywords
        if location:
            params['location'] = location

        # params['origin'] = 'FACETED_SEARCH'

        return f"{base_url}?{urlencode(params)}"

    async def _extract_profiles(self) -> List[PersonPreview]:
        """
        Extract profiles from search results.

        Returns:
            List of PersonPreview objects
        """
        profiles = []
        seen_urls = set()

        try:
            # Find all user result divs - each div with data-chameleon-result-urn represents one person
            user_items = await self.page.locator('div[data-chameleon-result-urn*="urn:li:member"]').all()

            for user_item in user_items:
                try:
                    # Extract LinkedIn URL from the profile link
                    profile_link = user_item.locator('a[href*="/in/"]').first
                    href = await profile_link.get_attribute('href')

                    if not href or '/in/' not in href:
                        continue

                    # Clean URL (remove query params)
                    clean_url = href.split('?')[0] if '?' in href else href

                    # Ensure full URL
                    if not clean_url.startswith('http'):
                        clean_url = f"https://www.linkedin.com{clean_url}"

                    # Skip duplicates and invalid URLs
                    if clean_url in seen_urls or clean_url.count('/in/') != 1:
                        continue

                    # Avoid feed posts, articles, etc.
                    if any(x in clean_url for x in ['/posts/', '/detail/', '/overlay/']):
                        continue

                    # Check if person is open to work from the profile image alt attribute
                    open_to_work = await self._check_open_to_work(user_item)

                    # Extract name, position and location
                    name = await self._extract_name(user_item)
                    position = await self._extract_position(user_item)
                    location = await self._extract_location(user_item)

                    # Create PersonPreview object
                    profile = PersonPreview(
                        linkedin_url=clean_url,
                        open_to_work=open_to_work,
                        name=name,
                        position=position,
                        location=location
                    )
                    print(profile)
                    profiles.append(profile)
                    seen_urls.add(clean_url)

                except Exception as e:
                    logger.debug(f"Error extracting profile: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error extracting profiles: {e}")

        return profiles

    async def _check_open_to_work(self, user_item) -> bool:
        """
        Check if person is open to work based on profile image alt attribute.

        Args:
            user_item: The user list item element to check

        Returns:
            True if person is open to work, False otherwise
        """
        try:
            # Check the alt attribute of the profile image
            # LinkedIn includes "is open to work" in the alt text
            img = user_item.locator('img.presence-entity__image').first
            alt_text = await img.get_attribute('alt')

            if alt_text and 'open to work' in alt_text.lower():
                return True

        except Exception as e:
            logger.debug(f"Error checking open to work status: {e}")

        return False
    async def _extract_name(self, user_item) -> Optional[str]:
        """
        Extract person's name from search result item.

        Args:
            user_item: The user list item element

        Returns:
            Person's name or None if not found
        """
        try:
            # Name is in the profile link with aria-hidden span
            name_link = user_item.locator('a[href*="/in/"] span[aria-hidden="true"]').first
            name = await name_link.text_content()
            return name.strip() if name else None
        except Exception as e:
            logger.debug(f"Error extracting name: {e}")
            return None

    async def _extract_position(self, user_item) -> Optional[str]:
        """
        Extract person's current position from search result item.

        Args:
            user_item: The user list item element

        Returns:
            Person's position or None if not found
        """
        try:
            # Position is in a div with specific class containing job title
            position_div = user_item.locator('div.EBZIKsqCsnpTqCnqpBHmhvufolUwGYHxXvtsE').first
            position = await position_div.text_content()
            return position.strip() if position else None
        except Exception as e:
            logger.debug(f"Error extracting position: {e}")
            return None

    async def _extract_location(self, user_item) -> Optional[str]:
        """
        Extract person's location from search result item.

        Args:
            user_item: The user list item element

        Returns:
            Person's location or None if not found
        """
        try:
            # Location is in a div with specific class
            location_div = user_item.locator('div.UJhpPqzaSvkHBNbtGhibqEhfZgLFJLCVqhsw').first
            location = await location_div.text_content()
            return location.strip() if location else None
        except Exception as e:
            logger.debug(f"Error extracting location: {e}")
            return None
