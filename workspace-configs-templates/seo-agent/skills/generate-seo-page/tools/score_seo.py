"""SEO scoring tool that evaluates content for basic on-page SEO factors."""

import re
from langchain_core.tools import tool


@tool
def score_seo(content: str, primary_keyword: str) -> dict:
    """Score content for on-page SEO factors given a primary keyword.

    Args:
        content: The page content in markdown or plain text.
        primary_keyword: The primary keyword to evaluate against.

    Returns:
        A dictionary with individual scores and an overall SEO score.
    """
    keyword_lower = primary_keyword.lower()
    content_lower = content.lower()
    words = content_lower.split()
    word_count = len(words)

    scores = {}

    # Word count (target: 800-1500)
    if 800 <= word_count <= 1500:
        scores["word_count"] = {"score": 10, "detail": f"{word_count} words (ideal range)"}
    elif 500 <= word_count < 800 or 1500 < word_count <= 2000:
        scores["word_count"] = {"score": 7, "detail": f"{word_count} words (acceptable)"}
    else:
        scores["word_count"] = {"score": 3, "detail": f"{word_count} words (outside ideal range)"}

    # Keyword density (target: 1-2%) — whole-word matches only
    keyword_count = len(re.findall(r"\b" + re.escape(keyword_lower) + r"\b", content_lower))
    density = (keyword_count / max(word_count, 1)) * 100
    if 1.0 <= density <= 2.0:
        scores["keyword_density"] = {"score": 10, "detail": f"{density:.1f}% (ideal)"}
    elif 0.5 <= density < 1.0 or 2.0 < density <= 3.0:
        scores["keyword_density"] = {"score": 6, "detail": f"{density:.1f}% (acceptable)"}
    else:
        scores["keyword_density"] = {"score": 2, "detail": f"{density:.1f}% (poor)"}

    # H1 presence with keyword
    h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if h1_match and keyword_lower in h1_match.group(1).lower():
        scores["h1_keyword"] = {"score": 10, "detail": "H1 contains primary keyword"}
    elif h1_match:
        scores["h1_keyword"] = {"score": 5, "detail": "H1 present but missing keyword"}
    else:
        scores["h1_keyword"] = {"score": 0, "detail": "No H1 found"}

    # H2 count (target: 3-5)
    h2_count = len(re.findall(r"^##\s+", content, re.MULTILINE))
    if 3 <= h2_count <= 5:
        scores["h2_structure"] = {"score": 10, "detail": f"{h2_count} H2 headings (ideal)"}
    elif 1 <= h2_count <= 2 or 6 <= h2_count <= 8:
        scores["h2_structure"] = {"score": 6, "detail": f"{h2_count} H2 headings"}
    else:
        scores["h2_structure"] = {"score": 2, "detail": f"{h2_count} H2 headings"}

    # Meta description check
    has_meta = bool(re.search(r"(meta.?description|description:)", content_lower))
    scores["meta_description"] = {
        "score": 10 if has_meta else 0,
        "detail": "Meta description present" if has_meta else "No meta description found",
    }

    # Overall score
    total = sum(s["score"] for s in scores.values())
    max_total = len(scores) * 10
    overall = round((total / max_total) * 100)

    return {
        "overall_score": overall,
        "max_score": 100,
        "factors": scores,
        "keyword": primary_keyword,
        "word_count": word_count,
        "keyword_occurrences": keyword_count,
    }
