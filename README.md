# ChainGuard detector starter kit

Run your detector as an independent HTTP service. ChainGuard sends input to
`POST /detect`; this wrapper calls your algorithm and returns a `DetectionResult`.
It does not call ChainGuard's LLMs, fetchers, or backend.

## Run

Requires Python 3.10 or newer. Download/copy this entire folder, then run inside it:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

On Linux/macOS activate with `source .venv/bin/activate` instead.
Open http://127.0.0.1:9000/docs for the interactive API, or try:

```powershell
curl.exe -X POST http://127.0.0.1:9000/detect -H "Content-Type: application/json" --data-binary "@examples/context.json"
```

Use `curl` instead of `curl.exe` on Linux/macOS. The initial stub returns
`insufficient_evidence` with a message that no detector has been implemented.
`GET /health` returns `{"status":"ok"}` without executing the algorithm.

## Implement your detector

The only application code you need to edit is `detector.py`:

```python
from schema import AddressContext, DetectionResult

def detect(context: AddressContext) -> DetectionResult:
    # Invoke your algorithm and translate its output here.
    return DetectionResult(
        label="insufficient_evidence", risk_type="unknown",
        confidence=0.0, evidence=[],
    )
```

Add your detector's dependencies to `requirements.txt` and supply any model
weights or configuration it needs. Synchronous detector calls run in FastAPI's
worker thread pool. Your implementation should be safe for concurrent calls;
serialize access inside the adapter if your model requires it.

For a working demonstration, replace the contents of `detector.py` with:

```python
from examples.heuristic import detect
```

Restart the server and send `examples/context.json` again. It returns `scam`
with risk type `rug_pull` when an explicitly unverified contract has a pool
with zero liquidity and a recorded removal event. Otherwise it returns
`insufficient_evidence`. This is illustrative logic, not a validated model;
it does not establish the timing or percentage of a liquidity removal.

### Package or source code

Import your package inside `detector.py`, call it using `context.address`,
`context.chain`, or `context.model_dump()`, and map its native output to
`DetectionResult`. Map labels explicitly and convert percentage scores to
the 0–1 range. Do not assume every detector's score represents confidence.

### CLI tool

For a tool that accepts JSON on standard input and emits JSON on standard output:

```python
import json
import subprocess
from schema import AddressContext, DetectionResult

def detect(context: AddressContext) -> DetectionResult:
    result = subprocess.run(
        ["your-detector", "--json"],
        input=context.model_dump_json(), text=True,
        capture_output=True, check=True, timeout=30,
    )
    native = json.loads(result.stdout)
    # This direct validation works only if the CLI emits the standard schema.
    # Otherwise translate native fields/labels into DetectionResult here.
    return DetectionResult.model_validate(native)
```

Adapt command arguments to the actual tool. Use an argument list and keep
`shell=False` (the default). Failures/timeouts become HTTP 500, not a safe verdict.

### Standalone model

Load the model once in `detector.py`, preprocess the supplied context, run
inference in `detect()`, then translate its prediction and evidence to the
standard result. Document required weights, hardware, and dependencies in your
copy of this README. Python detector execution has no built-in hard timeout;
configure HTTP timeouts in the caller and bound expensive work in your adapter.

## Contract

`schema.py` defines the local Pydantic wire models; no ChainGuard package is
required. The request body is the context object itself, with no envelope.

- `address`: required nonblank string; `chain` defaults to `ethereum`.
- Optional context: `queried_at`, `contract`, `tx_history`, `tokens`, `liquidity`,
  and `fetcher_provenance`. `address_analysis` is also accepted for compatibility.
- Missing context sections default to empty collections. Missing or failed
  fetches are not proof that an address is safe; inspect provenance where needed.
- Result: `label` (`scam`, `not_scam`, or `insufficient_evidence`), `risk_type`,
  `confidence` (0–1), and `evidence` (items with `description` and `weight`, 0–1).
- Optional `explanation` supports detectors that supply their own rationale.
  When unset, it is omitted from HTTP output to preserve the core result shape.

Invalid requests return 422. Invalid detector results and execution exceptions
return a generic 500; diagnostic details go to the server log. A failed detector
is never silently converted into `not_scam` or `insufficient_evidence`.
The schemas are based on SPEC.md; coordinate future schema changes with
ChainGuard. Automatic shared-schema distribution is not part of this starter kit.

## Authentication and deployment

Authentication is optional. To require an API key, set it before starting:

```powershell
$env:DETECTOR_API_KEY = "replace-with-your-secret"
python app.py
```

Then send `X-API-Key` on `/detect` requests. Missing/wrong keys return 401.
The health endpoint and API docs remain public. Environment variables are read
directly; `.env` files are not automatically loaded.

`HOST` defaults to `127.0.0.1`; `PORT` defaults to `9000`. Set `HOST=0.0.0.0`
when the process must accept remote/container traffic. Deploy this folder with
its Python dependencies and detector assets; configure HTTPS at your hosting
service or reverse proxy. ChainGuard must be able to reach the deployed URL;
`localhost` refers to the caller's own machine/container.

## Configure in ChainGuard

`detector_config.json` is an example registration for the consuming app; the
wrapper does not read it. It starts disabled to avoid treating the stub as a
real detector. After deploying your implementation, register its endpoint in
ChainGuard and enable it:

```json
{
  "enabled": true,
  "name": "MyTemplateDetector",
  "endpoint": "http://127.0.0.1:9000/detect",
  "mode": "template",
  "required_input_type": "address_with_context",
  "is_llm_based": false
}
```

Use `required_input_type: "address"` if your detector only needs address/chain
and does its own lookups. Both use the same `/detect` request schema. Use
`is_llm_based: true` only when your detector supplies its own explanation.
Template mode needs no response mapping because the result follows the contract.
If API-key auth is enabled, the caller must send the configured `X-API-Key`.
Keep secrets in the caller's server-side configuration.

Existing external APIs can instead use ChainGuard's generic connector with
native parameters, authentication, and response mapping; they do not need this
wrapper. ChainGuard's outbound connector/admin configuration implementation is
a separate task. This starter kit does not add those capabilities to ChainGuard.
The previous `/analyse`, `/configuration`, and `/resolve-contract-address`
routes have been removed; input fetching/resolution belongs in the caller.

## External API wrapper examples: Honeypot and RugCheck

These examples illustrate response normalization behind the template API. For
an existing API, the intended default is for ChainGuard's **generic connector**
to call it directly using configured request/auth/response mappings. A wrapper
is useful if translation requires conditional logic the generic mapper cannot
express, or if you want one standard API contract. Both paths fit the architecture;
wrapping an existing API is optional. The generic connector is separate app work.

To try a wrapper, replace `detector.py` with **one** of these imports and restart:

```python
from examples.honeypot import detect
```

```python
from examples.rugcheck import detect
```

Install `requirements.txt` again if your environment does not have `httpx`.
Send a real **token** address to `/detect`, not a wallet address:

```json
{"address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "chain": "ethereum"}
```

For the RugCheck example, send a Solana token mint and explicitly use
`"chain": "solana"`. This does not add Solana resolution/fetchers to ChainGuard.
The Honeypot example intentionally supports Ethereum only, and sends `chainID=1`
instead of letting the provider guess the network. Configure either wrapper in
ChainGuard as `mode: template`, `required_input_type: address`,
`is_llm_based: false`; point the endpoint at **your wrapper's** `/detect` URL.

Mapping policy (inspect/change `map_result()` for your integration):

- Honeypot `isHoneypot: true` maps to `scam` / `honeypot`. False or missing maps
  to `insufficient_evidence`: absence of a honeypot is not absence of all scams.
  A verdict may exist even when simulation failed, so the adapter uses the
  explicit verdict rather than relying on `simulationSuccess` alone.
- RugCheck `danger` findings map to `scam` / `token_risk` by an **example local
  policy**, not a provider-confirmed scam/rug-pull verdict. Other findings remain
  `insufficient_evidence`; all risk descriptions and levels are kept as evidence.
- Neither adapter derives confidence from risk scores. `confidence` and evidence
  `weight` are `0.0` placeholders for unavailable values, not calibrated estimates.
  A future shared contract could represent unavailable confidence as `null`.
- HTTP errors, timeouts, invalid JSON and malformed fields raise exceptions,
  which the wrapper reports as HTTP 500. They are not successful safe verdicts.
  Unsupported chains/invalid address syntax also fail before a network request.

No prompts, JSON file writes, folder clearing, or network calls occur on import.
Provider references: [Honeypot API](https://docs.honeypot.is/ishoneypot) and
[RugCheck API schema](https://api.rugcheck.xyz/swagger/doc.json).

## Test

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
