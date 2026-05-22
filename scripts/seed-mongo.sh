#!/usr/bin/env bash
# Seed the local MongoDB with a few demo solicitations.
# Usage:  ./scripts/seed-mongo.sh   (run after `docker-compose up`)

set -euo pipefail

MONGO_URL="${MONGO_URL:-mongodb://app:app_dev_password@localhost:27017}"

cat <<'EOF' | docker run --rm -i --network host mongo:7 mongosh "$MONGO_URL/acquire_gov?authSource=admin"
db.solicitations.insertMany([
  {
    agencyId: "DOI",
    title: "FAR 52.219-9 Small Business Subcontracting Plan — IT Modernization",
    description: "<p>Recompete of the DOI bureau-wide IT modernization vehicle.</p>",
    status: "DRAFT",
    createdAt: new Date(),
    updatedAt: new Date()
  },
  {
    agencyId: "GSA",
    title: "Cloud Migration Services — Civilian Agency Pool 3",
    description: "Multiple-award IDIQ for cloud migration support.",
    status: "OPEN",
    createdAt: new Date(),
    updatedAt: new Date()
  }
]);
print("Seeded " + db.solicitations.countDocuments() + " solicitations.");
EOF
