"""
Build a PyGraphistry graph from LDBC SNB SF1 CSV data using a Polars backend.

This script reads the CSV files under ../csv/, normalises them into a unified
nodes table and a unified edges table (both with native integer ids), adds
boolean ``label__<Label>`` columns on nodes for GFQL Cypher ``:Label`` matching,
and a ``type`` string column on edges for ``[:REL_TYPE]`` matching, then writes
them as Parquet files for fast reuse.

IDs are kept as native integers. GFQL's ``:Label`` filter restricts to a
single node type *before* joining on ``id``, so IDs only need to be unique
within a type (which they are) — across-type collisions are resolved by the
label filter. Integer joins keep the GFQL Polars backend fast.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parent
CSV_ROOT = REPO_ROOT / "csv"
OUT_DIR = SCRIPT_ROOT / "graph_data"

# ── Node files ──────────────────────────────────────────────────────────────
NODE_CSVS: dict[str, Path] = {
    "Comment": CSV_ROOT / "dynamic" / "comment_0_0.csv",
    "Forum": CSV_ROOT / "dynamic" / "forum_0_0.csv",
    "Organisation": CSV_ROOT / "static" / "organisation_0_0.csv",
    "Person": CSV_ROOT / "dynamic" / "person_0_0.csv",
    "Place": CSV_ROOT / "static" / "place_0_0.csv",
    "Post": CSV_ROOT / "dynamic" / "post_0_0.csv",
    "Tag": CSV_ROOT / "static" / "tag_0_0.csv",
    "Tagclass": CSV_ROOT / "static" / "tagclass_0_0.csv",
}

# ── Edge specs: (name, src_label, dst_label, filename_stem) ─────────────────
EDGE_SPECS: list[tuple[str, str, str, str]] = [
    ("containerOf", "Forum", "Post", "forum_containerOf_post"),
    ("commentHasCreator", "Comment", "Person", "comment_hasCreator_person"),
    ("postHasCreator", "Post", "Person", "post_hasCreator_person"),
    ("hasInterest", "Person", "Tag", "person_hasInterest_tag"),
    ("hasMember", "Forum", "Person", "forum_hasMember_person"),
    ("hasModerator", "Forum", "Person", "forum_hasModerator_person"),
    ("commentHasTag", "Comment", "Tag", "comment_hasTag_tag"),
    ("forumHasTag", "Forum", "Tag", "forum_hasTag_tag"),
    ("postHasTag", "Post", "Tag", "post_hasTag_tag"),
    ("hasType", "Tag", "Tagclass", "tag_hasType_tagclass"),
    ("commentIsLocatedIn", "Comment", "Place", "comment_isLocatedIn_place"),
    ("organisationIsLocatedIn", "Organisation", "Place", "organisation_isLocatedIn_place"),
    ("personIsLocatedIn", "Person", "Place", "person_isLocatedIn_place"),
    ("postIsLocatedIn", "Post", "Place", "post_isLocatedIn_place"),
    ("isPartOf", "Place", "Place", "place_isPartOf_place"),
    ("isSubclassOf", "Tagclass", "Tagclass", "tagclass_isSubclassOf_tagclass"),
    ("knows", "Person", "Person", "person_knows_person"),
    ("likeComment", "Person", "Comment", "person_likes_comment"),
    ("likePost", "Person", "Post", "person_likes_post"),
    ("replyOfComment", "Comment", "Comment", "comment_replyOf_comment"),
    ("replyOfPost", "Comment", "Post", "comment_replyOf_post"),
    ("studyAt", "Person", "Organisation", "person_studyAt_organisation"),
    ("workAt", "Person", "Organisation", "person_workAt_organisation"),
]


def _edge_path(stem: str) -> Path:
    """Find the CSV file for a given edge stem."""
    p = CSV_ROOT / "dynamic" / f"{stem}_0_0.csv"
    if p.exists():
        return p
    p = CSV_ROOT / "static" / f"{stem}_0_0.csv"
    if p.exists():
        return p
    raise FileNotFoundError(f"Edge CSV not found for stem '{stem}'")


def _read_csv(path: Path) -> pl.DataFrame:
    """Read a pipe-delimited CSV with automatic header detection."""
    return pl.read_csv(
        path,
        separator="|",
        try_parse_dates=True,
        infer_schema_length=1000,
    )


def _normalise_column_names(df: pl.DataFrame) -> pl.DataFrame:
    """Lowercase and replace dots with underscores in column names."""
    mapping = {}
    for col in df.columns:
        new = col.lower().replace(".", "_")
        while new in mapping.values():
            new = new + "_"
        mapping[col] = new
    return df.rename(mapping)


def build_nodes() -> pl.DataFrame:
    """Read all node CSVs and return a unified nodes DataFrame with integer IDs.

    Each row gets a ``type`` column set to the node label, and boolean
    ``label__<Label>`` columns for GFQL Cypher ``:Label`` syntax. IDs are kept
    as native ``Int64`` for fast integer joins. GFQL filters by ``:Label``
    before joining, so IDs only need to be unique within a node type.
    """
    parts: list[pl.DataFrame] = []
    for label, path in NODE_CSVS.items():
        if not path.exists():
            print(f"  [SKIP] {label} – file not found: {path}")
            continue
        df = _read_csv(path)
        df = _normalise_column_names(df)

        # Cast id to Int64 for fast integer joins
        df = df.with_columns(pl.col("id").cast(pl.Int64).alias("id"))

        # Rename any existing 'type' column to avoid conflict with our node type
        if "type" in df.columns:
            df = df.rename({"type": "original_type"})

        # Node type column (the node label)
        df = df.with_columns(pl.lit(label).alias("type"))
        # Boolean label__<Label> column for GFQL Cypher :Label matching
        df = df.with_columns(pl.lit(True).alias(f"label__{label}"))

        parts.append(df)
        print(f"  [OK]   {label}: {len(df)} rows")

    nodes = pl.concat(parts, how="diagonal")

    # Fill missing label__ columns with False
    for label in NODE_CSVS:
        col = f"label__{label}"
        if col not in nodes.columns:
            nodes = nodes.with_columns(pl.lit(False).alias(col))
        else:
            nodes = nodes.with_columns(pl.col(col).fill_null(False))

    print(f"\n  Total nodes: {len(nodes)}")
    return nodes


def build_edges() -> pl.DataFrame:
    """Read all edge CSVs and return a unified edges DataFrame with integer src/dst.

    Columns are normalised to ``src``, ``dst`` (both ``Int64``), plus extra
    properties. A ``type`` string column carries the relationship name; GFQL
    Cypher ``[:REL_TYPE]`` filters on this ``type`` column directly.
    """
    parts: list[pl.DataFrame] = []
    for rel_name, src_label, dst_label, stem in EDGE_SPECS:
        path = _edge_path(stem)
        if not path.exists():
            print(f"  [SKIP] {rel_name} – file not found: {path}")
            continue
        df = _read_csv(path)
        df = _normalise_column_names(df)

        # Rename first two columns to src/dst
        old_cols = df.columns
        new_cols = list(old_cols)
        new_cols[0] = "src"
        new_cols[1] = "dst"
        df = df.rename(dict(zip(old_cols, new_cols)))

        # Cast src/dst to Int64 for fast integer joins
        df = df.with_columns(pl.col("src").cast(pl.Int64).alias("src"))
        df = df.with_columns(pl.col("dst").cast(pl.Int64).alias("dst"))

        # Relationship type column. GFQL Cypher ``[:REL_TYPE]`` filters this
        # ``type`` string column (discriminator_key="type"), so no boolean
        # ``rel__*`` columns are needed.
        df = df.with_columns(pl.lit(rel_name).alias("type"))

        parts.append(df)
        print(f"  [OK]   {rel_name} ({src_label}->{dst_label}): {len(df)} rows")

    edges = pl.concat(parts, how="diagonal")

    print(f"\n  Total edges: {len(edges)}")
    return edges


def write_outputs(nodes: pl.DataFrame, edges: pl.DataFrame) -> None:
    """Write the unified DataFrames as Parquet for fast reloading."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    nodes_path = OUT_DIR / "nodes.parquet"
    edges_path = OUT_DIR / "edges.parquet"
    nodes.write_parquet(str(nodes_path))
    edges.write_parquet(str(edges_path))
    print(f"\n  Nodes written: {nodes_path} ({nodes.estimated_size('mb'):.1f} MB)")
    print(f"  Edges written: {edges_path} ({edges.estimated_size('mb'):.1f} MB)")


def load_built_graph() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load previously built node/edge DataFrames from Parquet."""
    nodes = pl.read_parquet(str(OUT_DIR / "nodes.parquet"))
    edges = pl.read_parquet(str(OUT_DIR / "edges.parquet"))
    return nodes, edges


def main() -> None:
    print("Building graph from LDBC SNB SF1 CSV data ...\n")
    print("─ Nodes ──────────────────────────────────────")
    nodes = build_nodes()
    print(f"\n{'─ Edges ' + '─' * 50}")
    edges = build_edges()
    print(f"\n{'─ Write ' + '─' * 48}")
    write_outputs(nodes, edges)

    print(f"\n{'─ Summary ' + '─' * 45}")
    print(f"  Unique node types: {nodes['type'].n_unique()}")
    print(f"  Unique edge types: {edges['type'].n_unique()}")
    print(f"  id dtype: {nodes.schema['id']}, src dtype: {edges.schema['src']}, dst dtype: {edges.schema['dst']}")
    print("\nDone. Graph data ready for PyGraphistry + Polars.")


if __name__ == "__main__":
    main()