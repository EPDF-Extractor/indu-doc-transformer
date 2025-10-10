

def normalize_string(s: str) -> str:
    """Normalize a string for consistent searching."""
    return ' '.join(s.lower().strip().split())