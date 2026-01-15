"use client";

import React from "react";
import { useSearchParams } from "next/navigation";

export default function HomeClient() {
  const searchParams = useSearchParams();

  return (
    <main style={{ padding: 24 }}>
      <h1>OSS Scout</h1>
      <p>Deployed successfully. Query params:</p>
      <pre>{JSON.stringify(Object.fromEntries(searchParams.entries()), null, 2)}</pre>
    </main>
  );
}
