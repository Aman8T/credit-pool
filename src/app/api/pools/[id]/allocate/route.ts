import { allocateCredits } from "@/lib/db";
import { NextResponse } from "next/server";

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const poolId = Number(id);
  const body = (await request.json()) as { amount?: number };
  const amount = body.amount;

  if (!Number.isInteger(poolId) || typeof amount !== "number") {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }

  try {
    const pool = allocateCredits(poolId, amount);
    if (!pool) {
      return NextResponse.json({ error: "Pool not found" }, { status: 404 });
    }
    return NextResponse.json({ pool });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Allocation failed";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
