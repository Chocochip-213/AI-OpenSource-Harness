# Backend (Spring) integration — {RECIPE_NAME}

> 1-page guide for the Spring team. Generated from `_template/exports/` —
> values come from `recipe.yaml`. Edit the template, not this file.

## TL;DR
1. Add env var `{BACKEND_ENV_VAR}=https://xxxx.gradio.live` to your config.
2. POST `{ "data": [<input>] }` to `${ {BACKEND_ENV_VAR} }/gradio_api/call/predict` — returns an `event_id`.
3. GET `${ {BACKEND_ENV_VAR} }/gradio_api/call/predict/<event_id>` (SSE) until `event: complete`;
   parse `data:` JSON array. For image/file outputs, `data[0].url` is the downloadable asset URL.
   Asset MIME: `{ASSET_MIME}`.
4. When the URL changes (Colab restart), update the env var — team channel `{TEAM_CHANNEL}`.

> **Protocol note** — Colab ships Gradio 5.x, which moved every API
> path under a `/gradio_api/` prefix (see `GET /config → api_prefix`).
> The canonical queued call is:
> `POST /gradio_api/call/predict` → `{"event_id": "..."}`
> `GET  /gradio_api/call/predict/<event_id>` → SSE stream, terminate on `event: complete`.
> The legacy Gradio 3.x `/run/predict` one-shot and Gradio 4.x `/call/predict` (no
> prefix) both 404 on 5.x — re-use old code carefully.

> **Response shape** — for image/file outputs, `data` is a list of objects
> shaped `{path, url, size, orig_name, mime_type, is_stream, meta}`. The
> backend fetches `url` (a second HTTP GET to the Gradio file server at
> `{share}/gradio_api/file=...`) to obtain the actual bytes. For JSON /
> text outputs, `data[i]` is the primitive / dict directly.

## Java client (Spring Boot 3.2+ `RestClient`)
```java
@RestController
@RequestMapping("/api/ai/{RECIPE_NAME}")
public class {RECIPE_CLASS_NAME}Controller {

    @Value("${ai.gradio.url:}")
    private String gradioUrl;

    private final RestClient rest = RestClient.create();

    @PostMapping
    public ResponseEntity<Object> predict(@RequestBody Map<String, Object> input) {
        if (gradioUrl == null || gradioUrl.isBlank()) {
            return ResponseEntity.status(503).body(Map.of("error", "AI offline"));
        }
        String base = gradioUrl.endsWith("/")
            ? gradioUrl.substring(0, gradioUrl.length() - 1)
            : gradioUrl;
        try {
            Map<?, ?> started = rest.post()
                .uri(base + "/gradio_api/call/predict")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("data", List.of(input)))
                .retrieve()
                .body(Map.class);
            String eventId = (String) started.get("event_id");

            // Follow SSE until the completion event. For production, prefer
            // a reactive WebClient + Flux<ServerSentEvent> consumer. This
            // synchronous polling is fine for low-RPS demos.
            Object output = pollEventStream(base, eventId);
            return ResponseEntity.ok(output);
        } catch (RestClientException e) {
            return ResponseEntity.status(502).body(Map.of(
                "error", "AI upstream failed",
                "detail", e.getMessage()
            ));
        }
    }

    private Object pollEventStream(String base, String eventId) {
        String body = rest.get()
            .uri(base + "/gradio_api/call/predict/" + eventId)
            .accept(MediaType.TEXT_EVENT_STREAM)
            .retrieve()
            .body(String.class);
        // Gradio 5.x SSE terminates with:
        //   event: complete
        //   data: [<output_0>, <output_1>, ...]
        // For image outputs, <output_i> is {path, url, size, orig_name, mime_type, ...};
        // the caller usually does a second GET on .url to retrieve the bytes.
        String[] lines = body.split("\n");
        String pendingEvent = null;
        for (String line : lines) {
            if (line.startsWith("event: ")) {
                pendingEvent = line.substring(7).trim();
            } else if (line.startsWith("data: ") && "complete".equals(pendingEvent)) {
                String json = line.substring(6).trim();
                List<?> data = JsonMapper.builder().build().readValue(json, List.class);
                return data.isEmpty() ? null : data.get(0);
            } else if (line.isEmpty()) {
                pendingEvent = null;
            }
        }
        throw new IllegalStateException("Gradio SSE ended without event: complete");
    }
}
```

> **Legacy note** — If you are on Spring Boot 3.1 or earlier, `RestClient`
> is not yet available — use `WebClient` (reactive) or the now-deprecated
> `RestTemplate`. For reactive backpressure with long-running inferences,
> `WebClient.get().retrieve().bodyToFlux(ServerSentEvent.class)` is the
> idiomatic choice.

`application.yml`:
```yaml
ai:
  gradio:
    url: ${{BACKEND_ENV_VAR}:}    # empty default -> /api/ai/* returns 503 with a clear error body
```

> **SSAFY note** — if the harness sits at `<repo>/ai/`, put the non-empty
> value in `application-prod.yml` only; keep `application-local.yml`'s
> `ai.gradio.url` empty so local dev returns 503 without hitting the
> (possibly-expired) Colab share URL.

## Request / Response contract
- **Schema**: `gradio_api.schema.json` (in this directory) — single source of truth.
- **Request**: `POST /gradio_api/call/predict` with body `{"data": [arg1, arg2, ...]}`.
- **Intermediate**: server replies `{"event_id": "<uuid>"}` immediately.
- **Final**: follow `GET /gradio_api/call/predict/<event_id>` SSE until `event: complete`; parse the `data:` line as JSON array. For file/image outputs each element is `{path, url, size, orig_name, mime_type, is_stream, meta}` — GET `url` to download the asset bytes.
- **MIME of payload values** matches `recipe.yaml:integration.asset_mime` (`{ASSET_MIME}`).
- **Errors**: see "Failure modes the backend must handle" in `model_card.md`.

## Operational notes
- **Cold start** (first request after Colab restart): up to 60s. Set HTTP client read timeout ≥ 90s.
- **Gradio share URL TTL**: 72h or until Colab kernel dies. Whichever comes first.
- **URL refresh procedure**: AI team posts the new URL to `{TEAM_CHANNEL}` + updates the deployment env var. Backend retries failed requests once after a 30s delay.
- **Concurrency**: a single Gradio share serves requests serially (one Colab kernel). For load > 1 RPS, queue on the Spring side or run multiple Colab notebooks.

## Testing without the AI online
Use the example assets in `exports/assets/` as canned responses. Spring Boot 3.4+ uses `@MockitoBean`; older versions use the now-deprecated `@MockBean`:
```java
@MockitoBean RestClient rest;
when(rest.post().uri(anyString()).contentType(any()).body(any()).retrieve().body(Map.class))
    .thenReturn(Map.of("data", List.of(loadAsset("example_output.json"))));
```

## Pinning version
`recipe.yaml:version = {RECIPE_VERSION}`. When the AI team bumps this, they:
1. Post the new `gradio_api.schema.json` diff to `{TEAM_CHANNEL}`
2. Tag the AI subtree (e.g. `{RECIPE_NAME}-v{RECIPE_VERSION}`) — GitLab tag if this lives in a SSAFY monorepo at `<repo>/ai/`
3. Spring team updates client code if the schema changed (most version bumps don't)
