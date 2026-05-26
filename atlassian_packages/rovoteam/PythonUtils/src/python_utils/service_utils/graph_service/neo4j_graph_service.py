"""
Neo4j Graph Service

Neo4j-backed graph storage service using the Bolt protocol.
Ported from ``Neo4jEntityGraphStore`` and generalized with namespace support.

Architecture:
    - Single ``Entity`` node label with composite uniqueness on ``(namespace, node_id)``.
    - Namespace stored as a property on all ``Entity`` nodes. All Cypher ``MATCH``
      clauses include ``{namespace: $namespace}``. Sentinel ``"_default"`` for ``None``.
    - ``__attrs_post_init__`` runs a migration: ``SET n.namespace = '_default'``
      for any existing nodes missing the namespace property.
    - Single ``RELATES_TO`` relationship type with ``edge_type`` stored as a
      relationship property.
    - Node and edge properties stored as JSON strings.
    - ``MERGE`` for upsert semantics on ``add_node``.
    - ``DETACH DELETE`` for cascade removal on ``remove_node``.
    - Variable-length path queries for ``get_neighbors`` with depth parameter.

Requires: ``neo4j``
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .graph_node import GraphEdge, GraphNode
from .graph_service_base import GraphServiceBase
from python_utils.service_utils.data_operation_record import DataOperationRecord

logger = logging.getLogger(__name__)

_DEFAULT_NAMESPACE = "_default"


@attrs(slots=False, repr=False)
class Neo4jGraphService(GraphServiceBase):
    """Neo4j-backed graph storage service.

    Attributes:
        uri: Neo4j Bolt URI, e.g. ``"bolt://localhost:7687"``.
        auth: ``(username, password)`` tuple.
        database: Neo4j database name (default ``"neo4j"``).
    """

    uri: str = attrib()
    auth: Tuple[str, str] = attrib()
    database: str = attrib(default="neo4j")
    _driver: Any = attrib(init=False, default=None)
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(self.uri, auth=self.auth)
        self._ensure_indexes()
        self._migrate_namespace()

    # ── internal ──

    def _ensure_indexes(self):
        with self._driver.session(database=self.database) as session:
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS "
                "FOR (n:Entity) REQUIRE (n.namespace, n.node_id) IS UNIQUE"
            )
            session.run(
                "CREATE INDEX IF NOT EXISTS "
                "FOR (n:Entity) ON (n.node_type)"
            )

    def _migrate_namespace(self):
        """Set namespace='_default' on any existing nodes missing it."""
        with self._driver.session(database=self.database) as session:
            session.run(
                "MATCH (n:Entity) WHERE n.namespace IS NULL "
                "SET n.namespace = $_default",
                _default=_DEFAULT_NAMESPACE,
            )

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    @staticmethod
    def _node_from_record(record) -> GraphNode:
        props_json = record.get("properties", "{}")
        try:
            properties = json.loads(props_json) if isinstance(props_json, str) else {}
        except (json.JSONDecodeError, TypeError):
            properties = {}
        history_json = record.get("history", "[]")
        try:
            history_raw = json.loads(history_json) if isinstance(history_json, str) else []
        except (json.JSONDecodeError, TypeError):
            history_raw = []
        history = [DataOperationRecord.from_dict(r) for r in history_raw if isinstance(r, dict)]
        return GraphNode(
            node_id=record["node_id"],
            node_type=record["node_type"],
            label=record.get("label", ""),
            properties=properties,
            history=history,
            is_active=record.get("is_active", True),
        )

    @staticmethod
    def _edge_from_rel(source_id, target_id, rel) -> GraphEdge:
        props_json = rel.get("properties", "{}")
        try:
            properties = json.loads(props_json) if isinstance(props_json, str) else {}
        except (json.JSONDecodeError, TypeError):
            properties = {}
        history_json = rel.get("history", "[]")
        try:
            history_raw = json.loads(history_json) if isinstance(history_json, str) else []
        except (json.JSONDecodeError, TypeError):
            history_raw = []
        history = [DataOperationRecord.from_dict(r) for r in history_raw if isinstance(r, dict)]
        return GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=rel.get("relation_type", ""),
            properties=properties,
            history=history,
            is_active=rel.get("is_active", True),
        )

    # ── GraphServiceBase implementation ──

    def add_node(self, node: GraphNode, namespace: Optional[str] = None) -> None:
        ns = self._resolve_namespace(namespace)
        props_json = json.dumps(node.properties, ensure_ascii=False)
        history_json = json.dumps([r.to_dict() for r in node.history], ensure_ascii=False)
        with self._driver.session(database=self.database) as session:
            session.run(
                "MERGE (n:Entity {namespace: $ns, node_id: $node_id}) "
                "SET n.node_type = $node_type, "
                "    n.label = $label, "
                "    n.properties = $properties, "
                "    n.history = $history, "
                "    n.is_active = $is_active",
                ns=ns,
                node_id=node.node_id,
                node_type=node.node_type,
                label=node.label,
                properties=props_json,
                history=history_json,
                is_active=node.is_active,
            )

    def get_node(self, node_id: str, namespace: Optional[str] = None) -> Optional[GraphNode]:
        ns = self._resolve_namespace(namespace)
        with self._driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (n:Entity {namespace: $ns, node_id: $node_id}) RETURN n",
                ns=ns, node_id=node_id,
            )
            record = result.single()
            if record is None:
                return None
            return self._node_from_record(record["n"])

    def remove_node(self, node_id: str, namespace: Optional[str] = None) -> bool:
        ns = self._resolve_namespace(namespace)
        with self._driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (n:Entity {namespace: $ns, node_id: $node_id}) "
                "DETACH DELETE n "
                "RETURN count(n) AS cnt",
                ns=ns, node_id=node_id,
            )
            record = result.single()
            return record is not None and record["cnt"] > 0

    def add_edge(self, edge: GraphEdge, namespace: Optional[str] = None) -> None:
        ns = self._resolve_namespace(namespace)
        props_json = json.dumps(edge.properties, ensure_ascii=False)
        with self._driver.session(database=self.database) as session:
            result = session.run(
                "OPTIONAL MATCH (a:Entity {namespace: $ns, node_id: $src}) "
                "OPTIONAL MATCH (b:Entity {namespace: $ns, node_id: $tgt}) "
                "RETURN a IS NOT NULL AS src_exists, b IS NOT NULL AS tgt_exists",
                ns=ns, src=edge.source_id, tgt=edge.target_id,
            )
            record = result.single()
            if not record["src_exists"]:
                raise ValueError(f"Source node '{edge.source_id}' does not exist")
            if not record["tgt_exists"]:
                raise ValueError(f"Target node '{edge.target_id}' does not exist")
            history_json = json.dumps([r.to_dict() for r in edge.history], ensure_ascii=False)
            session.run(
                "MATCH (a:Entity {namespace: $ns, node_id: $src}) "
                "MATCH (b:Entity {namespace: $ns, node_id: $tgt}) "
                "CREATE (a)-[r:RELATES_TO {"
                "  relation_type: $rel_type, "
                "  properties: $props, "
                "  history: $history, "
                "  is_active: $is_active"
                "}]->(b)",
                ns=ns, src=edge.source_id, tgt=edge.target_id,
                rel_type=edge.edge_type, props=props_json,
                history=history_json, is_active=edge.is_active,
            )

    def get_edges(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        direction: str = "outgoing",
        namespace: Optional[str] = None,
    ) -> List[GraphEdge]:
        ns = self._resolve_namespace(namespace)
        results: List[GraphEdge] = []
        with self._driver.session(database=self.database) as session:
            if direction in ("outgoing", "both"):
                q = "MATCH (n:Entity {namespace: $ns, node_id: $nid})-[r:RELATES_TO]->(m:Entity {namespace: $ns}) "
                if edge_type is not None:
                    q += "WHERE r.relation_type = $et "
                q += "RETURN n.node_id AS src, m.node_id AS tgt, r.relation_type AS rt, r.properties AS props, r.history AS hist, r.is_active AS active"
                params: Dict[str, Any] = {"ns": ns, "nid": node_id}
                if edge_type is not None:
                    params["et"] = edge_type
                for rec in session.run(q, **params):
                    results.append(self._edge_from_rel(rec["src"], rec["tgt"], {
                        "relation_type": rec["rt"], "properties": rec["props"] or "{}",
                        "history": rec["hist"] or "[]", "is_active": rec.get("active", True),
                    }))

            if direction in ("incoming", "both"):
                q = "MATCH (n:Entity {namespace: $ns, node_id: $nid})<-[r:RELATES_TO]-(m:Entity {namespace: $ns}) "
                if edge_type is not None:
                    q += "WHERE r.relation_type = $et "
                q += "RETURN m.node_id AS src, n.node_id AS tgt, r.relation_type AS rt, r.properties AS props, r.history AS hist, r.is_active AS active"
                params = {"ns": ns, "nid": node_id}
                if edge_type is not None:
                    params["et"] = edge_type
                for rec in session.run(q, **params):
                    results.append(self._edge_from_rel(rec["src"], rec["tgt"], {
                        "relation_type": rec["rt"], "properties": rec["props"] or "{}",
                        "history": rec["hist"] or "[]", "is_active": rec.get("active", True),
                    }))
        return results

    def remove_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        namespace: Optional[str] = None,
    ) -> bool:
        ns = self._resolve_namespace(namespace)
        with self._driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (a:Entity {namespace: $ns, node_id: $src})"
                "-[r:RELATES_TO {relation_type: $rt}]->"
                "(b:Entity {namespace: $ns, node_id: $tgt}) "
                "DELETE r RETURN count(r) AS cnt",
                ns=ns, src=source_id, tgt=target_id, rt=edge_type,
            )
            record = result.single()
            return record is not None and record["cnt"] > 0

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        depth: int = 1,
        namespace: Optional[str] = None,
    ) -> List[Tuple[GraphNode, int]]:
        ns = self._resolve_namespace(namespace)
        with self._driver.session(database=self.database) as session:
            exists = session.run(
                "MATCH (n:Entity {namespace: $ns, node_id: $nid}) RETURN n",
                ns=ns, nid=node_id,
            )
            if exists.single() is None:
                return []

            if edge_type is not None:
                q = (
                    f"MATCH path = (start:Entity {{namespace: $ns, node_id: $nid}})"
                    f"-[r:RELATES_TO*1..{depth}]->"
                    f"(neighbor:Entity {{namespace: $ns}}) "
                    "WHERE ALL(rel IN relationships(path) WHERE rel.relation_type = $et) "
                    "AND neighbor.node_id <> $nid "
                    "RETURN neighbor, min(length(path)) AS depth ORDER BY depth"
                )
                params: Dict[str, Any] = {"ns": ns, "nid": node_id, "et": edge_type}
            else:
                q = (
                    f"MATCH path = (start:Entity {{namespace: $ns, node_id: $nid}})"
                    f"-[r:RELATES_TO*1..{depth}]->"
                    f"(neighbor:Entity {{namespace: $ns}}) "
                    "WHERE neighbor.node_id <> $nid "
                    "RETURN neighbor, min(length(path)) AS depth ORDER BY depth"
                )
                params = {"ns": ns, "nid": node_id}

            seen: Dict[str, int] = {}
            results: List[Tuple[GraphNode, int]] = []
            for rec in session.run(q, **params):
                neo_node = rec["neighbor"]
                d = rec["depth"]
                nid = neo_node["node_id"]
                if nid not in seen:
                    seen[nid] = d
                    results.append((self._node_from_record(neo_node), d))
            return results

    def list_nodes(
        self,
        node_type: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> List[GraphNode]:
        ns = self._resolve_namespace(namespace)
        with self._driver.session(database=self.database) as session:
            if node_type is not None:
                records = session.run(
                    "MATCH (n:Entity {namespace: $ns, node_type: $nt}) RETURN n",
                    ns=ns, nt=node_type,
                )
            else:
                records = session.run(
                    "MATCH (n:Entity {namespace: $ns}) RETURN n",
                    ns=ns,
                )
            return [self._node_from_record(r["n"]) for r in records]

    def size(self, namespace: Optional[str] = None) -> int:
        ns = self._resolve_namespace(namespace)
        with self._driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (n:Entity {namespace: $ns}) RETURN count(n) AS cnt",
                ns=ns,
            )
            record = result.single()
            return record["cnt"] if record else 0

    def clear(self, namespace: Optional[str] = None) -> int:
        ns = self._resolve_namespace(namespace)
        count = self.size(namespace=namespace)
        if count > 0:
            with self._driver.session(database=self.database) as session:
                session.run(
                    "MATCH (n:Entity {namespace: $ns}) DETACH DELETE n",
                    ns=ns,
                )
        return count

    def namespaces(self) -> List[str]:
        with self._driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (n:Entity) RETURN DISTINCT n.namespace AS ns"
            )
            return [r["ns"] for r in result if r["ns"] is not None]

    def _edge_count(self, namespace: str) -> int:
        """Count edges in a namespace."""
        with self._driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (a:Entity {namespace: $ns})-[r:RELATES_TO]->(b:Entity {namespace: $ns}) "
                "RETURN count(r) AS cnt",
                ns=namespace,
            )
            record = result.single()
            return record["cnt"] if record else 0

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        if namespace is not None:
            ns = namespace
            return {
                "backend": "neo4j",
                "uri": self.uri,
                "database": self.database,
                "namespace": ns,
                "nodes": self.size(namespace=ns),
                "edges": self._edge_count(ns),
            }
        all_ns = self.namespaces()
        total_nodes = sum(self.size(namespace=ns) for ns in all_ns)
        total_edges = sum(self._edge_count(ns) for ns in all_ns)
        return {
            "backend": "neo4j",
            "uri": self.uri,
            "database": self.database,
            "namespace_count": len(all_ns),
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "namespaces": {
                ns: {"nodes": self.size(namespace=ns), "edges": self._edge_count(ns)}
                for ns in all_ns
            },
        }

    def ping(self) -> bool:
        if self._closed or self._driver is None:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._driver is not None:
                self._driver.close()
                self._driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return (
            f"Neo4jGraphService("
            f"uri='{self.uri}', "
            f"database='{self.database}', "
            f"closed={self._closed})"
        )
