# Where Validator Gets Country/Address Seed

## Overview

The validator gets the country/address seed from **two different sources** depending on whether the identity is a **positive sample** (sanctioned individual) or a **negative sample** (generated name).

## Source 1: Positive Samples (Sanctioned Individuals)

### Source: `Country_Residence` Field

For **positive samples** (sanctioned individuals from the sanctions list), the address comes from the `Country_Residence` field in the sanctioned individuals data.

**Code Location:** `MIID/validator/query_generator.py`

```python
# Line 1495 (transliterated sanctioned individuals)
address = str(person.get("Country_Residence", ""))

# Line 1525 (main sanctioned individuals list)
address = str(person.get("Country_Residence", ""))
```

**What it contains:**
- The actual country of residence from the sanctions database
- Example: `"United States"`, `"United Kingdom"`, `"Russia"`, etc.
- This is the **real country** where the sanctioned individual resides

**Example:**
```python
person = {
    "FirstName": "John",
    "LastName": "Smith",
    "DOB": "1990-01-15",
    "Country_Residence": "United States",  # ← This becomes the seed address
    "Script": "latin"
}
```

## Source 2: Negative Samples (Generated Names)

### Source: `get_random_country()` Function

For **negative samples** (generated fake names), the address comes from `get_random_country()`, which randomly selects a country from **GeonamesCache**.

**Code Location:** `MIID/validator/query_generator.py`

```python
# Line 1658 (non-Latin negative samples)
address = self.get_random_country()

# Line 1707 (Latin negative samples)
address = self.get_random_country()
```

### How `get_random_country()` Works

**Function:** `get_random_country()` (Line 475-481)

```python
def get_random_country(self):
    """Get a random valid country from GeonamesCache."""
    if not self._valid_countries:
        bt.logging.warning("No valid countries available, falling back to empty string")
        return ""
    
    return random.choice(self._valid_countries)
```

### How `_valid_countries` is Loaded

**Function:** `_load_valid_countries()` (Line 375-473)

1. **Loads GeonamesCache:**
   ```python
   self._geonames_cache = geonamescache.GeonamesCache()
   countries_data = self._geonames_cache.get_countries()
   ```

2. **Excludes Territories:**
   - Antarctica, Bouvet Island, Heard Island, etc.
   - Small island nations (Tokelau, Nauru, etc.)
   - Dependencies and territories

3. **Excludes Sanctioned Countries:**
   - Countries from `self.sanctioned_countries` list

4. **Returns Valid Countries:**
   - Only real, valid countries that are not territories or sanctioned
   - Example: `["United States", "United Kingdom", "France", "Germany", ...]`

**Example:**
```python
# Loaded from GeonamesCache
valid_countries = [
    "United States",
    "United Kingdom",
    "France",
    "Germany",
    "Japan",
    # ... ~150+ countries
    # Excludes: Antarctica, Tokelau, sanctioned countries, etc.
]

# Random selection
address = random.choice(valid_countries)  # e.g., "France"
```

## How Address is Sent to Miner

The address is sent to the miner in **two ways**:

### 1. In the Query Template (as placeholder)

The query template includes a placeholder:
```python
address_requirement = f" The following address is the seed country/city to generate address variations for: {{address}}. Generate unique real addresses within the specified country/city for each variation. "
```

**Note:** The `{address}` placeholder is **NOT replaced** in the query template itself. It's sent as-is in the template string.

### 2. In the Synapse Identity Field (actual value)

The actual address value is sent in the `identity` field of the `IdentitySynapse`:

**Code Location:** `MIID/validator/forward.py` (Line 333-344)

```python
# Create identity list with [name, dob, address] arrays
identity_list = [[item['name'], item['dob'], item['address']] for item in seed_names_with_labels]

# Prepare the synapse
request_synapse = IdentitySynapse(
    identity=identity_list,  # [[name1, dob1, address1], [name2, dob2, address2], ...]
    query_template=query_template,  # Contains {address} placeholder (not replaced)
    variations={},
    timeout=adaptive_timeout
)
```

**Example Synapse:**
```python
IdentitySynapse(
    identity=[
        ["John Smith", "1990-01-15", "United States"],
        ["Jane Doe", "1985-03-20", "France"],
        ["Bob Johnson", "1992-07-10", "United Kingdom"]
    ],
    query_template="Generate 10 variations for {name}. The following address is the seed country/city to generate address variations for: {address}. ...",
    variations={}
)
```

## Summary

| Sample Type | Source | What It Contains | Example |
|------------|--------|------------------|---------|
| **Positive** (Sanctioned) | `Country_Residence` field from sanctions DB | Real country of residence | `"United States"` |
| **Negative** (Generated) | `get_random_country()` from GeonamesCache | Random valid country (excludes territories/sanctioned) | `"France"` |

## Key Points

1. **Positive samples** use the **real country** from the sanctions database
2. **Negative samples** use a **random country** from GeonamesCache (valid countries only)
3. The address is sent in the `identity` field of the synapse as `[name, dob, address]`
4. The query template has `{address}` placeholder but it's **not replaced** - the actual value is in the `identity` field
5. GeonamesCache excludes:
   - Territories (Antarctica, small islands, etc.)
   - Sanctioned countries
   - Invalid/empty entries

## For Your Generator

When you receive a synapse, you can access the address like this:

```python
# In your miner's forward() function
for identity in synapse.identity:
    name = identity[0]
    dob = identity[1]
    address = identity[2]  # ← This is the seed address (country/city)
    
    # address could be:
    # - "United States" (from Country_Residence for positive samples)
    # - "France" (from get_random_country() for negative samples)
    # - "New York, USA" (if validator sends city+country format)
```

## Code References

- **Positive samples address:** `query_generator.py` Lines 1495, 1525
- **Negative samples address:** `query_generator.py` Lines 1658, 1707
- **get_random_country():** `query_generator.py` Lines 475-481
- **_load_valid_countries():** `query_generator.py` Lines 375-473
- **Synapse creation:** `forward.py` Lines 333-344

