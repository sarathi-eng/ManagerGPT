import re
from urllib.parse import urlparse
from typing import Tuple, List


class SourceValidator:
    """Filter and score sources for quality"""

    # Trusted domains - HIGH quality
    TRUSTED_DOMAINS = {
        # Research & Academia
        "arxiv.org",
        "scholar.google.com",
        "researchgate.net",
        "pubmed.ncbi.nlm.nih.gov",
        "ieee.org",
        "acm.org",
        "springer.com",
        "sciencedirect.com",
        "nature.com",

        # Business & Market Research
        "statista.com",
        "gartner.com",
        "forrester.com",
        "mckinsey.com",
        "bcg.com",
        "bain.com",
        "deloitte.com",
        "pwc.com",
        "kpmg.com",
        "ey.com",
        "grandviewresearch.com",
        "marketsandmarkets.com",
        "ibisworld.com",

        # Government & Official Data
        "gov",
        "census.gov",
        "bls.gov",
        "sec.gov",
        "fda.gov",
        "who.int",
        "worldbank.org",
        "imf.org",
        "oecd.org",
        "un.org",

        # Reputable News & Publications
        "reuters.com",
        "bloomberg.com",
        "wsj.com",
        "ft.com",
        "economist.com",
        "forbes.com",
        "fortune.com",
        "businessinsider.com",
        "techcrunch.com",
        "theverge.com",
        "arstechnica.com",
        "wired.com",
        "mit.edu",

        # Industry-Specific
        "crunchbase.com",
        "pitchbook.com",
        "cbinsights.com",
        "venturebeat.com",
        "harvard.edu",
        "stanford.edu",
        "medium.com",  # Medium allowed if verified publication
    }

    # Acceptable domains - MEDIUM quality
    ACCEPTABLE_DOMAINS = {
        "wikipedia.org",
        "investopedia.com",
        "corporatefinanceinstitute.com",
        "news.ycombinator.com",
        "hackernews.com",
        "stripe.com",
        "shopify.com",
        "aws.amazon.com",
        "cloud.google.com",
        "microsoft.com",
    }

    # Banned domains - REJECT
    BANNED_DOMAINS = {
        "tiktok.com",
        "reddit.com",
        "quora.com",
        "yahoo.answers.com",
        "pinterest.com",
        "instagram.com",
        "facebook.com",
        "twitter.com",
        "apk",
        "download",
        "crack",
        "torrent",
        "wordle",
        "game",
        "dating",
        "casino",
        "porn",
        "xxx",
    }

    # Banned URL patterns
    BANNED_PATTERNS = [
        r"\.apk$",
        r"\.exe$",
        r"\.zip$",
        r"\.rar$",  # Downloads
        r"/download/",
        r"/crack/",
        r"/keygen/",  # Piracy
        r"wordle",
        r"quiz",
        r"puzzle",
        r"game-answer",  # Entertainment
        r"watch.*online",
        r"stream.*free",  # Streaming sites
    ]

    @classmethod
    def validate_source(cls, url: str) -> Tuple[bool, str, float]:
        """
        Validate a source URL

        Returns:
            (is_valid, quality_tier, confidence_score)
            quality_tier: 'HIGH', 'MEDIUM', 'LOW', 'REJECTED'
            confidence_score: 0.0 - 1.0
        """

        try:
            parsed = urlparse(url.lower())
            domain = parsed.netloc.replace("www.", "")
            path = parsed.path.lower()

            # Check banned patterns first
            for pattern in cls.BANNED_PATTERNS:
                if re.search(pattern, url.lower()):
                    return False, "REJECTED", 0.0

            # Check if domain contains banned keywords
            for banned in cls.BANNED_DOMAINS:
                if banned in domain:
                    return False, "REJECTED", 0.0

            # Check trusted domains
            for trusted in cls.TRUSTED_DOMAINS:
                if domain.endswith(trusted) or trusted in domain:
                    return True, "HIGH", 0.95

            # Check acceptable domains
            for acceptable in cls.ACCEPTABLE_DOMAINS:
                if domain.endswith(acceptable) or acceptable in domain:
                    return True, "MEDIUM", 0.75

            # Check if it's a .gov, .edu, or .org from reputable source
            if domain.endswith(".gov"):
                return True, "HIGH", 0.90

            if domain.endswith(".edu"):
                # Only major universities
                if any(uni in domain for uni in ["mit", "stanford", "harvard", "berkeley", "cambridge", "oxford"]):
                    return True, "HIGH", 0.90
                return True, "MEDIUM", 0.70

            if domain.endswith(".org"):
                # Major NGOs and organizations
                if any(org in domain for org in ["world", "international", "global", "foundation"]):
                    return True, "MEDIUM", 0.70

            # Unknown source - low confidence
            return True, "LOW", 0.40

        except Exception:
            return False, "REJECTED", 0.0

    @classmethod
    def filter_sources(cls, sources: List[str], min_quality: str = "MEDIUM") -> List[dict]:
        """
        Filter list of sources and return validated ones

        Args:
            sources: List of URLs
            min_quality: Minimum acceptable quality ('HIGH', 'MEDIUM', 'LOW')

        Returns:
            List of dicts with url, quality, confidence
        """
        quality_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "REJECTED": 0}
        min_level = quality_order.get(min_quality, 2)

        validated = []
        for url in sources:
            is_valid, quality, confidence = cls.validate_source(url)

            if is_valid and quality_order[quality] >= min_level:
                validated.append(
                    {
                        "url": url,
                        "quality": quality,
                        "confidence": confidence,
                    }
                )

        # Sort by quality (HIGH first) then confidence
        validated.sort(
            key=lambda x: (quality_order[x["quality"]], x["confidence"]),
            reverse=True,
        )

        return validated

    @classmethod
    def get_quality_summary(cls, sources: List[dict]) -> str:
        """Generate human-readable quality summary"""
        if not sources:
            return "No valid sources found"

        high = sum(1 for s in sources if s["quality"] == "HIGH")
        medium = sum(1 for s in sources if s["quality"] == "MEDIUM")
        low = sum(1 for s in sources if s["quality"] == "LOW")

        parts = []
        if high:
            parts.append(f"{high} high-quality")
        if medium:
            parts.append(f"{medium} medium-quality")
        if low:
            parts.append(f"{low} low-quality")

        return f"Sources: {', '.join(parts)}"
