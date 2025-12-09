#!/usr/bin/env python3
"""
Standalone address normalizer for duplicate detection.

This is the exact function used by the validator to detect duplicate addresses.
Two addresses that normalize to the same string are considered duplicates.

Usage:
    python3 normalize_address_standalone.py "Seh Aqrab Road, Kabul, 1006, Afghanistan"
    python3 normalize_address_standalone.py "address1" "address2" "address3"
"""

import re
import unicodedata
from unidecode import unidecode


def remove_disallowed_unicode(text: str) -> str:
    """Remove disallowed Unicode characters from text, keeping only:
    - Letters (any language)
    - Marks (diacritics)
    - ASCII digits and space
    
    This removes currency symbols (like £), emoji, math operators, etc.
    Also excludes phonetic small-cap blocks AND Latin Extended-D block (U+A720 to U+A7FF)
    which includes characters like ꞎ, ꞙ, ꞟ and similar extended Latin characters.
    """
    allowed = []
    
    for c in text:
        codepoint = ord(c)
        
        # ✅ Updated exclusion: phonetic small-cap blocks + Latin Extended-D block
        # Latin Extended-D (U+A720 to U+A7FF) includes characters like ꞎ, ꞙ, ꞟ
        if (
            0x1D00 <= codepoint <= 0x1D7F or  # Phonetic Extensions
            0x1D80 <= codepoint <= 0x1DBF or  # Phonetic Extensions Supplement
            0xA720 <= codepoint <= 0xA7FF      # Latin Extended-D (includes ꞎ, ꞙ, ꞟ)
        ):
            continue
        
        cat = unicodedata.category(c)
        if cat.startswith("L"):       # ✓ Letter (any language)
            allowed.append(c)
        elif cat.startswith("M"):     # ✓ Mark (diacritics)
            allowed.append(c)
        elif c in " 0123456789":      # ✓ ASCII digits and space
            allowed.append(c)
        else:
            # everything else (symbols, emoji, currency signs, math operators)
            # gets removed
            pass
    return "".join(allowed)


def normalize_address_for_deduplication(addr: str) -> str:
    """Normalize address using Nominatim-style normalization + transliteration + deduplication logic.
    
    This combines:
    1. Remove disallowed Unicode characters (currency symbols, emoji, etc.)
    2. Nominatim-style Unicode normalization (NFKD) and diacritic removal
    3. Transliteration of all non-ASCII characters to ASCII (using unidecode)
    4. Existing deduplication logic (unique words, sorted letters)
    
    This prevents different transliterations/translations of the same address
    from bypassing duplicate detection by converting all scripts to ASCII.
    
    Returns:
        A normalized string. Two addresses that normalize to the same string
        are considered duplicates by the validator.
    """
    if not addr or not addr.strip():
        return ""
    
    # Step 0: Remove disallowed Unicode characters (currency symbols like £, emoji, etc.)
    text = remove_disallowed_unicode(addr)
    
    # Step 1: Apply Nominatim-style normalization (NFKD + diacritic removal)
    # Unicode normalization (NFKD)
    text = unicodedata.normalize("NFKD", text)
    # Remove diacritics
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Lowercase
    text = text.lower()
    # Replace punctuation and symbols with space (like Nominatim)
    text = re.sub(r"[-:,.;!?(){}\[\]\"'""''/\\|*_=+<>@#^&]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Trim
    text = text.strip(" -:")
    
    # Step 2: Transliterate all non-ASCII characters to ASCII
    # This converts Arabic, Cyrillic, Chinese, etc. to their ASCII equivalents
    text = unidecode(text)
    
    # Step 3: Apply existing deduplication logic
    # Replace commas with spaces (if any remain)
    cleaned = text.replace(",", " ")
    parts = [p for p in cleaned.split(" ") if p]
    unique_words = set(parts)
    dedup_text = " ".join(unique_words)
    # Extract letters (non-word, non-digit), excluding specific Unicode chars and lowercase
    letters = re.findall(r'[^\W\d]', dedup_text, flags=re.UNICODE)
    letters = [c.lower() for c in letters if c not in ['\u02BB', '\u02BC']]
    # Sort and join
    normalized = ''.join(sorted(letters))
    
    return normalized


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 normalize_address_standalone.py <address1> [address2] [address3] ...")
        print("\nExample:")
        print('  python3 normalize_address_standalone.py "Seh Aqrab Road, Kabul, 1006, Afghanistan"')
        print('  python3 normalize_address_standalone.py "address1" "address2" "address3"')
        sys.exit(1)
    
    addresses = sys.argv[1:]
    
    print("=" * 80)
    print("ADDRESS NORMALIZATION (DUPLICATE DETECTION)")
    print("=" * 80)
    print()
    
    normalized_results = {}
    for i, addr in enumerate(addresses, 1):
        norm = normalize_address_for_deduplication(addr)
        normalized_results.setdefault(norm, []).append(i)
        print(f"[{i}] {addr}")
        print(f"    normalized: {norm[:120]}... (len={len(norm)})")
        print()
    
    print("=" * 80)
    print("DUPLICATE GROUPS")
    print("=" * 80)
    print("Addresses with the SAME normalized signature are considered duplicates:")
    print()
    
    for norm, idxs in normalized_results.items():
        if len(idxs) > 1:
            print(f"  DUPLICATES (ids {idxs}):")
            for idx in idxs:
                print(f"    [{idx}] {addresses[idx-1]}")
            print(f"    → normalized: {norm[:120]}...")
            print()
        else:
            print(f"  UNIQUE (id {idxs[0]}): {addresses[idxs[0]-1]}")
            print(f"    → normalized: {norm[:120]}...")
            print()




