# Frontend (Next.js) integration — {RECIPE_NAME}

> 1-page guide for the Next.js team. **You only call the Spring backend** —
> the Gradio URL stays server-side and frontend never knows about it.

## TL;DR
1. Backend exposes `POST /api/ai/{RECIPE_NAME}` (request/response in
   `gradio_api.schema.json` `request`/`response.output.data[0]` shapes).
2. Asset MIME of the payload value: `{ASSET_MIME}`.
3. While AI is offline, backend returns 503 — show a friendly placeholder.

## TypeScript types (hand-written; keep in sync with `gradio_api.schema.json`)
```typescript
// types/{RECIPE_SNAKE_NAME}.ts
export type {RECIPE_CLASS_NAME}Input = {
  // TODO recipe author: replace with your real input shape.
  // Example: prompt: string; max_tokens?: number;
};

export type {RECIPE_CLASS_NAME}Output = {
  // TODO recipe author: replace with your real output shape.
  // Example: result_url: string; duration_sec: number;
};
```

(Optional: generate these automatically from `gradio_api.schema.json` via
`npx openapi-typescript` if you ever switch to OpenAPI.)

## Fetch wrapper
```typescript
// lib/ai-client.ts
import type {
  {RECIPE_CLASS_NAME}Input,
  {RECIPE_CLASS_NAME}Output,
} from "@/types/{RECIPE_SNAKE_NAME}";

export async function predict{RECIPE_CLASS_NAME}(
  input: {RECIPE_CLASS_NAME}Input,
  signal?: AbortSignal,
): Promise<{RECIPE_CLASS_NAME}Output> {
  let res: Response;
  try {
    res = await fetch("/api/ai/{RECIPE_NAME}", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new Error(`Network error: ${(e as Error).message}`);
  }
  if (res.status === 503) {
    throw new Error("AI service offline. Try again in a few minutes.");
  }
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`AI request failed (${res.status}): ${detail}`);
  }
  return res.json() as Promise<{RECIPE_CLASS_NAME}Output>;
}
```

> **Note** — `res.json()` is untyped at runtime; the `as Promise<...>`
> cast is a type hint only. If the schema tightens, consider validating
> the response with `zod` so runtime drift surfaces as an error rather
> than `undefined.someField`.

## React component skeleton
```tsx
// components/{RECIPE_CLASS_NAME}Result.tsx
"use client";
import { useState } from "react";
import type {
  {RECIPE_CLASS_NAME}Input,
  {RECIPE_CLASS_NAME}Output,
} from "@/types/{RECIPE_SNAKE_NAME}";
import { predict{RECIPE_CLASS_NAME} } from "@/lib/ai-client";

export function {RECIPE_CLASS_NAME}Result() {
  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState<{RECIPE_CLASS_NAME}Output | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(input: {RECIPE_CLASS_NAME}Input) {
    setLoading(true);
    setError(null);
    try {
      setOutput(await predict{RECIPE_CLASS_NAME}(input));
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  // ... render based on output / loading / error
}
```

## Asset rendering (pick the branch matching your recipe's `integration.asset_mime`)

This recipe uses: `{ASSET_MIME}`. Pick the corresponding branch below.

**`model/gltf-binary` (GLB, glTF Binary)** — use `<model-viewer>` web component or
`@react-three/fiber` + `@react-three/drei` GLTF loader. Backend can return either:
- The URL of a stored GLB file → `<model-viewer src={url} />`
- Base64-encoded GLB inline → decode + `URL.createObjectURL(new Blob([bytes]))`

**`image/png` / `image/jpeg`** — standard `<img src={url} alt="..." />`, or
`<Image src={url} width={512} height={512} alt="..." />` from `next/image`
(note: `width` and `height` are required unless you use `fill`).

**`application/json`** — render fields directly. No binary decoding needed.
Good fit for structured predictions (labels, scores, bounding boxes).

**`video/mp4` / `audio/wav`** — standard HTML `<video>` / `<audio>` elements
pointing at the URL, or stream via `MediaSource` for large files.

## When the AI endpoint is offline (very common during demos)
Backend returns 503. Show:
```tsx
<div className="ai-offline">
  AI service is restarting. Try again in a minute.
  {/* optional: fallback static example using exports/assets/example_output.* */}
</div>
```
Do NOT retry automatically (could spam the AI team during their cold-start work).

## Local dev without the AI
Easiest: backend developer runs Spring with `{BACKEND_ENV_VAR}=` empty → all
calls return 503 with a clear message. The frontend can still develop the
loading/error/empty states.

If you need real data shapes for development, use `exports/assets/example_output.{json|png|glb}`
as a static stub — same contract, no AI required.
