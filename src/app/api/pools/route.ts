import { createPool, listPools } from "@/lib/db";
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ pools: listPools() });
}

export async function POST(request: Request) {
  const body = (await request.json()) as {
    name?: string;
    totalCredits?: number;
  };

  const name = body.name?.trim();
  const totalCredits = body.totalCredits;

  if (!name || typeof totalCredits !== "number" || totalCredits <= 0) {
    return NextResponse.json(
      { error: "Name and positive totalCredits are required" },
      { status: 400 },
    );
  }

  const pool = createPool(name, totalCredits);
  return NextResponse.json({ pool }, { status: 201 });
}
