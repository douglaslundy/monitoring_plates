#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const { DatabaseSync } = require("node:sqlite");

function nowSqlite() {
  return new Date().toISOString().replace("T", " ").replace("Z", "");
}

function genId() {
  return crypto.randomBytes(12).toString("base64url").slice(0, 16);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function main() {
  const workflowFile = process.argv[2] || path.join("infra", "n8n", "whatsapp-alert.workflow.json");
  const dbFile = process.argv[3] || "n8n-database.sqlite";

  const workflow = readJson(workflowFile);
  const db = new DatabaseSync(dbFile);
  db.exec("PRAGMA foreign_keys = OFF");
  db.exec("BEGIN");
  try {
    const existing = db
      .prepare("SELECT id FROM workflow_entity WHERE name = ?")
      .get(workflow.name);
    if (existing) {
      db.prepare("DELETE FROM shared_workflow WHERE workflowId = ?").run(existing.id);
      db.prepare("DELETE FROM workflow_published_version WHERE workflowId = ?").run(existing.id);
      db.prepare("DELETE FROM workflow_history WHERE workflowId = ?").run(existing.id);
      db.prepare("DELETE FROM workflow_entity WHERE id = ?").run(existing.id);
    }

    const project = db.prepare("SELECT id FROM project ORDER BY createdAt LIMIT 1").get();
    if (!project) {
      throw new Error("No project found in n8n database");
    }

    const workflowId = genId();
    const versionId = crypto.randomUUID();
    const createdAt = nowSqlite();
    const nodes = JSON.stringify(workflow.nodes);
    const connections = JSON.stringify(workflow.connections);
    const settings = JSON.stringify(workflow.settings ?? { executionOrder: "v1", binaryMode: "separate", availableInMCP: false });
    const pinData = JSON.stringify(workflow.pinData ?? {});
    const nodeGroups = JSON.stringify(workflow.nodeGroups ?? []);

    db.prepare(
      `INSERT INTO workflow_history (
        versionId, workflowId, authors, createdAt, updatedAt, nodes, connections, name,
        autosaved, description, nodeGroups
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      versionId,
      workflowId,
      workflow.authors ?? "Douglas Lundy Santos",
      createdAt,
      createdAt,
      nodes,
      connections,
      workflow.name,
      1,
      workflow.description ?? null,
      nodeGroups,
    );

    db.prepare(
      `INSERT INTO workflow_entity (
        id, name, active, nodes, connections, settings, staticData, pinData, versionId,
        triggerCount, meta, parentFolderId, createdAt, updatedAt, isArchived, versionCounter,
        description, activeVersionId, nodeGroups, sourceWorkflowId
      ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?
      )`,
    ).run(
      workflowId,
      workflow.name,
      workflow.active ? 1 : 0,
      nodes,
      connections,
      settings,
      null,
      pinData,
      versionId,
      0,
      null,
      null,
      createdAt,
      createdAt,
      0,
      1,
      workflow.description ?? null,
      workflow.active ? versionId : null,
      nodeGroups,
      null,
    );

    db.prepare(
      "INSERT INTO shared_workflow (workflowId, projectId, role, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?)",
    ).run(workflowId, project.id, "workflow:owner", createdAt, createdAt);

    if (workflow.active) {
      db.prepare(
        "INSERT INTO workflow_published_version (workflowId, publishedVersionId, createdAt, updatedAt) VALUES (?, ?, ?, ?)",
      ).run(workflowId, versionId, createdAt, createdAt);
    }

    db.exec("COMMIT");
    db.exec("PRAGMA foreign_keys = ON");
    console.log(JSON.stringify({ workflowId, versionId }, null, 2));
  } catch (error) {
    db.exec("ROLLBACK");
    db.exec("PRAGMA foreign_keys = ON");
    throw error;
  }
}

main();
