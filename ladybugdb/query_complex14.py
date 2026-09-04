"""Official LDBC SNB Interactive v1 query suite (complex Q1-Q14) for Ladybug.

Faithful port of::

    /home/ubuntu/src/ldbc_snb_interactive_v1_impls/cypher/queries/
        interactive-complex-{1..14}.cypher

to the Ladybug schema of ``ldbc_snb_sf1.lbdb`` (from ``:schema`` in
``~/bin/lbug -r ldbc*.lbdb``). Structure mirrors ``query.py``.

----------------------------------------------------------------------
Schema mapping (official openCypher label -> Ladybug label)
----------------------------------------------------------------------
- ``Person.id`` -> ``Person.ID``; ``KNOWS`` -> ``knows`` (stored directed,
  hence traversed undirected ``-[:knows]-`` everywhere).
- ``Message`` (Post|Comment superclass) -> separate ``Post``/``Comment``
  branches combined with ``UNION ALL``.
- ``HAS_CREATOR`` -> ``postHasCreator`` / ``commentHasCreator``.
- ``REPLY_OF`` -> ``replyOfPost`` / ``replyOfComment``.
- ``LIKES`` (with ``like.creationDate``) -> ``likePost`` / ``likeComment``
  (both carry ``creationDate``).
- ``HAS_TAG`` -> ``postHasTag`` / ``commentHasTag``; ``HAS_TYPE`` -> ``hasType``;
  ``IS_SUBCLASS_OF`` -> ``isSubclassOf``.
- ``IS_LOCATED_IN`` -> ``personIsLocatedIn`` / ``postIsLocatedIn`` /
  ``commentIsLocatedIn`` / ``organisationIsLocatedIn``.
- ``IS_PART_OF`` -> ``isPartOf``; ``STUDY_AT`` (``classYear``) -> ``studyAt``;
  ``WORK_AT`` (``workFrom`` year) -> ``workAt``; ``HAS_MEMBER`` (``joinDate``)
  -> ``hasMember``; ``CONTAINER_OF`` (Forum->Post) -> ``containerOf``;
  ``HAS_INTEREST`` -> ``hasInterest``.
- Official ``City``/``Country`` (resp. ``University``/``Company``) node labels
  -> Ladybug ``Place.type`` (``city``/``country``), ``Organisation.type``
  (``university``/``company``) discriminators.
- Official epoch-millis date params -> ``"YYYY-MM-DD HH:MM:SS"`` strings bound
  via ``TIMESTAMP($param)``.
- Unavailable in this snapshot (omitted, noted per query): ``Person.email``,
  ``Person.speaks`` (Q1); ``horoscopeSign`` is expressed officially as a
  birthday month/day zodiac predicate on ``$month`` (Q10).

----------------------------------------------------------------------
PARAMETERS (highlighted)
----------------------------------------------------------------------
Every query is parameterized with ``$name`` placeholders matching the official
query's parameter names. Each ``run_queryN`` lists its parameters in its
docstring, binds them from the ``PARAMS`` table below (overridable via keyword
arguments), and prints the bound values before executing, e.g.::

    uv run query_complex14.py "1,2"        # run Q1 and Q2 with defaults
    uv run query_complex14.py              # run all 14 queries

    # override from Python:
    #   run_query1(conn, personId=2783, firstName="Yang")

Official example person IDs (e.g. 4398046511333, 6597069766734) do NOT exist
in this SF1 snapshot (only 143 does), so person defaults use verified members
(Samir = highest degree; Rafael = his direct friend; 143 for Q8). Tag, country,
tag-class and date-window defaults follow the official examples wherever they
yield results here.

================= ============================================================
Query           Parameters (all have working defaults in PARAMS)
================= ============================================================
Q1              $personId, $firstName
Q2              $personId, $maxDate
Q3              $personId, $countryXName, $countryYName, $startDate, $endDate
                  (+ optional $durationDays to derive $endDate)
Q4              $personId, $startDate, $endDate
Q5              $personId, $minDate
Q6              $personId, $tagName
Q7              $personId
Q8              $personId
Q9              $personId, $maxDate
Q10             $personId, $month
Q11             $personId, $countryName, $workFromYear
Q12             $personId, $tagClassName
Q13             $person1Id, $person2Id  (-1 when disconnected)
Q14             $person1Id, $person2Id
================= ============================================================
"""

import sys
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import ladybug as lb
from ladybug import Connection

# ---------------------------------------------------------------------------
# Default parameter values. Persons verified in SF1 via lbug; tag/country/
# class/date defaults follow the official query examples where non-empty.
# ---------------------------------------------------------------------------
SAMIR = 2199023262543  # Samir Al-Fayez: highest-degree person (814 friends)
RAFAEL = 2783  # Rafael Alonso, a direct friend of Samir

PARAMS: dict[int, dict[str, Any]] = {
    # official ex.: 4398046511333 / "Jose" (person missing here; 85 Joses near Samir)
    1: {"personId": SAMIR, "firstName": "Jose"},
    # official ex.: 10995116278009 (missing here), maxDate 1287230400000 = 2010-10-16 12:00:00
    2: {"personId": SAMIR, "maxDate": "2010-10-16 12:00:00"},
    # official ex.: 6597069766734 (missing here); Angola/Colombia kept, June-2010 window kept
    3: {
        "personId": SAMIR,
        "countryXName": "Angola",
        "countryYName": "Colombia",
        "startDate": "2010-06-01 12:00:00",
        "endDate": "2010-06-29 12:00:00",
        "durationDays": None,
    },
    # official ex.: 4398046511333 (missing here); window 1275350400000..1277856000000
    4: {"personId": SAMIR, "startDate": "2010-06-01 00:00:00", "endDate": "2010-06-30 00:00:00"},
    # official ex.: 6597069766734 (missing here); minDate 1288612800000 = 2010-11-01 12:00:00
    5: {"personId": SAMIR, "minDate": "2010-11-01 12:00:00"},
    # official ex.: 4398046511333 (missing here) / "Carl_Gustaf_Emil_Mannerheim" (kept)
    6: {"personId": SAMIR, "tagName": "Carl_Gustaf_Emil_Mannerheim"},
    # official ex.: 4398046511268 (missing here)
    7: {"personId": SAMIR},
    # official ex.: 143 (exists: Maria Alkaios)
    8: {"personId": 143},
    # official ex.: 4398046511268 (missing here), maxDate 1289908800000 = 2010-11-16 12:00:00
    9: {"personId": SAMIR, "maxDate": "2010-11-16 12:00:00"},
    # official ex.: 4398046511333 (missing here), month 5 (kept)
    10: {"personId": SAMIR, "month": 5},
    # official ex.: 10995116277918 (missing here); Hungary / 2011 kept
    11: {"personId": SAMIR, "countryName": "Hungary", "workFromYear": 2011},
    # official ex.: 10995116278009 (missing here); "Monarch" kept
    12: {"personId": SAMIR, "tagClassName": "Monarch"},
    # official ex.: 8796093022390 / 8796093022357 (both missing here)
    13: {"person1Id": SAMIR, "person2Id": RAFAEL},
    # official ex.: 8796093022357 / 8796093022390 (both missing here)
    14: {"person1Id": SAMIR, "person2Id": RAFAEL},
}


def _execute(conn: Connection, idx: int, query: str, params: dict[str, Any] | None = None):
    bound = dict(params or {})
    # without a parameter the engine doesn't cache the plan (cf. query.py);
    # keep one dummy entry so plan caching stays enabled.
    bound.setdefault("dummy", 0)
    print(f"\nQuery {idx}  parameters: " + ", ".join(f"${k}={v!r}" for k, v in bound.items() if k != "dummy"))
    print(f"Query {idx}:\n{query}")
    response = conn.execute(query, bound)
    result = response.get_as_pl()  # type: ignore
    print(result)
    response.close()
    return result


def _get(conn: Connection, query: str, params: dict[str, Any]):
    """Lightweight fetch (list of rows) for internal helpers (Q3/Q7/Q14)."""
    response = conn.execute(query, params)
    try:
        return response.get_all()
    finally:
        response.close()


def _execute_union_top(
    conn: Connection,
    idx: int,
    query: str,
    params: dict[str, Any],
    sort_by: list[str],
    descending: list[bool],
    limit: int,
):
    """UNION ALL branch-merge with client-side ORDER BY + LIMIT.

    NOTE: Ladybug currently ignores a trailing ORDER BY/LIMIT over a
    UNION ALL (it returns the unsorted, un-truncated union), so the union
    is fetched whole and the top-N is selected here with polars. The
    printed Cypher shows the intended ordering as a comment.
    """
    import polars as pl

    bound = dict(params or {})
    bound.setdefault("dummy", 0)
    print(f"\nQuery {idx}  parameters: " + ", ".join(f"${k}={v!r}" for k, v in bound.items() if k != "dummy"))
    print(f"Query {idx}:\n{query}")
    response = conn.execute(query, bound)
    df = response.get_as_pl()
    response.close()
    assert isinstance(df, pl.DataFrame)
    top = df.sort(sort_by, descending=descending).head(limit)
    print(top)
    return top


# ---------------------------------------------------------------------------
# Q1. Transitive friends with certain name (official: complex-1).
# ---------------------------------------------------------------------------
def run_query1(conn: Connection, personId: int | None = None, firstName: str | None = None):
    """Q1. Transitive (1-3 hop) friends of $personId named $firstName.

    Parameters:
        $personId  -- start Person ID.
        $firstName -- given first name to match.
    Ordered by distance ASC, last name ASC, friend ID ASC. LIMIT 20.
    Includes home city, universities [{name, classYear, city}] and companies
    [{name, workFrom, country}] as structs.

    Diffs vs official: ``friendEmails``/``friendLanguages`` omitted (no
    ``email``/``speaks`` properties in this snapshot); unmatched uni/company
    collect as a null-field struct instead of official ``[null]`` (Ladybug
    lists must be homogeneous); company place may be a city, not a Country.
    """
    p = PARAMS[1].copy()
    if personId is not None:
        p["personId"] = personId
    if firstName is not None:
        p["firstName"] = firstName
    query = """
        MATCH (start:Person {ID: $personId})-[e:knows* SHORTEST 1..3]-(friend:Person)
        WHERE friend.firstName = $firstName AND friend.ID <> $personId
        WITH friend, LENGTH(e) AS distance
        ORDER BY distance ASC, friend.lastName ASC, friend.ID ASC
        LIMIT 20
        MATCH (friend)-[:personIsLocatedIn]->(friendCity:Place)
        OPTIONAL MATCH (friend)-[studyAt:studyAt]->(uni:Organisation)
                           -[:organisationIsLocatedIn]->(uniCity:Place)
        WITH friend, friendCity, distance,
             COLLECT(DISTINCT {universityName: uni.name, classYear: studyAt.classYear,
                               cityName: uniCity.name}) AS unis
        OPTIONAL MATCH (friend)-[workAt:workAt]->(company:Organisation)
                           -[:organisationIsLocatedIn]->(companyPlace:Place)
        WITH friend, friendCity, distance, unis,
             COLLECT(DISTINCT {companyName: company.name, workFrom: workAt.workFrom,
                               countryName: companyPlace.name}) AS companies
        RETURN friend.ID AS friendId, friend.lastName AS friendLastName,
               distance AS distanceFromPerson, friend.birthday AS friendBirthday,
               friend.creationDate AS friendCreationDate, friend.gender AS friendGender,
               friend.browserUsed AS friendBrowserUsed, friend.locationIP AS friendLocationIp,
               friendCity.name AS friendCityName, unis AS friendUniversities,
               companies AS friendCompanies
        ORDER BY distanceFromPerson ASC, friendLastName ASC, friendId ASC
        LIMIT 20;
    """
    return _execute(conn, 1, query, p)


# ---------------------------------------------------------------------------
# Q2. Recent messages by your friends (official: complex-2).
# ---------------------------------------------------------------------------
def run_query2(conn: Connection, personId: int | None = None, maxDate: str | None = None):
    """Q2. Recent posts+comments of friends of $personId, created <= $maxDate.

    Parameters:
        $personId -- start Person ID.
        $maxDate  -- upper bound (inclusive) "YYYY-MM-DD HH:MM:SS" timestamp
                     (official: epoch millis).
    Ordered by creation date DESC, message ID ASC. LIMIT 20.
    """
    p = PARAMS[2].copy()
    if personId is not None:
        p["personId"] = personId
    if maxDate is not None:
        p["maxDate"] = maxDate
    query = """
        // friends' posts created <= $maxDate
        MATCH (start:Person {ID: $personId})-[:knows]-(friend:Person),
              (post:Post)-[:postHasCreator]->(friend)
        WHERE post.creationDate <= TIMESTAMP($maxDate)
        RETURN friend.ID AS personId, friend.firstName AS personFirstName,
               friend.lastName AS personLastName, post.ID AS postOrCommentId,
               COALESCE(post.content, post.imageFile) AS postOrCommentContent,
               post.creationDate AS postOrCommentCreationDate
        UNION ALL
        // friends' comments created <= $maxDate
        MATCH (start:Person {ID: $personId})-[:knows]-(friend:Person),
              (c:Comment)-[:commentHasCreator]->(friend)
        WHERE c.creationDate <= TIMESTAMP($maxDate)
        RETURN friend.ID AS personId, friend.firstName AS personFirstName,
               friend.lastName AS personLastName, c.ID AS postOrCommentId,
               c.content AS postOrCommentContent,
               c.creationDate AS postOrCommentCreationDate;
        // intended: ORDER BY postOrCommentCreationDate DESC, postOrCommentId ASC LIMIT 20
        // (applied client-side, see _execute_union_top)
    """
    return _execute_union_top(
        conn, 2, query, p,
        sort_by=["postOrCommentCreationDate", "postOrCommentId"],
        descending=[True, False], limit=20,
    )


# ---------------------------------------------------------------------------
# Q3. Friends/FoF that have been to given countries (official: complex-3).
# ---------------------------------------------------------------------------
def run_query3(
    conn: Connection,
    personId: int | None = None,
    countryXName: str | None = None,
    countryYName: str | None = None,
    startDate: str | None = None,
    endDate: str | None = None,
    durationDays: int | None = None,
):
    """Q3. Friends/FoF of $personId with messages in $countryXName AND $countryYName.

    Parameters:
        $personId     -- start Person ID (1-2 hop neighbourhood, excl. self and
                         friends located in either country, as in official).
        $countryXName -- first country (Place.name).
        $countryYName -- second country (Place.name).
        $startDate    -- window start "YYYY-MM-DD HH:MM:SS" (official: epoch
                         millis), inclusive.
        $endDate      -- window end, exclusive (official: ``endDate > t``).
        $durationDays -- optional convenience: overrides $endDate with
                         ``$startDate + durationDays`` (spec wording).
    Posts AND comments located directly in either country count (official
    ``(message)-[:IS_LOCATED_IN]->(country)``). Ordered by xCount+yCount DESC,
    friend ID ASC. LIMIT 20.
    """
    p = PARAMS[3].copy()
    if personId is not None:
        p["personId"] = personId
    if countryXName is not None:
        p["countryXName"] = countryXName
    if countryYName is not None:
        p["countryYName"] = countryYName
    if startDate is not None:
        p["startDate"] = startDate
    if endDate is not None:
        p["endDate"] = endDate
        p["durationDays"] = None
    if durationDays is not None:
        p["durationDays"] = durationDays
    if p.get("durationDays"):
        computed = (datetime.strptime(p["startDate"], "%Y-%m-%d %H:%M:%S") + timedelta(days=p["durationDays"])).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        print(f"[Q3] window: startDate={p['startDate']} + {p['durationDays']} days -> endDate={computed}")
        p["endDate"] = computed
    bound = {k: p[k] for k in ("personId", "countryXName", "countryYName", "startDate", "endDate")}
    # NOTE: a single Cypher statement starting from the ~8k friends/FoF with
    # OPTIONAL activity matches exhausts the buffer pool, so the spec is
    # executed inverted: anchor on the selective (country, window) side,
    # intersect active creators with the FoF set in Python, then count.
    # Same parameters, same semantics.
    print(
        f"\nQuery 3  parameters: $personId={bound['personId']!r}, "
        f"$countryXName={bound['countryXName']!r}, $countryYName={bound['countryYName']!r}, "
        f"$startDate={bound['startDate']!r}, $endDate={bound['endDate']!r}"
    )
    import polars as pl

    fof_rows = _get(
        conn,
        "MATCH (start:Person {ID: $personId})-[:knows*1..2]-(friend:Person)"
        " WHERE friend.ID <> $personId RETURN DISTINCT friend.ID AS fid;",
        {"personId": bound["personId"], "dummy": 0},
    )
    fof = {r[0] for r in fof_rows}
    print(f"[Q3] friends + friends-of-friends: {len(fof)}")

    # active creators per country (posts + comments located in the country)
    active_x: set = set()
    active_y: set = set()
    for country, slot in [(bound["countryXName"], active_x), (bound["countryYName"], active_y)]:
        for loc_rel, creator_rel in [
            ("postIsLocatedIn", "postHasCreator"),
            ("commentIsLocatedIn", "commentHasCreator"),
        ]:
            msg_label = "Post" if loc_rel.startswith("post") else "Comment"
            q = (
                f"MATCH (pl:Place {{name: $country}})<-[:{loc_rel}]-(m:{msg_label})"
                f"-[:{creator_rel}]->(f:Person)"
                " WHERE m.creationDate >= TIMESTAMP($startDate)"
                " AND m.creationDate < TIMESTAMP($endDate)"
                " RETURN DISTINCT f.ID AS fid;"
            )
            for row in _get(
                conn,
                q,
                {"country": country, "startDate": bound["startDate"], "endDate": bound["endDate"], "dummy": 0},
            ):
                slot.add(row[0])

    qualifiers = sorted(fof & active_x & active_y)
    print(f"[Q3] active in {bound['countryXName']}: {len(active_x & fof)}, "
          f"in {bound['countryYName']}: {len(active_y & fof)}, in both: {len(qualifiers)}")

    # official home-country exclusion: drop friends located in either country
    # (directly, or via home place -[:isPartOf]-> country)
    home_rows: list = []
    for i in range(0, len(qualifiers), 200):
        home_rows += _get(
            conn,
            "MATCH (f:Person) WHERE f.ID IN $ids "
            "OPTIONAL MATCH (f)-[:personIsLocatedIn]->(home:Place) "
            "OPTIONAL MATCH (home)-[:isPartOf]->(parent:Place) "
            "RETURN f.ID AS fid, home.name AS home, parent.name AS parent;",
            {"ids": qualifiers[i : i + 200], "dummy": 0},
        )
    countries = {bound["countryXName"], bound["countryYName"]}
    qualifiers = sorted(
        qid for qid, home, parent in home_rows if home not in countries and parent not in countries
    )
    print(f"[Q3] after home-country exclusion: {len(qualifiers)}")
    if not qualifiers:
        print("Query 3: no qualifying friends.")
        return pl.DataFrame()

    # per-kind counts via message-anchored grouped queries (no big IN-lists),
    # filtered to qualifiers client-side
    counts: dict[int, dict[str, int]] = {qid: {"xCount": 0, "yCount": 0} for qid in qualifiers}
    qset = set(qualifiers)
    for loc_rel, creator_rel, country, slot in [
        ("postIsLocatedIn", "postHasCreator", bound["countryXName"], "xCount"),
        ("commentIsLocatedIn", "commentHasCreator", bound["countryXName"], "xCount"),
        ("postIsLocatedIn", "postHasCreator", bound["countryYName"], "yCount"),
        ("commentIsLocatedIn", "commentHasCreator", bound["countryYName"], "yCount"),
    ]:
        msg_label = "Post" if loc_rel.startswith("post") else "Comment"
        cq = (
            f"MATCH (pl:Place {{name: $country}})<-[:{loc_rel}]-(m:{msg_label})"
            f"-[:{creator_rel}]->(f:Person)"
            " WHERE m.creationDate >= TIMESTAMP($startDate)"
            " AND m.creationDate < TIMESTAMP($endDate)"
            " RETURN f.ID AS personId, COUNT(m) AS n;"
        )
        for row in _get(
            conn, cq,
            {"country": country, "startDate": bound["startDate"], "endDate": bound["endDate"], "dummy": 0},
        ):
            if row[0] in qset:
                counts[row[0]][slot] += row[1]
    print("Query 3: (official: xCount/yCount per friend; ORDER BY xCount+yCount DESC, friendId ASC LIMIT 20)")
    name_rows: list = []
    for i in range(0, len(qualifiers), 200):
        name_rows += _get(
            conn,
            "MATCH (f:Person) WHERE f.ID IN $ids RETURN f.ID AS personId, f.firstName AS firstName,"
            " f.lastName AS lastName;",
            {"ids": qualifiers[i : i + 200], "dummy": 0},
        )
    names = {r[0]: (r[1], r[2]) for r in name_rows}
    df = pl.DataFrame(
        [
            {
                "friendId": qid,
                "friendFirstName": names[qid][0],
                "friendLastName": names[qid][1],
                "xCount": counts[qid]["xCount"],
                "yCount": counts[qid]["yCount"],
                "xyCount": counts[qid]["xCount"] + counts[qid]["yCount"],
            }
            for qid in qualifiers
        ]
    ).sort(["xyCount", "friendId"], descending=[True, False]).head(20)
    print(df)
    return df


# ---------------------------------------------------------------------------
# Q4. New topics (official: complex-4).
# ---------------------------------------------------------------------------
def run_query4(
    conn: Connection,
    personId: int | None = None,
    startDate: str | None = None,
    endDate: str | None = None,
):
    """Q4. Tags used on friends' posts only within [$startDate, $endDate).

    Parameters:
        $personId  -- start Person ID (only direct friends' posts).
        $startDate -- interval start (official: epoch millis), inclusive.
        $endDate   -- interval end, exclusive.
    A tag qualifies if it has posts in the window AND zero posts before the
    window (official ``postCount > 0 AND inValidPostCount = 0``).
    Ordered by post count DESC, tag name ASC. LIMIT 10.
    """
    p = PARAMS[4].copy()
    if personId is not None:
        p["personId"] = personId
    if startDate is not None:
        p["startDate"] = startDate
    if endDate is not None:
        p["endDate"] = endDate
    query = """
        MATCH (start:Person {ID: $personId})-[:knows]-(friend:Person),
              (friend)<-[:postHasCreator]-(post:Post)-[:postHasTag]->(tag:Tag)
        WITH DISTINCT tag, post
        WITH tag,
             SUM(CASE WHEN post.creationDate >= TIMESTAMP($startDate)
                       AND post.creationDate < TIMESTAMP($endDate)
                      THEN 1 ELSE 0 END) AS postCount,
             SUM(CASE WHEN post.creationDate < TIMESTAMP($startDate)
                      THEN 1 ELSE 0 END) AS inValidPostCount
        WHERE postCount > 0 AND inValidPostCount = 0
        RETURN tag.name AS tagName, postCount
        ORDER BY postCount DESC, tagName ASC
        LIMIT 10;
    """
    return _execute(conn, 4, query, p)


# ---------------------------------------------------------------------------
# Q5. New groups (official: complex-5).
# ---------------------------------------------------------------------------
def run_query5(conn: Connection, personId: int | None = None, minDate: str | None = None):
    """Q5. Forums friends/FoF joined after $minDate, ranked by their posts.

    Parameters:
        $personId -- start Person ID (1-2 hop neighbourhood, excl. self).
        $minDate  -- lower bound (exclusive) on hasMember.joinDate
                     (official: epoch millis).
    Ordered by post count DESC, forum ID ASC. LIMIT 20. Forums with zero
    posts by these members are kept (official OPTIONAL MATCH).
    """
    p = PARAMS[5].copy()
    if personId is not None:
        p["personId"] = personId
    if minDate is not None:
        p["minDate"] = minDate
    query = """
        MATCH (start:Person {ID: $personId})-[:knows*1..2]-(friend:Person)
        WHERE friend.ID <> $personId
        WITH DISTINCT friend
        MATCH (forum:Forum)-[membership:hasMember]->(friend)
        WHERE membership.joinDate > TIMESTAMP($minDate)
        WITH forum, COLLECT(friend) AS friends
        OPTIONAL MATCH (author:Person)<-[:postHasCreator]-(post:Post)<-[:containerOf]-(forum)
            WHERE author IN friends
        WITH forum, COUNT(post) AS postCount
        RETURN forum.title AS forumName, postCount
        ORDER BY postCount DESC, forum.ID ASC
        LIMIT 20;
    """
    return _execute(conn, 5, query, p)


# ---------------------------------------------------------------------------
# Q6. Tag co-occurrence (official: complex-6).
# ---------------------------------------------------------------------------
def run_query6(conn: Connection, personId: int | None = None, tagName: str | None = None):
    """Q6. Tags co-occurring with $tagName on friends/FoF posts.

    Parameters:
        $personId -- start Person ID (1-2 hop neighbourhood, excl. self).
        $tagName  -- anchor Tag.name.
    Top 10 other tags ordered by co-occurring post count DESC, tag name ASC.
    """
    p = PARAMS[6].copy()
    if personId is not None:
        p["personId"] = personId
    if tagName is not None:
        p["tagName"] = tagName
    query = """
        MATCH (given:Tag {name: $tagName})
        WITH given.ID AS knownTagId
        MATCH (start:Person {ID: $personId})-[:knows*1..2]-(friend:Person)
        WHERE friend.ID <> $personId
        WITH knownTagId, COLLECT(DISTINCT friend.ID) AS friendIds
        UNWIND friendIds AS fid
        MATCH (f:Person {ID: fid})<-[:postHasCreator]-(post:Post),
              (post)-[:postHasTag]->(t:Tag {ID: knownTagId}),
              (post)-[:postHasTag]->(tag:Tag)
        WHERE NOT t = tag
        WITH tag.name AS tagName, COUNT(post) AS postCount
        RETURN tagName, postCount
        ORDER BY postCount DESC, tagName ASC
        LIMIT 10;
    """
    return _execute(conn, 6, query, p)


# ---------------------------------------------------------------------------
# Q7. Recent likers (official: complex-7).
# ---------------------------------------------------------------------------
def run_query7(conn: Connection, personId: int | None = None):
    """Q7. Most recent likers of $personId's posts+comments (one row per liker).

    Parameters:
        $personId -- owner Person ID.
    Per liker only the latest like is kept (official ``head(collect(...))``).
    ``minutesLatency`` = whole minutes between message and like (computed
    client-side: Ladybug has no interval-to-epoch function); ``isNew`` flags
    likers outside the direct knows neighbourhood. Ordered by like date DESC,
    liker ID ASC. LIMIT 20.
    """
    p = PARAMS[7].copy()
    if personId is not None:
        p["personId"] = personId
    bound = {"personId": p["personId"]}
    print(f"\nQuery 7  parameters: $personId={bound['personId']!r}")
    import polars as pl

    # NOTE: single statement over both like-tables; latest-per-liker and the
    # top-20 are selected client-side (see _execute_union_top rationale).
    query = """
        // likes of own posts
        MATCH (liker:Person)-[l:likePost]->(msg:Post)-[:postHasCreator]->(owner:Person {ID: $personId})
        OPTIONAL MATCH (liker)-[k:knows]-(owner)
        RETURN liker.ID AS likerId, liker.firstName AS likerFirstName,
               liker.lastName AS likerLastName, l.creationDate AS likeTime,
               msg.ID AS msgId, COALESCE(msg.content, msg.imageFile) AS msgContent,
               msg.creationDate AS msgTime,
               (CASE WHEN k IS NULL THEN 1 ELSE 0 END) AS isOutsider
        UNION ALL
        // likes of own comments
        MATCH (liker:Person)-[l:likeComment]->(msg:Comment)-[:commentHasCreator]->(owner:Person {ID: $personId})
        OPTIONAL MATCH (liker)-[k:knows]-(owner)
        RETURN liker.ID AS likerId, liker.firstName AS likerFirstName,
               liker.lastName AS likerLastName, l.creationDate AS likeTime,
               msg.ID AS msgId, msg.content AS msgContent,
               msg.creationDate AS msgTime,
               (CASE WHEN k IS NULL THEN 1 ELSE 0 END) AS isOutsider;
        // intended: latest like per liker; ORDER BY likeTime DESC, likerId ASC LIMIT 20
    """
    print(f"Query 7:\n{query}")
    response = conn.execute(query, {**bound, "dummy": 0})
    df = response.get_as_pl()
    response.close()
    assert isinstance(df, pl.DataFrame)
    # latest like per liker (tie -> smallest msg id), then top-20
    best_rows = []
    for liker_id in df["likerId"].unique().to_list():
        sub = df.filter(pl.col("likerId") == liker_id)
        top_time = sub["likeTime"].max()
        best = sub.filter(pl.col("likeTime") == top_time).sort("msgId").head(1)
        best_rows.append(best)
    top = pl.concat(best_rows)
    top = top.with_columns(
        ((pl.col("likeTime") - pl.col("msgTime")).dt.total_seconds() // 60).alias("minutesLatency"),
        (pl.col("isOutsider") == 1).alias("isNew"),
    ).select(
        pl.col("likerId").alias("personId"),
        pl.col("likerFirstName").alias("personFirstName"),
        pl.col("likerLastName").alias("personLastName"),
        pl.col("likeTime").alias("likeCreationDate"),
        pl.col("msgId").alias("commentOrPostId"),
        pl.col("msgContent").alias("commentOrPostContent"),
        "minutesLatency",
        "isNew",
    ).sort(["likeCreationDate", "personId"], descending=[True, False]).head(20)
    print(top)
    return top


# ---------------------------------------------------------------------------
# Q8. Recent replies (official: complex-8).
# ---------------------------------------------------------------------------
def run_query8(conn: Connection, personId: int | None = None):
    """Q8. Most recent reply comments to $personId's posts+comments.

    Parameters:
        $personId -- owner Person ID.
    Covers replyOfPost (to own posts) and replyOfComment (to own comments).
    Ordered by reply creation date DESC, reply ID ASC. LIMIT 20.
    """
    p = PARAMS[8].copy()
    if personId is not None:
        p["personId"] = personId
    query = """
        // replies to own posts
        MATCH (owner:Person {ID: $personId})<-[:postHasCreator]-(post:Post)
              <-[:replyOfPost]-(comment:Comment)-[:commentHasCreator]->(person:Person)
        RETURN person.ID AS personId, person.firstName AS personFirstName,
               person.lastName AS personLastName,
               comment.creationDate AS commentCreationDate, comment.ID AS commentId,
               comment.content AS commentContent
        UNION ALL
        // replies to own comments
        MATCH (owner:Person {ID: $personId})<-[:commentHasCreator]-(parent:Comment)
              <-[:replyOfComment]-(comment:Comment)-[:commentHasCreator]->(person:Person)
        RETURN person.ID AS personId, person.firstName AS personFirstName,
               person.lastName AS personLastName,
               comment.creationDate AS commentCreationDate, comment.ID AS commentId,
               comment.content AS commentContent;
        // intended: ORDER BY commentCreationDate DESC, commentId ASC LIMIT 20
        // (applied client-side, see _execute_union_top)
    """
    return _execute_union_top(
        conn, 8, query, p,
        sort_by=["commentCreationDate", "commentId"],
        descending=[True, False], limit=20,
    )


# ---------------------------------------------------------------------------
# Q9. Recent messages by friends/FoF (official: complex-9).
# ---------------------------------------------------------------------------
def run_query9(conn: Connection, personId: int | None = None, maxDate: str | None = None):
    """Q9. Recent posts+comments of friends/FoF of $personId, before $maxDate.

    Parameters:
        $personId -- start Person ID (1-2 hop neighbourhood, excl. self).
        $maxDate  -- upper bound (STRICT, official ``<``) "YYYY-MM-DD HH:MM:SS"
                     timestamp (official: epoch millis).
    Ordered by creation date DESC, message ID ASC. LIMIT 20.
    """
    p = PARAMS[9].copy()
    if personId is not None:
        p["personId"] = personId
    if maxDate is not None:
        p["maxDate"] = maxDate
    query = """
        // friends/FoF posts created strictly before $maxDate
        MATCH (root:Person {ID: $personId})-[:knows*1..2]-(friend:Person)
        WHERE friend.ID <> $personId
        WITH DISTINCT friend
        MATCH (friend)<-[:postHasCreator]-(message:Post)
        WHERE message.creationDate < TIMESTAMP($maxDate)
        RETURN friend.ID AS personId, friend.firstName AS personFirstName,
               friend.lastName AS personLastName, message.ID AS commentOrPostId,
               COALESCE(message.content, message.imageFile) AS commentOrPostContent,
               message.creationDate AS commentOrPostCreationDate
        UNION ALL
        // friends/FoF comments created strictly before $maxDate
        MATCH (root:Person {ID: $personId})-[:knows*1..2]-(friend:Person)
        WHERE friend.ID <> $personId
        WITH DISTINCT friend
        MATCH (friend)<-[:commentHasCreator]-(message:Comment)
        WHERE message.creationDate < TIMESTAMP($maxDate)
        RETURN friend.ID AS personId, friend.firstName AS personFirstName,
               friend.lastName AS personLastName, message.ID AS commentOrPostId,
               message.content AS commentOrPostContent,
               message.creationDate AS commentOrPostCreationDate;
        // intended: ORDER BY commentOrPostCreationDate DESC, commentOrPostId ASC LIMIT 20
        // (applied client-side, see _execute_union_top)
    """
    return _execute_union_top(
        conn, 9, query, p,
        sort_by=["commentOrPostCreationDate", "commentOrPostId"],
        descending=[True, False], limit=20,
    )


# ---------------------------------------------------------------------------
# Q10. Friend recommendation (official: complex-10).
# ---------------------------------------------------------------------------
def run_query10(conn: Connection, personId: int | None = None, month: int | None = None):
    """Q10. Friend-of-friend recommender for $personId.

    Parameters:
        $personId -- start Person ID.
        $month    -- zodiac start month: candidates whose birthday falls in
                     [month/21, next-month/22), i.e. the official horoscope
                     predicate ``(m = $month AND d >= 21) OR
                     (m = ($month % 12) + 1 AND d < 22)``.
    Candidates = exact-2-hop friends, excluding direct friends and self.
    Score = common-interest posts minus other posts, where a post is
    "common" if it carries one of $personId's interest tags. Ordered by score
    DESC, person ID ASC. LIMIT 10.
    """
    p = PARAMS[10].copy()
    if personId is not None:
        p["personId"] = personId
    if month is not None:
        p["month"] = month
    query = """
        MATCH (person:Person {ID: $personId})-[:hasInterest]->(i:Tag)
        WITH person, COLLECT(i) AS interests
        MATCH (person)-[:knows]-(:Person)-[:knows]-(friend:Person)
        WHERE friend.ID <> person.ID
          AND NOT EXISTS { MATCH (person)-[:knows]-(friend) }
        WITH DISTINCT person, interests, friend
        WHERE (date_part("month", friend.birthday) = $month
               AND date_part("day", friend.birthday) >= 21)
           OR (date_part("month", friend.birthday) = ($month % 12) + 1
               AND date_part("day", friend.birthday) < 22)
        WITH person, interests, friend
        OPTIONAL MATCH (friend)<-[:postHasCreator]-(common:Post)-[:postHasTag]->(it:Tag)
            WHERE it IN interests
        WITH person, friend, COUNT(DISTINCT common) AS commonPostCount
        OPTIONAL MATCH (friend)<-[:postHasCreator]-(ap:Post)
        WITH friend, commonPostCount, COUNT(DISTINCT ap) AS postCount
        MATCH (friend)-[:personIsLocatedIn]->(city:Place)
        RETURN friend.ID AS personId, friend.firstName AS personFirstName,
               friend.lastName AS personLastName,
               commonPostCount - (postCount - commonPostCount) AS commonInterestScore,
               friend.gender AS personGender, city.name AS personCityName
        ORDER BY commonInterestScore DESC, personId ASC
        LIMIT 10;
    """
    return _execute(conn, 10, query, p)


# ---------------------------------------------------------------------------
# Q11. Job referral (official: complex-11).
# ---------------------------------------------------------------------------
def run_query11(
    conn: Connection,
    personId: int | None = None,
    countryName: str | None = None,
    workFromYear: int | None = None,
):
    """Q11. Friends/FoF who started at a $countryName company before $workFromYear.

    Parameters:
        $personId      -- start Person ID (1-2 hop neighbourhood, excl. self).
        $countryName   -- country Place.name of the company.
        $workFromYear  -- exclusive upper bound on workAt.workFrom (start year).
    Ordered by workFrom ASC, person ID ASC, company name DESC. LIMIT 10.
    """
    p = PARAMS[11].copy()
    if personId is not None:
        p["personId"] = personId
    if countryName is not None:
        p["countryName"] = countryName
    if workFromYear is not None:
        p["workFromYear"] = workFromYear
    query = """
        MATCH (person:Person {ID: $personId})-[:knows*1..2]-(friend:Person)
        WHERE friend.ID <> $personId
        WITH DISTINCT friend
        MATCH (friend)-[workAt:workAt]->(company:Organisation)
                  -[:organisationIsLocatedIn]->(:Place {name: $countryName})
        WHERE company.type = "company" AND workAt.workFrom < $workFromYear
        RETURN friend.ID AS personId, friend.firstName AS personFirstName,
               friend.lastName AS personLastName, company.name AS organizationName,
               workAt.workFrom AS organizationWorkFromYear
        ORDER BY organizationWorkFromYear ASC, personId ASC, organizationName DESC
        LIMIT 10;
    """
    return _execute(conn, 11, query, p)


# ---------------------------------------------------------------------------
# Q12. Expert search (official: complex-12).
# ---------------------------------------------------------------------------
def run_query12(conn: Connection, personId: int | None = None, tagClassName: str | None = None):
    """Q12. Friends of $personId replying most to $tagClassName posts.

    Parameters:
        $personId     -- start Person ID (direct friends only).
        $tagClassName -- Tagclass.name (official ``tagClassName``); matches the
                         tag of that name (if any) plus all tags whose
                         ``-[:hasType]->-[:isSubclassOf*0..]->`` hierarchy
                         reaches that class (official
                         ``HAS_TYPE|IS_SUBCLASS_OF*0..``).
    Counts friends' comments replying (replyOfPost) to posts carrying those
    tags. Returns reply tag names + reply count, ordered by count DESC,
    person ID ASC. LIMIT 20.
    """
    p = PARAMS[12].copy()
    if personId is not None:
        p["personId"] = personId
    if tagClassName is not None:
        p["tagClassName"] = tagClassName
    # NOTE: resolved in two small steps (a big IN-list or a single
    # alternation pattern is unreliable here); same semantics.
    direct = _get(
        conn,
        "MATCH (t:Tag) WHERE t.name = $tagClassName RETURN t.ID AS tid;",
        {"tagClassName": p["tagClassName"], "dummy": 0},
    )
    hier = _get(
        conn,
        "MATCH (t:Tag)-[:hasType]->(:Tagclass)-[:isSubclassOf*0..]->(base:Tagclass {name: $tagClassName})"
        " RETURN DISTINCT t.ID AS tid;",
        {"tagClassName": p["tagClassName"], "dummy": 0},
    )
    tag_ids = sorted({r[0] for r in direct} | {r[0] for r in hier})
    print(f"[Q12] tags in '{p['tagClassName']}' hierarchy: {len(tag_ids)}")
    if not tag_ids:
        print("Query 12: no tags for this class.")
        return []
    query = """
        MATCH (me:Person {ID: $personId})-[:knows]-(friend:Person)
        WITH DISTINCT friend
        MATCH (reply:Comment)-[:commentHasCreator]->(friend),
              (reply)-[:replyOfPost]->(post:Post)-[:postHasTag]->(tag:Tag)
        WHERE tag.ID IN $tagIds
        RETURN friend.ID AS personId, friend.firstName AS personFirstName,
               friend.lastName AS personLastName,
               COLLECT(DISTINCT tag.name) AS tagNames,
               COUNT(DISTINCT reply) AS replyCount
        ORDER BY replyCount DESC, personId ASC
        LIMIT 20;
    """
    print(f"Query 12:\n{query}")
    return _execute(conn, 12, query, {"personId": p["personId"], "tagIds": tag_ids})


# ---------------------------------------------------------------------------
# Q13. Single shortest path (official: complex-13).
# ---------------------------------------------------------------------------
def run_query13(conn: Connection, person1Id: int | None = None, person2Id: int | None = None):
    """Q13. Shortest knows-path length between $person1Id and $person2Id.

    Parameters:
        $person1Id -- start Person ID (official ``person1Id``).
        $person2Id -- target Person ID (official ``person2Id``).
    Undirected traversal of the knows subgraph (edges are stored directed).
    Returns -1 when disconnected (official ``CASE path IS NULL``), via Python
    since an empty SHORTEST match yields no row.
    """
    p = PARAMS[13].copy()
    if person1Id is not None:
        p["person1Id"] = person1Id
    if person2Id is not None:
        p["person2Id"] = person2Id
    query = """
        MATCH (person1:Person {ID: $person1Id})-[e:knows* SHORTEST 1..10]-(person2:Person {ID: $person2Id})
        RETURN LENGTH(e) AS shortestPathLength;
    """
    result = _execute(conn, 13, query, p)
    try:
        if len(result) == 0:  # type: ignore
            print("Query 13: disconnected -> shortestPathLength = -1")
            return -1
    except TypeError:
        pass
    return result


# ---------------------------------------------------------------------------
# Q14. Trusted connection paths (official: complex-14).
# ---------------------------------------------------------------------------
def _count_weighted_exchanges(conn: Connection, x: int, y: int) -> tuple[int, int]:
    """Interaction volumes between persons X and Y (both directions).

    Official weights: comment-reply-post pairs count 1.0 each, and
    comment-reply-comment pairs 0.5 each. The knows table itself carries no
    weight property, so reply volume is the weight (official ``reduce``).
    Returns (post_replies, comment_replies).
    """
    rows = _get(
        conn,
        """
        MATCH (c:Comment)-[:commentHasCreator]->(x:Person {ID: $x}),
              (c)-[:replyOfPost]->(post:Post)-[:postHasCreator]->(y:Person {ID: $y})
        RETURN COUNT(c) AS n
        UNION ALL
        MATCH (c:Comment)-[:commentHasCreator]->(x:Person {ID: $x}),
              (c)-[:replyOfComment]->(pc:Comment)-[:commentHasCreator]->(y:Person {ID: $y})
        RETURN COUNT(c) AS n
        """,
        {"x": x, "y": y, "dummy": 0},
    )
    post_n = rows[0][0] if len(rows) > 0 else 0
    comment_n = rows[1][0] if len(rows) > 1 else 0
    return post_n, comment_n


def run_query14(conn: Connection, person1Id: int | None = None, person2Id: int | None = None):
    """Q14. All shortest knows-paths between $person1Id and $person2Id, weighted.

    Parameters:
        $person1Id -- start Person ID (official ``person1Id``).
        $person2Id -- target Person ID (official ``person2Id``).
    Step 1 finds the shortest length L (as in Q13). Step 2 enumerates every
    L-hop path (unrolled undirected knows chain built in Python; Ladybug has
    no ``allShortestPaths``/``reduce``). Step 3 weights each edge with
    ``1.0 * postReplies + 0.5 * commentReplies`` (official weights); path
    weight = sum of edge weights. Ordered by path weight DESC (official).
    """
    p = PARAMS[14].copy()
    if person1Id is not None:
        p["person1Id"] = person1Id
    if person2Id is not None:
        p["person2Id"] = person2Id
    x, y = p["person1Id"], p["person2Id"]

    # --- step 1: shortest length ------------------------------------------------
    rows = _get(
        conn,
        "MATCH (a:Person {ID: $person1Id})-[e:knows* SHORTEST 1..10]-(b:Person {ID: $person2Id})"
        " RETURN LENGTH(e) AS shortestPathLength;",
        {"person1Id": x, "person2Id": y, "dummy": 0},
    )
    if not rows:
        print(f"\nQuery 14  parameters: $person1Id={x!r}, $person2Id={y!r}")
        print("Query 14: no knows-path between the two persons (within 10 hops).")
        return rows
    length = rows[0][0]
    print(f"\nQuery 14  parameters: $person1Id={x!r}, $person2Id={y!r}")
    print(f"Query 14: shortest length = {length}; enumerating all {length}-hop paths ...")

    # --- step 2: enumerate all L-hop paths (unrolled chain) ---------------------
    nodes = ["a"] + [f"n{i}" for i in range(1, length)] + ["b"]
    match = f"MATCH (a:Person {{ID: $person1Id}})"
    for i in range(length):
        match += f"-[:knows]-({nodes[i + 1]}" + ("", ":Person")[i < length - 1] + ")"
    match += f" WHERE {nodes[-1]}.ID = $person2Id"
    # intermediate nodes must be distinct people (simple paths only)
    if length > 1:
        mids = nodes[1:-1] + ["a"]
        conds = [f"{m1}.ID <> {m2}.ID" for i, m1 in enumerate(mids) for m2 in (["b"] + mids[i + 1 :])]
        match += " AND " + " AND ".join(conds)
    ret_ids = ", ".join(f"{n}.ID AS id{i}" for i, n in enumerate(nodes))
    paths = _get(conn, f"{match} RETURN {ret_ids};", {"person1Id": x, "person2Id": y, "dummy": 0})

    # --- step 3: weight each path (official 1.0 / 0.5 weights) ------------------
    weighted = []
    for path in paths:
        w1 = w2 = 0
        for i in range(length):
            a, b = path[i], path[i + 1]
            p1, c1 = _count_weighted_exchanges(conn, a, b)
            p2, c2 = _count_weighted_exchanges(conn, b, a)
            w1 += p1 + p2
            w2 += c1 + c2
        weighted.append((w1 + 0.5 * w2, list(path)))
    weighted.sort(key=lambda t: -t[0])
    print(f"Query 14: {len(weighted)} shortest path(s) of length {length}:")
    for w, path in weighted:
        print(f"  pathWeight={w}  personIdsInPath={path}")
    return weighted


QUERY_FUNCTIONS: dict[int, Callable[..., object]] = {
    1: run_query1,
    2: run_query2,
    3: run_query3,
    4: run_query4,
    5: run_query5,
    6: run_query6,
    7: run_query7,
    8: run_query8,
    9: run_query9,
    10: run_query10,
    11: run_query11,
    12: run_query12,
    13: run_query13,
    14: run_query14,
}


def _parse_selection(argv: list[str]) -> list[int] | None:
    if not argv:
        return None
    selection = argv[0].strip()
    if selection in {"run_all", "all"}:
        return None
    parts = [p.strip() for p in selection.split(",") if p.strip()]
    indices: list[int] = []
    for part in parts:
        try:
            indices.append(int(part))
        except ValueError:
            raise ValueError(f"Invalid query index: {part}")
    return indices


def main(conn: Connection, selected: list[int] | None = None) -> None:
    start = time.perf_counter()
    if selected is None:
        selected = list(QUERY_FUNCTIONS.keys())
    for idx in selected:
        func = QUERY_FUNCTIONS.get(idx)
        if func is None:
            print(f"Skipping unknown query index: {idx}")
            continue
        func(conn)
    elapsed = time.perf_counter() - start
    print(f"\nCompleted {len(selected)} query(ies) in {elapsed:.2f}s")


if __name__ == "__main__":
    DB_NAME = "ldbc_snb_sf1.lbdb"
    db = lb.Database(f"./{DB_NAME}")
    conn = lb.Connection(db)
    selected_queries = _parse_selection(sys.argv[1:])
    main(conn, selected_queries)
