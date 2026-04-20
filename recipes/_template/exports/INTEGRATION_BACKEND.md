# Backend (Spring) integration — {RECIPE_NAME}

> 1-page guide for the Spring team. Generated from `_template/exports/` —
> values come from `recipe.yaml`. Edit the template, not this file.

## TL;DR
1. Add env var `{BACKEND_ENV_VAR}=https://xxxx.gradio.live` to your config.
2. POST `{ "data": [<input>] }` to `${ {BACKEND_ENV_VAR} }/call/predict` — returns an `event_id`.
3. GET `${ {BACKEND_ENV_VAR} }/call/predict/<event_id>` (SSE) and read the final
   `process_completed` event: `output.data[0]` is the AI result. Asset MIME: `{ASSET_MIME}`.
4. When the URL changes (Colab restart), update the env var — team channel `{TEAM_CHANNEL}`.

> **Protocol note** — Colab ships Gradio 5.x, which replaced the legacy
> `POST /run/predict` one-shot endpoint with a **two-step queued call**:
> `POST /call/predict` → `event_id` → `GET /call/predict/<event_id>` (SSE
> stream). The Spring side has to follow the SSE stream until it sees
> `event: complete` / `msg: process_completed`.

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
                .uri(base + "/call/predict")
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
            .uri(base + "/call/predict/" + eventId)
            .accept(MediaType.TEXT_EVENT_STREAM)
            .retrieve()
            .body(String.class);
        // Gradio SSE payload ends with a line: data: {"msg":"process_completed","output":{"data":[...]}}
        for (String line : body.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            String json = line.substring(6).trim();
            if (json.contains("\"process_completed\"")) {
                Map<?, ?> evt = JsonMapper.builder().build().readValue(json, Map.class);
                Map<?, ?> out = (Map<?, ?>) evt.get("output");
                List<?> data = (List<?>) out.get("data");
                return data.isEmpty() ? null : data.get(0);
            }
        }
        throw new IllegalStateException("Gradio SSE ended without process_completed");
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
- **Request**: `POST /call/predict` with body `{"data": [arg1, arg2, ...]}`.
- **Intermediate**: server replies `{"event_id": "<uuid>"}` immediately.
- **Final**: follow `GET /call/predict/<event_id>` SSE until `msg: process_completed`. Final output is `output.data[0..N]`.
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
