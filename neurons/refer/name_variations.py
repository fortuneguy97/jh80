import random

# phonetic substitution rules
TRANSFORMATIONS = [
    ("ph", ["f"]),
    ("f", ["ph"]),
    ("c", ["k", "s"]),
    ("k", ["c", "ck"]),
    ("j", ["jh"]),
    ("s", ["z"]),
    ("z", ["s"]),
    ("x", ["ks"]),
    ("v", ["w"]),
    ("w", ["v"]),
    ("oo", ["u"]),
    ("u", ["oo"]),
    ("ee", ["i"]),
    ("i", ["ee", "y"]),
    ("y", ["i"]),
    ("o", ["oh", "o"]),
    ("a", ["ah", "aa"]),
    ("h", ["", "h"]),
]

def generate_variants_for_word(word):
    variants = set([word])
    lw = word.lower()

    for src, subs in TRANSFORMATIONS:
        if src in lw:
            for sub in subs:
                new_word = lw.replace(src, sub)
                variants.add(new_word)

    return {v.capitalize() for v in variants}

def generate_name_variations(full_name, limit=10):
    parts = full_name.split()
    variants_per_part = [generate_variants_for_word(p) for p in parts]

    all_variations = set()

    def combine(index, current):
        if index == len(variants_per_part):
            all_variations.add(" ".join(current))
            return
        for variant in variants_per_part[index]:
            combine(index + 1, current + [variant])

    combine(0, [])
    all_variations.discard(full_name)

    return list(all_variations)[:limit]

if __name__ == "__main__":
    name = input("Enter a name: ")
    results = generate_name_variations(name)

    print("\nGenerated Variations:")
    for r in results:
        print(r)

