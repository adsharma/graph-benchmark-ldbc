"""Read-only count and index checks for this local benchmark run."""

import importlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODES = {
    "Comment": 2052169,
    "Forum": 90492,
    "Organisation": 7955,
    "Person": 9892,
    "Place": 1460,
    "Post": 1003605,
    "Tag": 16080,
    "Tagclass": 71,
}
EDGES = {
    "commentHasCreator": 2052169,
    "commentHasTag": 2698393,
    "commentIsLocatedIn": 2052169,
    "containerOf": 1003605,
    "forumHasTag": 309766,
    "hasInterest": 229166,
    "hasMember": 1611869,
    "hasModerator": 90492,
    "hasType": 16080,
    "isPartOf": 1454,
    "isSubclassOf": 70,
    "knows": 180623,
    "likeComment": 1438418,
    "likePost": 751677,
    "organisationIsLocatedIn": 7955,
    "personIsLocatedIn": 9892,
    "postHasCreator": 1003605,
    "postHasTag": 713258,
    "postIsLocatedIn": 1003605,
    "replyOfComment": 1040749,
    "replyOfPost": 1011420,
    "studyAt": 7949,
    "workAt": 21654,
}
EXPECTED_ART = {
    "Place_name_art",
    "Tag_name_art",
    "Person_firstName_art",
    "Person_lastName_art",
    "Person_birthday_art",
    "Comment_length_art",
}


def embedded(engine):
    module = importlib.import_module(engine)
    directory, extension = (
        ("ladybugdb", "lbdb") if engine == "ladybug" else ("kuzu", "kuzu")
    )
    path = ROOT / directory / f"ldbc_snb_sf1.{extension}"
    assert path.exists(), f"Missing database: {path}"
    db = module.Database(str(path), read_only=True)
    conn = module.Connection(db)

    def rows(query):
        result = conn.execute(query)
        try:
            return result.get_as_pl().to_dicts()
        finally:
            result.close()

    try:
        nodes = {
            name: rows(f"MATCH (n:{name}) RETURN count(*) AS count")[0]["count"]
            for name in NODES
        }
        edges = {
            name: rows(f"MATCH ()-[r:{name}]->() RETURN count(*) AS count")[0]["count"]
            for name in EDGES
        }
        tables = rows("CALL show_tables() RETURN *")
        assert len(tables) == 31, tables
        primary_keys = {
            name: rows(f"CALL table_info('{name}') RETURN *") for name in NODES
        }
        for name, columns in primary_keys.items():
            assert any(
                c.get("name") == "ID" and c.get("primary key") is True for c in columns
            ), (name, columns)
        indexes = rows("CALL show_indexes() RETURN *") if engine == "ladybug" else []
        if engine == "ladybug":
            assert EXPECTED_ART.issubset(
                {str(value) for row in indexes for value in row.values()}
            ), indexes
        return (
            nodes,
            edges,
            {"secondary_indexes": indexes, "primary_keys": primary_keys},
        )
    finally:
        conn.close()
        db.close()


def lance_graph():
    import lance

    mappings = dict(
        re.findall(
            r"COPY (\w+) FROM '\.\./csv/(.*?)'",
            (ROOT / "ladybugdb/etl/copy.cypher").read_text(),
        )
    )
    nodes, edges, indexes = {}, {}, {}
    for name in NODES | EDGES:
        dataset_name = (
            name
            if name in NODES
            else re.sub(r"_\d+_\d+$", "", Path(mappings[name]).stem)
        )
        dataset = lance.dataset(
            str(ROOT / "lance_graph/graph_lance" / f"{dataset_name}.lance")
        )
        (nodes if name in NODES else edges)[name] = dataset.count_rows()
        if name in NODES:
            indexes[name] = dataset.list_indices()
            assert any(
                i["name"] == f"{name}_id_btree" and i["fields"] == ["id"]
                for i in indexes[name]
            ), indexes[name]
    return nodes, edges, indexes


def neo4j():
    from dotenv import load_dotenv

    from neo4j import GraphDatabase

    load_dotenv(ROOT / "neo4j/.env")
    with (
        GraphDatabase.driver(
            os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        ) as driver,
        driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session,
    ):
        session.run("CALL db.awaitIndexes(300)").consume()
        nodes = {
            name: session.run(f"MATCH (n:{name}) RETURN count(*) AS count").single()[
                "count"
            ]
            for name in NODES
        }
        edges = {
            name: session.run(
                f"MATCH ()-[r:{name}]->() RETURN count(*) AS count"
            ).single()["count"]
            for name in EDGES
        }
        assert session.run("MATCH (n) RETURN count(*) AS count").single()[
            "count"
        ] == sum(NODES.values())
        assert session.run("MATCH ()-[r]->() RETURN count(*) AS count").single()[
            "count"
        ] == sum(EDGES.values())
        indexes = session.run(
            "SHOW INDEXES YIELD name, state, type, labelsOrTypes, properties RETURN *"
        ).data()
        assert all(i["state"] == "ONLINE" for i in indexes), indexes
        for name in NODES:
            assert any(
                i["labelsOrTypes"] == [name] and i["properties"] == ["ID"]
                for i in indexes
            ), name
        return nodes, edges, indexes


if __name__ == "__main__":
    engine = sys.argv[1]
    nodes, edges, indexes = (
        embedded(engine)
        if engine in {"ladybug", "kuzu"}
        else {"lance_graph": lance_graph, "neo4j": neo4j}[engine]()
    )
    assert nodes == NODES, {
        k: (NODES[k], nodes.get(k)) for k in NODES if NODES[k] != nodes.get(k)
    }
    assert edges == EDGES, {
        k: (EDGES[k], edges.get(k)) for k in EDGES if EDGES[k] != edges.get(k)
    }
    print(
        json.dumps(
            {
                "engine": engine,
                "validated": True,
                "nodes": nodes,
                "relationships": edges,
                "total_nodes": sum(nodes.values()),
                "total_relationships": sum(edges.values()),
                "indexes": indexes,
            },
            indent=2,
            default=str,
        )
    )
