"""
cleaning.py

Reusable data-cleaning functions: converting/standardizing customer names
and grouping raw store names under a canonical parent/group name.

The name -> group mapping itself is NOT hardcoded here — it's loaded from
mapping.csv via mapping_store.py, so it can be edited (through the app's
"Manage Customer Names" screen, or directly in Excel) without touching
this file or rebuilding the app. See mapping_store.py.

Import this from a notebook (for testing) or from gui/step2_clean.py.
"""

import re

import pandas as pd

from mapping_store import load_mapping


# ---------------------------------------------------------------------
# 1. WHITESPACE NORMALIZATION (defined early — used by both the mapping
#    builder below and the name-cleaning step later)
# ---------------------------------------------------------------------
def normalize_whitespace(text) -> str:
    """
    Fix common whitespace issues seen in real store-name data:
      - leading/trailing spaces        '  ABC '         -> 'ABC'
      - double/irregular internal gaps 'ABC   MART'     -> 'ABC MART'
      - space just inside parentheses  '( PENANG )'     -> '(PENANG)'
                                       '(PENANG  )'     -> '(PENANG)'
    Collapses ALL whitespace characters (regular spaces, tabs, non-breaking
    spaces, other unicode spaces) into a single regular space.
    Always returns a string (non-string input is stringified first).
    """
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)     # collapse any run of whitespace to one space
    text = re.sub(r"\(\s+", "(", text)   # remove space right after '('
    text = re.sub(r"\s+\)", ")", text)   # remove space right before ')'
    return text


# ---------------------------------------------------------------------
# 2. VALIDATION — catches conflicting duplicate keys before they bite you
# ---------------------------------------------------------------------
def validate_mapping(pairs):
    """
    Scan a list of (raw_name, group_name) pairs for raw_names that appear
    more than once mapped to *different* groups. Returns a dict of
    {raw_name: [group1, group2, ...]} for every conflict found.
    Exact duplicate pairs (same name, same group) are not flagged.
    """
    seen = {}
    for raw_name, group_name in pairs:
        seen.setdefault(raw_name, set()).add(group_name)

    return {name: sorted(groups) for name, groups in seen.items() if len(groups) > 1}


# ---------------------------------------------------------------------
# 3. MAPPING BUILD / RELOAD
# ---------------------------------------------------------------------
def build_mapping(pairs=None, on_conflict="warn"):
    """
    Build the final {raw_name: group_name} dict used for df.map().
    Keys are run through the same normalize_whitespace() + uppercase used
    on incoming data, so a stray double space or inconsistent casing in
    the mapping file can't silently break matching against cleaned data.
    on_conflict: 'warn' (print + keep last), 'raise' (stop and raise ValueError),
                 or 'ignore' (silently keep last).
    """
    if pairs is None:
        pairs = load_mapping()

    normalized_pairs = [(normalize_whitespace(name).upper(), group) for name, group in pairs]

    conflicts = validate_mapping(normalized_pairs)
    if conflicts and on_conflict != "ignore":
        msg = "Conflicting mapping entries found (same raw name -> different groups):\n" + \
              "\n".join(f"  - {name!r}: {groups}" for name, groups in conflicts.items())
        if on_conflict == "raise":
            raise ValueError(msg)
        print("WARNING:", msg)

    return dict(normalized_pairs)  # dict() over a list keeps the LAST occurrence per key


# Build once at import time so callers can just do: from cleaning import NAME_TO_GROUP
NAME_TO_GROUP = build_mapping(on_conflict="warn")


def reload_mapping() -> dict:
    """
    Re-read mapping.csv from disk and refresh NAME_TO_GROUP in place.
    Call this after the mapping has been edited (e.g. via the "Manage
    Customer Names" screen) so the app picks up changes without a restart.
    """
    global NAME_TO_GROUP
    NAME_TO_GROUP = build_mapping(on_conflict="warn")
    return NAME_TO_GROUP


# ---------------------------------------------------------------------
# 4. NAME CLEANING (basic standardization before grouping)
# ---------------------------------------------------------------------
def clean_names(df: pd.DataFrame, name_col: str = "Name") -> pd.DataFrame:
    """
    Basic text standardization on the name column: fix whitespace issues
    (via normalize_whitespace) and uppercase for consistent matching.
    Returns a copy of df — does not mutate the original.
    """
    df = df.copy()
    df[name_col] = df[name_col].apply(normalize_whitespace).str.upper()
    return df


# ---------------------------------------------------------------------
# 5. ECONSAVE-SPECIFIC NAME CONVERSION
# ---------------------------------------------------------------------
def convert_econsave_names(df: pd.DataFrame, name_col: str = "Name") -> pd.DataFrame:
    """
    Detects rows where `name_col` starts with a 5-digit code (e.g.
    '10026 BUTTERWORTH', or messier real-world variants like
    '10026   BUTTERWORTH  ( PENANG )' with double spaces / spaced parens).

    Extracts the code into a new 'EconsaveCode' column and rewrites the
    name as 'ECONSAVE - <branch>', with whitespace normalized on both the
    branch name and any row that doesn't match the pattern.
    Rows that don't start with a 5-digit code are left as-is (just
    whitespace-normalized) with an empty 'EconsaveCode'.
    """
    df = df.copy()
    pattern = re.compile(r"^(\d{5})\s+(.*)$")

    def split_code(name):
        cleaned = normalize_whitespace(name)
        match = pattern.match(cleaned)
        if match:
            branch = normalize_whitespace(match.group(2))
            return pd.Series([match.group(1), f"ECONSAVE - {branch}"])
        return pd.Series(["", cleaned])

    df[["EconsaveCode", name_col]] = df[name_col].apply(split_code)
    return df


# ---------------------------------------------------------------------
# 6. GROUPING
# ---------------------------------------------------------------------
def apply_grouping(
    df: pd.DataFrame,
    name_col: str = "Name",
    group_col: str = "group",
    mapping: dict = None,
    default: str = "Other",
) -> pd.DataFrame:
    """
    Add a `group_col` to df by mapping df[name_col] through `mapping`.
    Names not found in the mapping fall back to `default` (so they're
    easy to spot and add to the mapping later, instead of vanishing).
    """
    if mapping is None:
        mapping = NAME_TO_GROUP
    df = df.copy()
    df[group_col] = df[name_col].map(mapping).fillna(default)
    return df


def unmatched_names(df: pd.DataFrame, name_col: str = "Name", mapping: dict = None) -> list:
    """
    Return the sorted list of unique names in df that are NOT covered by
    the mapping. Useful for finding new stores that need to be added.
    """
    if mapping is None:
        mapping = NAME_TO_GROUP
    return sorted(set(df[name_col].astype(str)) - set(mapping.keys()))


# ---------------------------------------------------------------------
# 7. CS BROTHERS-SPECIFIC OUTLET DIFFERENTIATION
# ---------------------------------------------------------------------
# Hardcoded lookup: raw store code (from the invoice data's Code column)
# -> friendly branch name. Hardcoded deliberately, not an external CSV
# like mapping.csv — these codes are a small, stable set, unlike customer
# groupings which change regularly. To add/fix a branch, just edit this
# dict and rebuild/rerun — no GUI editor for this one.
#
# Any code NOT in this dict falls back to showing the raw code as-is
# (see convert_cs_brothers_names below), so an unmapped branch is still
# visible and traceable instead of silently disappearing or crashing.
CS_BROTHERS_CODE_MAP = {
    "300-BANGI": "BANGI",
    "300-H.LGT": "H. LANGAT",
    "300-KAJANG": "KAJANG",
    "300-T.PRK": "T.PRK",
    "300-C0084": "C0084",
    "300-D.PERD": "D.PERD",
}


def convert_cs_brothers_names(
    df: pd.DataFrame,
    name_col: str = "Name",
    code_col: str = "Code",
    group_col: str = "group",
    code_map: dict = None,
) -> pd.DataFrame:
    """
    Unlike Econsave, the CS Brothers outlet code isn't embedded in the
    Name text — it comes from a separate 'Code' column already present
    in the invoice data (from InvoiceConverter's FIELDS list). This runs
    AFTER apply_grouping(), not before, since it needs the group column
    to find CS BROTHERS rows.

    For every row already grouped as 'CS BROTHERS':
      - stores the raw outlet code in a new 'CSBrothersCode' column
      - rewrites the name to 'CS BROTHERS - <friendly name>', looking the
        code up in CS_BROTHERS_CODE_MAP. A code not in the map falls back
        to showing the raw code as-is, so it's still visible rather than
        silently dropped.
    Rows in other groups are left untouched. If a CS BROTHERS row has no
    code (blank/missing), the name is left as-is and the code column is
    blank for that row rather than guessing.
    If `code_col` or `group_col` isn't present in df at all (e.g. someone
    runs cleaning standalone on data with no Code column), this is a
    no-op — df is returned unchanged rather than raising an error.
    """
    df = df.copy()
    if group_col not in df.columns or code_col not in df.columns:
        return df
    if code_map is None:
        code_map = CS_BROTHERS_CODE_MAP

    if "CSBrothersCode" not in df.columns:
        df["CSBrothersCode"] = ""

    mask = df[group_col].astype(str).str.upper() == "CS BROTHERS"
    if not mask.any():
        return df

    def build_name(row):
        code = row[code_col]
        if pd.isna(code) or str(code).strip() == "":
            return row[name_col], ""
        code_str = str(code).strip()
        friendly_name = code_map.get(code_str, code_str)  # fallback to raw code if unmapped
        return f"CS BROTHERS - {friendly_name}", code_str

    results = df.loc[mask].apply(build_name, axis=1)
    df.loc[mask, name_col] = results.apply(lambda t: t[0])
    df.loc[mask, "CSBrothersCode"] = results.apply(lambda t: t[1])

    return df


# ---------------------------------------------------------------------
# 8. CONVENIENCE WRAPPER — one call to run the whole pipeline
# ---------------------------------------------------------------------
def process(
    df: pd.DataFrame,
    name_col: str = "Name",
    group_col: str = "group",
    handle_econsave: bool = True,
    handle_cs_brothers: bool = True,
    code_col: str = "Code",
) -> pd.DataFrame:
    """
    Full pipeline: normalize whitespace, optionally split out Econsave
    branch codes, group, then optionally differentiate CS Brothers
    outlets by their store code. This is what gui/step2_clean.py calls.
    Set handle_econsave=False if this dataset never has Econsave rows.
    Set handle_cs_brothers=False to skip CS Brothers outlet codes.
    """
    df = clean_names(df, name_col=name_col)
    if handle_econsave:
        df = convert_econsave_names(df, name_col=name_col)
    df = apply_grouping(df, name_col=name_col, group_col=group_col)
    if handle_cs_brothers:
        df = convert_cs_brothers_names(df, name_col=name_col, code_col=code_col, group_col=group_col)
    return df


if __name__ == "__main__":
    # Quick manual check when running `python cleaning.py` directly:
    # reports conflicting entries in mapping.csv.
    from mapping_store import get_mapping_path

    conflicts = validate_mapping(load_mapping())
    if conflicts:
        print(f"{len(conflicts)} conflicting name(s) found:")
        for name, groups in conflicts.items():
            print(f"  - {name!r} -> {groups}")
    else:
        print("No conflicts found in mapping.")
    print(f"Mapping file: {get_mapping_path()}")
    print(f"Total mapped names: {len(NAME_TO_GROUP)}")
