// 03-audit-indexes.js — audit_log btree indexes for OIG-replay queries.
//
// Source: ADR-0008 D3 + ADR-0010 D5.
//
// The three query patterns OIG / CO replay clients use:
//   - "everything in time order"            → {ts: 1}
//   - "everything for tenant X in time"      → {tenant_id: 1, ts: -1}
//   - "trace by request_id across services"  → {request_id: 1}
//
// All createIndex calls are idempotent in Mongo by name+spec; no extra
// try/catch needed.

(function () {
  const target = db.getSiblingDB("acquire_gov");

  // Ensure collection exists before indexing (idempotent).
  try {
    target.createCollection("audit_log");
  } catch (e) {
    if (e.codeName !== "NamespaceExists") throw e;
  }

  target.audit_log.createIndex({ ts: 1 });
  target.audit_log.createIndex({ tenant_id: 1, ts: -1 });
  target.audit_log.createIndex({ request_id: 1 });

  print("[seed] 03-audit-indexes.js complete");
})();
