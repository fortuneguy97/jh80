#!/usr/bin/env python3
"""
Strong orthographic + phonetic name variant generator (Option B).
Works for any input name (one or many words).
"""

import re
import random
from itertools import product, combinations
from difflib import SequenceMatcher

# -------------------------
# Utility: Soundex (simple phonetic grouping)
# -------------------------
def soundex(name: str) -> str:
    """Return a simple Soundex code for a single word."""
    if not name:
        return ""
    name = name.upper()
    first = name[0]
    # soundex mapping
    mapping = {
        **dict.fromkeys(list("BFPV"), "1"),
        **dict.fromkeys(list("CGJKQSXZ"), "2"),
        **dict.fromkeys(list("DT"), "3"),
        "L": "4",
        **dict.fromkeys(list("MN"), "5"),
        "R": "6"
    }
    # convert letters
    digits = []
    prev = None
    for ch in name[1:]:
        d = mapping.get(ch, "0")
        if d != prev and d != "0":
            digits.append(d)
        prev = d
    code = first + "".join(digits)
    code = re.sub(r'[^A-Z0-9]', '', code)
    return (code + "000")[:4]

# -------------------------
# Syllable-ish splitter (heuristic)
# -------------------------
VOWELS = "aeiouy"
def syllables(word: str):
    w = word.lower()
    # split at vowel groups keeping boundaries
    parts = re.findall(r'[^aeiouy]*[aeiouy]+(?:[^aeiouy]+(?=[aeiouy])|[^aeiouy]*)?', w)
    if not parts:
        return [w]
    return parts

# -------------------------
# Transformation rules (ordered)
# -------------------------
# pattern -> list of replacements
TRANSFORMS = [
    (r"ph", ["f", "ph"]),        # ph <-> f
    (r"ck", ["k", "ck"]),
    (r"qu", ["kw", "qu", "q"]),
    (r"c(?=[eiy])", ["s"]),     # c before e/i/y -> s
    (r"c", ["k"]),
    (r"k", ["c", "ck"]),
    (r"x", ["ks", "x"]),
    (r"v", ["w", "v"]),
    (r"w", ["v", "w"]),
    (r"oo", ["u", "oo"]),
    (r"ou", ["ow", "u", "ou"]),
    (r"ee", ["i", "ee"]),
    (r"ie", ["i", "y", "ie"]),
    (r"y", ["i", "y"]),
    (r"gh", ["g", ""]),          # silent gh or g
    (r"mb$", ["m", "mb"]),       # climb -> clim?
    (r"e$", ["", "e"]),          # trailing e optional
    (r"h", ["", "h"]),           # sometimes silent
    (r"ph", ["f"]),
    (r"tion$", ["shun"]),
]

# explicit cross-language / nickname mappings (small set; extendable)
CROSSMAP = {
    "joseph": ["jose", "josef", "joseppe"],
    "michael": ["mike", "mikal", "mykel"],
    "steven": ["stephen", "stephan"],
    "katherine": ["catherine", "kathryn", "katharine"],
    "john": ["jon", "jahn", "jhon", "joan"],
    "sara": ["sarah"],
    "alexander": ["alex", "aleksandr", "alek"],
    "elizabeth": ["elisabeth", "liza", "liz"],
}

# keyboard-adjacent swaps for common typos (small heuristic)
KEY_NEAR = {
    "a": ["s","q","z"], "s": ["a","d","w","x"], "d":["s","f","e","c"],
    "e":["w","r","s"], "i":["u","o","k"], "o":["i","p","l"],
    "n":["b","m","h"], "m":["n","j","k"],
}

# -------------------------
# Generation helpers
# -------------------------
def apply_transformations(word):
    """Return a set of variants by applying single substitution transforms on the word."""
    variants = set([word])
    lw = word.lower()
    for pattern, replacements in TRANSFORMS:
        for repl in replacements:
            new = re.sub(pattern, repl, lw)
            if new and new != lw:
                variants.add(new)
    return variants

def add_double_letters(word):
    """Insert or remove double letters at consonant positions."""
    results = set([word])
    for i, ch in enumerate(word[:-1]):
        if ch == word[i+1]:
            # remove a double
            results.add(word[:i] + ch + word[i+2:])
        else:
            # insert a double for consonants
            if ch.isalpha() and ch not in VOWELS:
                results.add(word[:i+1] + ch + word[i+1:])
    return results

def transpose_neighbor(word):
    """Return variants where two adjacent letters are swapped (typo-like)."""
    res = set()
    for i in range(len(word)-1):
        lst = list(word)
        lst[i], lst[i+1] = lst[i+1], lst[i]
        res.add("".join(lst))
    return res

def keyboard_typos(word):
    """Introduce single-key nearby typo (lowercase)."""
    res = set()
    for i,ch in enumerate(word.lower()):
        if ch in KEY_NEAR:
            for n in KEY_NEAR[ch]:
                res.add(word[:i] + n + word[i+1:])
    return res

def cross_language_variants(word):
    lw = word.lower()
    return set(CROSSMAP.get(lw, []))

# -------------------------
# Combine generator for a single word
# -------------------------
def variants_for_word(word, depth=2):
    """
    Generate candidate variants for a single word.
    depth: how many transformation steps to combine (1-3)
    """
    word = word.strip()
    if not word:
        return set()

    base = {word}
    # apply rules 1-step
    step1 = set()
    step1 |= apply_transformations(word)
    step1 |= add_double_letters(word)
    step1 |= transpose_neighbor(word)
    step1 |= keyboard_typos(word)
    step1 |= cross_language_variants(word)

    # 2-step: apply transforms to results of step1
    step2 = set()
    if depth >= 2:
        for w in step1:
            step2 |= apply_transformations(w)
            step2 |= add_double_letters(w)
            step2 |= transpose_neighbor(w)
            step2 |= keyboard_typos(w)
            step2 |= cross_language_variants(w)

    # 3-step can be heavy; keep but small
    step3 = set()
    if depth >= 3:
        for w in list(step2)[:80]:
            step3 |= apply_transformations(w)
            step3 |= transpose_neighbor(w)

    all_candidates = base | step1 | step2 | step3
    # clean up: remove empty and keep alphabetic-ish strings
    cleaned = set()
    for w in all_candidates:
        w2 = re.sub(r'[^A-Za-z\-]', '', w)
        if w2:
            cleaned.add(w2.capitalize())
    return cleaned

# -------------------------
# Scoring & filtering
# -------------------------
def similarity_score(a, b):
    """Combined phonetic (soundex) + sequence similarity score in [0,1]."""
    a_snd = soundex(a)
    b_snd = soundex(b)
    snd_score = 1.0 if a_snd == b_snd else 0.5 if a_snd[:2] == b_snd[:2] else 0.0
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()  # 0..1
    # weight phonetic higher
    return 0.6 * snd_score + 0.4 * seq

# -------------------------
# Top-level: combine parts and rank
# -------------------------
def generate_name_variations(full_name: str, limit: int = 30, min_score: float = 0.35):
    """
    full_name: any string (multiple words allowed)
    limit: max number of variants returned
    min_score: minimum combined score per whole-name to keep (0..1)
    """
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return []

    # generate per-part variants
    variants_per_part = [variants_for_word(p, depth=2) for p in parts]

    # include original capitalization as baseline
    original = " ".join([p.capitalize() for p in parts])

    # cartesian product (but limit explosion)
    combos = []
    # produce combinations but avoid explosion: sample intelligently
    # For each part, sort its variants by closeness to original part and take top-N
    sampled_per_part = []
    for i, part in enumerate(parts):
        variants = list(variants_per_part[i])
        # ensure original present
        if part.capitalize() not in variants:
            variants.append(part.capitalize())
        # score each variant by similarity to the original part
        scored = [(v, similarity_score(part, v)) for v in variants]
        scored.sort(key=lambda x: x[1], reverse=True)
        # keep top K per part (K depends on number of words)
        K = 12 if len(parts) == 1 else (8 if len(parts) == 2 else 6)
        sampled = [v for v,_ in scored[:K]]
        sampled_per_part.append(sampled)

    # now take cartesian combinations but cap to product_limit
    product_limit = 4000
    count = 0
    seen = set()
    for combo in product(*sampled_per_part):
        if count > product_limit:
            break
        candidate = " ".join(combo)
        if candidate.lower() == original.lower():
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        count += 1
        combos.append(candidate)

    # score full-name candidates vs original using average per-part soundex+seq
    scored_full = []
    for c in combos:
        parts_c = c.split()
        # average per-part score
        scores = []
        for orig_part, cand_part in zip(parts, parts_c):
            scores.append(similarity_score(orig_part, cand_part))
        avg = sum(scores) / len(scores)
        # small penalty for length difference
        len_pen = max(0.0, 1.0 - abs(len(c) - len(original)) / max(1, len(original)))
        final_score = 0.8 * avg + 0.2 * len_pen
        if final_score >= min_score:
            scored_full.append((c, final_score))

    # sort by score & return top 'limit'
    scored_full.sort(key=lambda x: x[1], reverse=True)
    results = [c for c, s in scored_full[:limit]]

    # if not enough results, relax threshold and fill with best extras
    if len(results) < limit:
        extras = [c for c in combos if c not in results]
        results += extras[:(limit - len(results))]

    return results

# -------------------------
# CLI
# -------------------------
if __name__ == "__main__":
    print("Strong Orthographic + Phonetic Name Variant Generator (Option B)\n")
    name = input("Enter a full name: ").strip()
    if not name:
        print("No name entered. Exiting.")
        raise SystemExit(1)

    # you may tune limit/min_score below
    variants = generate_name_variations(name, limit=30, min_score=0.35)

    print(f"\nOriginal: {name}\n")
    print("Generated variants (top):")
    for v in variants:
        print(" -", v)

