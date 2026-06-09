// 01-indexes.js — Atlas Search index DDL for chunks collection.
//
// Sources: ADR-0007 D4 (vector + BM25 index definitions),
//          ADR-0008 D2 (tenant_id filter slot),
//          ADR-0010 D5 (consolidated DDL block).
//
// atlas-local executes any *.js under /docker-entrypoint-initdb.d/ via
// mongosh on first container boot. Mounted in by infra/docker/docker-compose.yml.
//
// Idempotent: every createSearchIndex call is wrapped in a try/catch that
// swallows "DuplicateIndex" / "IndexAlreadyExists" — second boot is a no-op.

(function () {
  const dbName = "acquire_gov";
  const target = db.getSiblingDB(dbName);

  // Make sure `chunks` collection exists so createSearchIndex has somewhere
  // to attach. createCollection is idempotent (errors swallowed).
  try {
    target.createCollection("chunks");
  } catch (e) {
    if (e.codeName !== "NamespaceExists") throw e;
  }

  // ---- far_vector_idx (ADR-0007 D4) ------------------------------------
  // numDimensions: 512  → Titan v2 embeddings @ 512 dims (ADR-0005 D2).
  // similarity:   cosine
  // quantization: scalar (4x faster recall vs none on 512-dim Titan v2)
  // filter slots: tenant_id  → REQ-RAG-3 pre-filter (ADR-0008 D2)
  //               far_section + far_clause → query classifier hints (ADR-0006 D3)
  const VECTOR_INDEX = {
    name: "far_vector_idx",
    type: "vectorSearch",
    definition: {
      fields: [
        {
          type: "vector",
          path: "embedding",
          numDimensions: 512,
          similarity: "cosine",
          quantization: "scalar",
        },
        { type: "filter", path: "tenant_id" },
        { type: "filter", path: "far_section" },
        { type: "filter", path: "far_clause" },
      ],
    },
  };

  // ---- far_search_idx (ADR-0007 D4) -----------------------------------
  // BM25 for full-text half of $rankFusion. dynamic: true keeps the index
  // permissive — chunk fields can grow without an index rebuild.
  const SEARCH_INDEX = {
    name: "far_search_idx",
    type: "search",
    definition: { mappings: { dynamic: true } },
  };

  function createSearchIndexIdempotent(coll, indexDef) {
    try {
      coll.createSearchIndex(indexDef);
      print(`[seed] createSearchIndex ${indexDef.name} → submitted`);
    } catch (e) {
      const msg = String(e.message || e);
      // atlas-local raises different codeNames depending on version.
      // The substrings below cover all observed "already exists" variants.
      if (
        msg.indexOf("already exists") >= 0 ||
        msg.indexOf("DuplicateIndex") >= 0 ||
        msg.indexOf("IndexAlreadyExists") >= 0
      ) {
        print(`[seed] createSearchIndex ${indexDef.name} → already exists, skipping`);
        return;
      }
      throw e;
    }
  }

  createSearchIndexIdempotent(target.chunks, VECTOR_INDEX);
  createSearchIndexIdempotent(target.chunks, SEARCH_INDEX);

  print("[seed] 01-indexes.js complete");
})();
