// 02-roles.js — append-only audit_log roles per ADR-0008 D3.
//
// Two roles bound at seed time:
//   auditLogWriter  — privileges: insert + find (NO update, NO remove).
//                     Orchestrator service user binds to this role only.
//   auditLogReader  — privileges: find only.
//                     For OIG-replay / CO-review endpoint (Phase 1.5; not
//                     served by orchestrator).
//
// Both roles are scoped to {db: "acquire_gov", collection: "audit_log"}.
// Granting these privileges at the role level means an attacker who pivots
// onto the orchestrator service account CANNOT mutate audit history —
// the "append-only by DB role, not by app code" property from ADR-0008 D3.
//
// Idempotent: createRole errors are swallowed if the role already exists.

(function () {
  const target = db.getSiblingDB("acquire_gov");

  const WRITER = {
    role: "auditLogWriter",
    privileges: [
      {
        resource: { db: "acquire_gov", collection: "audit_log" },
        actions: ["insert", "find"],
      },
    ],
    roles: [],
  };

  const READER = {
    role: "auditLogReader",
    privileges: [
      {
        resource: { db: "acquire_gov", collection: "audit_log" },
        actions: ["find"],
      },
    ],
    roles: [],
  };

  function createRoleIdempotent(roleDef) {
    try {
      target.createRole(roleDef);
      print(`[seed] createRole ${roleDef.role} → created`);
    } catch (e) {
      const msg = String(e.message || e);
      if (
        msg.indexOf("already exists") >= 0 ||
        msg.indexOf("Role already exists") >= 0 ||
        msg.indexOf("DuplicateKey") >= 0
      ) {
        print(`[seed] createRole ${roleDef.role} → already exists, skipping`);
        return;
      }
      throw e;
    }
  }

  createRoleIdempotent(WRITER);
  createRoleIdempotent(READER);

  print("[seed] 02-roles.js complete");
})();
