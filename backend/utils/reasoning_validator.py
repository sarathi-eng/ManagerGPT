import re


class ReasoningValidator:
    """Validate quality of business reasoning"""

    WEAK_PHRASES = [
        "seems",
        "appears",
        "might",
        "could",
        "possibly",
        "potential exists",
        "requires validation",
        "needs investigation",
        "market looks",
        "demand appears",
        "seems viable",
    ]

    REQUIRED_ELEMENTS = [
        r"\$[\d,\.]+[MBK]?",  # Money amounts
        r"\d+%",  # Percentages
        r"\d+[\.,]\d+",  # Decimal numbers
        r"\([A-Z][a-z]+ \d{4}\)",  # Source citations like (Statista 2024)
        r"\([A-Z][A-Z]+\)",  # Acronym sources like (SEC)
    ]

    @classmethod
    def validate_reasoning(cls, reasoning: str) -> dict:
        """
        Check if reasoning meets quality standards

        Returns:
            {
                "is_strong": bool,
                "score": float (0-1),
                "issues": list[str],
                "suggestions": list[str]
            }
        """

        issues = []
        suggestions = []
        score = 1.0
        reasoning_text = reasoning or ""

        weak_count = sum(1 for phrase in cls.WEAK_PHRASES if phrase in reasoning_text.lower())
        if weak_count > 2:
            issues.append(f"Contains {weak_count} weak/vague phrases")
            suggestions.append("Replace vague language with specific data")
            score -= 0.2

        has_numbers = bool(re.search(r"\d", reasoning_text))
        if not has_numbers:
            issues.append("No quantitative data referenced")
            suggestions.append("Include specific numbers from research")
            score -= 0.3

        has_sources = bool(re.search(r"\([A-Z]", reasoning_text))
        if not has_sources:
            issues.append("No sources cited")
            suggestions.append("Cite sources inline: (McKinsey 2024)")
            score -= 0.2

        if len(reasoning_text) < 200:
            issues.append("Reasoning too brief")
            suggestions.append("Provide more detailed analysis")
            score -= 0.1

        element_count = sum(
            1 for pattern in cls.REQUIRED_ELEMENTS if re.search(pattern, reasoning_text)
        )

        if element_count < 2:
            issues.append("Insufficient evidence anchors")
            suggestions.append("Include more specific data points")
            score -= 0.2

        score = max(0.0, score)

        return {
            "is_strong": score >= 0.7,
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
        }
