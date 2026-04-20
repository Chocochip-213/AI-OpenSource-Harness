# Backend (Spring) integration — _mcp-sandbox

> 1-page guide for the Spring team. Generated from `_template/exports/` —
> values come from `recipe.yaml`. Edit the template, not this file.

## TL;DR
1. Add env var `AI_GRADIO_URL=https://xxxx.gradio.live` to your config.
2. POST `{ "data": [<input>] }` to `${ AI_GRADIO_URL }/run/predict`.
3. Read `response.data[0]` as the AI output. Asset MIME: `application/json`.
4. When the URL changes (Colab restart), update the env var — Slack channel `#ai-endpoint`.

## Java client (RestTemplate — minimal)
```java
@RestController
@RequestMapping("/api/ai/_mcp-sandbox")
public class _mcp-sandboxController {

    @Value("${ai.gradio.url}")  // mapped from env: AI_GRADIO_URL
    private String gradioUrl;

    private final RestTemplate rest = new RestTemplate();

    @PostMapping
    public ResponseEntity<Object> predict(@RequestBody Map<String, Object> input) {
        if (gradioUrl == null || gradioUrl.isBlank()) {
            return ResponseEntity.status(503).body(Map.of(
                "error", "AI offline",
                "hint", "Set AI_GRADIO_URL env (Colab Gradio share URL)"
            ));
        }
        Map<String, Object> req = Map.of("data", List.of(input));
        try {
            Map<?,?> resp = rest.postForObject(gradioUrl + "/run/predict", req, Map.class);
            List<?> data = (List<?>) resp.get("data");
            return ResponseEntity.ok(data.isEmpty() ? null : data.get(0));
        } catch (RestClientException e) {
            // Most likely: stale Gradio share URL (Colab session ended).
            return ResponseEntity.status(502).body(Map.of(
                "error", "AI upstream failed",
                "detail", e.getMessage(),
                "hint", "AI_GRADIO_URL may be stale; ask AI team for the new URL"
            ));
        }
    }
}
```

`application.yml`:
```yaml
ai:
  gradio:
    url: ${AI_GRADIO_URL:}    # empty default → /api/ai/* returns 503 cleanly
```

## Request / Response contract
- **Schema**: `gradio_api.schema.json` (in this directory) — single source of truth.
- **Request**: Gradio always wraps positional inputs as `{"data": [arg1, arg2, ...]}`.
- **Response**: `{"data": [out1, out2, ...], "duration": <sec>, "is_generating": false}`.
- **MIME of payload values** matches `recipe.yaml:integration.asset_mime` (`application/json`).
- **Errors**: see "Failure modes the backend must handle" in `model_card.md`.

## Operational notes
- **Cold start** (first request after Colab restart): up to 60s. Set HTTP client read timeout ≥ 90s.
- **Gradio share URL TTL**: 72h or until Colab kernel dies. Whichever comes first.
- **URL refresh SOP**: AI team posts the new URL to `#ai-endpoint` Slack channel + updates the deployment env var. Backend retries failed requests once after a 30s delay (in case env var was just rotated).
- **Concurrency**: a single Gradio share serves requests serially (one Colab kernel). For load > 1 RPS, the Spring side should queue or scale to multiple Colab notebooks (one per AI team member).

## Testing without the AI online
Use the example assets in `exports/assets/` as canned responses:
```java
@MockBean RestTemplate rest;
when(rest.postForObject(any(), any(), any()))
    .thenReturn(Map.of("data", List.of(loadAsset("example_output.json"))));
```

## Pinning version
`recipe.yaml:version = 0.1.0`. When the AI team bumps this, they:
1. Post the new `gradio_api.schema.json` diff to `#ai-endpoint`
2. Tag the AI repo (e.g. `_mcp-sandbox-v0.1.0`)
3. Spring team updates client code if the schema changed (most version bumps don't)
