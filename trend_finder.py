import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TrendFinder")

# Keywords identifying scientifically and educationally suitable video topics
SCIENCE_KEYWORDS = [
    "space", "nasa", "isro", "astronomy", "physics", "quantum", "gravity",
    "planet", "star", "galaxy", "black hole", "telescope", "mars", "moon",
    "solar", "sun", "earth", "science", "scientists", "discovery", "biology",
    "dna", "cell", "genetics", "fossil", "dinosaur", "evolution", "brain",
    "neuroscience", "ai", "artificial intelligence", "robot", "supercomputer",
    "nuclear", "fusion", "particle", "atom", "chemistry", "element", "laser",
    "climate", "atmosphere", "antarctica", "deep sea", "ocean", "volcano",
    "asteroid", "meteor", "comet", "hubble", "james webb", "chandrayaan"
]

# Disallowed topics (politics, sports, entertainment gossip, crime, speculative finance)
DISALLOWED_TREND_KEYWORDS = [
    "election", "politics", "minister", "bjp", "congress", "party", "modi",
    "cricket", "ipl", "match", "score", "wicket", "t20", "bollywood", "actor",
    "actress", "box office", "movie review", "trailer", "celebrity", "gossip",
    "scam", "arrested", "police", "murder", "crime", "crypto", "bitcoin",
    "stock market", "sensex", "nifty", "share price"
]

class TrendFinder:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def fetch_rss_feed(self, url: str, timeout: int = 5):
        """Fetches and parses an RSS feed with status, timeout, and XML error handling."""
        try:
            logger.info(f"Fetching RSS feed: {url}")
            response = requests.get(url, headers=self.headers, timeout=timeout)
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.content)
                    if root.tag.lower() in ["html", "head", "body"] or "error" in root.tag.lower():
                        logger.warning(f"Response from '{url}' was HTML error page, not RSS feed.")
                        return None
                    return root
                except ET.ParseError as xml_err:
                    logger.warning(f"Malformed XML in RSS feed '{url}': {xml_err}")
                    return None
            elif response.status_code == 429:
                logger.warning(f"Rate limited (HTTP 429) fetching feed '{url}'. Skipping gracefully.")
                return None
            elif response.status_code == 404:
                logger.warning(f"Feed not found (HTTP 404) at '{url}'. Upstream endpoint may be deprecated.")
                return None
            else:
                logger.warning(f"Failed to fetch {url}, status code: {response.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout ({timeout}s) fetching RSS feed: {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {e}")
            return None

    def get_nasa_trends(self) -> List[Dict]:
        """Fetches active space exploration and scientific news from NASA Breaking News RSS."""
        url = "https://www.nasa.gov/news-release/feed/"
        root = self.fetch_rss_feed(url)
        trends = []
        if root is not None:
            for item in root.findall('.//item'):
                title = item.find('title')
                description = item.find('description')
                title_text = title.text.strip() if title is not None and title.text else ""
                desc_text = description.text.strip() if description is not None and description.text else ""
                if title_text:
                    trends.append({
                        "title": title_text,
                        "description": desc_text,
                        "traffic": "Verified NASA Space News",
                        "source": "NASA Breaking News",
                        "discovery_type": "LIVE_TREND",
                        "score": 60
                    })
        return trends

    def get_phys_org_trends(self) -> List[Dict]:
        """Fetches active science breakthroughs from Phys.org RSS."""
        url = "https://phys.org/rss-feed/"
        root = self.fetch_rss_feed(url)
        trends = []
        if root is not None:
            for item in root.findall('.//item'):
                title = item.find('title')
                description = item.find('description')
                title_text = title.text.strip() if title is not None and title.text else ""
                desc_text = description.text.strip() if description is not None and description.text else ""
                if title_text:
                    trends.append({
                        "title": title_text,
                        "description": desc_text,
                        "traffic": "Active Phys.org Research",
                        "source": "Phys.org Science",
                        "discovery_type": "LIVE_TREND",
                        "score": 50
                    })
        return trends

    def get_news_trends(self) -> List[Dict]:
        """Fetches global science & environment news from BBC Science RSS."""
        url = "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
        root = self.fetch_rss_feed(url)
        trends = []
        if root is not None:
            for item in root.findall('.//item'):
                title = item.find('title')
                description = item.find('description')
                title_text = title.text.strip() if title is not None and title.text else ""
                desc_text = description.text.strip() if description is not None and description.text else ""
                if title_text:
                    trends.append({
                        "title": title_text,
                        "description": desc_text,
                        "traffic": "BBC Science Wire",
                        "source": "BBC Science & Environment",
                        "discovery_type": "LIVE_TREND",
                        "score": 45
                    })
        return trends

    def get_science_daily_trends(self) -> List[Dict]:
        """Fetches top science headlines from ScienceDaily RSS."""
        url = "https://www.sciencedaily.com/rss/top/science.xml"
        root = self.fetch_rss_feed(url)
        trends = []
        if root is not None:
            for item in root.findall('.//item'):
                title = item.find('title')
                description = item.find('description')
                title_text = title.text.strip() if title is not None and title.text else ""
                desc_text = description.text.strip() if description is not None and description.text else ""
                if title_text:
                    trends.append({
                        "title": title_text,
                        "description": desc_text,
                        "traffic": "ScienceDaily Top Headlines",
                        "source": "ScienceDaily",
                        "discovery_type": "LIVE_TREND",
                        "score": 40
                    })
        return trends

    def get_google_trends(self) -> List[Dict]:
        """Maintains backward compatibility interface; queries BBC science wire."""
        return self.get_news_trends()

    def get_reddit_trends(self) -> List[Dict]:
        """Maintains backward compatibility interface; queries Phys.org feed."""
        return self.get_phys_org_trends()

    def get_combined_trends(self) -> List[Dict]:
        """Fetches trends from maintained feeds and returns them sorted by popularity score."""
        all_trends = []

        # NASA Science & Space Releases
        try:
            all_trends.extend(self.get_nasa_trends())
        except Exception as e:
            logger.error(f"Failed to retrieve NASA trends: {e}")

        # Phys.org Research News
        try:
            all_trends.extend(self.get_phys_org_trends())
        except Exception as e:
            logger.error(f"Failed to retrieve Phys.org trends: {e}")

        # BBC Science & Environment
        try:
            all_trends.extend(self.get_news_trends())
        except Exception as e:
            logger.error(f"Failed to retrieve BBC news trends: {e}")

        # ScienceDaily Headlines
        try:
            all_trends.extend(self.get_science_daily_trends())
        except Exception as e:
            logger.error(f"Failed to retrieve ScienceDaily trends: {e}")

        # Remove empty titles and sort by score descending
        valid_trends = [t for t in all_trends if t["title"].strip()]
        sorted_trends = sorted(valid_trends, key=lambda x: x["score"], reverse=True)
        
        # De-duplicate items with similar titles
        seen = set()
        deduped = []
        for item in sorted_trends:
            norm_title = "".join(c for c in item["title"].lower() if c.isalnum())
            if norm_title not in seen:
                seen.add(norm_title)
                deduped.append(item)
                
        return deduped

    def is_science_trend(self, text: str) -> bool:
        """Evaluates whether trend text is scientifically or educationally relevant and free of disallowed topics."""
        lower = text.lower()
        # Reject disallowed topics (politics, sports, gossip, crime)
        if any(re.search(r'\b' + re.escape(kw) + r'\b', lower) for kw in DISALLOWED_TREND_KEYWORDS):
            return False
        # Require at least one substantive science keyword
        return any(re.search(r'\b' + re.escape(kw) + r'\b', lower) for kw in SCIENCE_KEYWORDS)

    def filter_science_trends(self, trends: List[Dict]) -> List[Dict]:
        """Filters discovered trends for scientific and educational relevance."""
        science_trends = []
        for t in trends:
            title = t.get("title", "")
            desc = t.get("description", "")
            combined = f"{title} {desc}"
            if self.is_science_trend(combined):
                science_trends.append(t)
        return science_trends

    def get_trending_science_topics(self, max_results: int = 5) -> List[Dict]:
        """
        Fetches real-time trends from Google Trends, Reddit science/tech subreddits, and news,
        filtering strictly for science topics.
        Never invents trends or statistics without real feed data.
        """
        all_trends = self.get_combined_trends()
        science_trends = self.filter_science_trends(all_trends)
        return science_trends[:max_results]

if __name__ == "__main__":
    finder = TrendFinder()
    trends = finder.get_combined_trends()
    print(f"Discovered {len(trends)} trending topics:")
    for idx, t in enumerate(trends[:10], 1):
        print(f"{idx}. [{t['source']}] {t['title']} (Score: {t['score']}, Traffic: {t['traffic']})")
