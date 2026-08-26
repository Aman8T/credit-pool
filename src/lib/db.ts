import Database from "better-sqlite3";
import fs from "fs";
import path from "path";

export type CreditPool = {
  id: number;
  name: string;
  totalCredits: number;
  allocatedCredits: number;
  createdAt: string;
};

const dataDir = path.join(process.cwd(), "data");
const dbPath = path.join(dataDir, "credit-pool.db");

let db: Database.Database | null = null;

function getDb(): Database.Database {
  if (!db) {
    fs.mkdirSync(dataDir, { recursive: true });
    db = new Database(dbPath);
    db.exec(`
      CREATE TABLE IF NOT EXISTS credit_pools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        total_credits INTEGER NOT NULL,
        allocated_credits INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
    `);
  }
  return db;
}

export function listPools(): CreditPool[] {
  const rows = getDb()
    .prepare(
      `SELECT id, name, total_credits as totalCredits, allocated_credits as allocatedCredits, created_at as createdAt
       FROM credit_pools
       ORDER BY id DESC`,
    )
    .all() as CreditPool[];
  return rows;
}

export function createPool(name: string, totalCredits: number): CreditPool {
  const result = getDb()
    .prepare(
      `INSERT INTO credit_pools (name, total_credits, allocated_credits)
       VALUES (?, ?, 0)`,
    )
    .run(name, totalCredits);

  return getDb()
    .prepare(
      `SELECT id, name, total_credits as totalCredits, allocated_credits as allocatedCredits, created_at as createdAt
       FROM credit_pools WHERE id = ?`,
    )
    .get(result.lastInsertRowid) as CreditPool;
}

export function allocateCredits(
  poolId: number,
  amount: number,
): CreditPool | null {
  const pool = getDb()
    .prepare(
      `SELECT id, name, total_credits as totalCredits, allocated_credits as allocatedCredits, created_at as createdAt
       FROM credit_pools WHERE id = ?`,
    )
    .get(poolId) as CreditPool | undefined;

  if (!pool) {
    return null;
  }

  const available = pool.totalCredits - pool.allocatedCredits;
  if (amount <= 0 || amount > available) {
    throw new Error("Invalid allocation amount");
  }

  getDb()
    .prepare(
      `UPDATE credit_pools SET allocated_credits = allocated_credits + ? WHERE id = ?`,
    )
    .run(amount, poolId);

  return getDb()
    .prepare(
      `SELECT id, name, total_credits as totalCredits, allocated_credits as allocatedCredits, created_at as createdAt
       FROM credit_pools WHERE id = ?`,
    )
    .get(poolId) as CreditPool;
}
