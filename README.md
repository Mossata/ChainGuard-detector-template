# ChainGuard external detector template

Turn your detection algorithm into a separate service that ChainGuard can call. ChainGuard sends an Ethereum address and, optionally, blockchain evidence to `POST /detect`; this template runs your code and returns a validated risk assessment.

**The initial detector is a placeholder.** It always returns `insufficient_evidence` with confidence `0.0`. Starting the server proves the interface works, not that it can detect scams. Implement your algorithm before relying on its results.

This template is separate from the [local LLM hosting template](../ChainGuard-localLLM-template/README.md), which runs models for ChainGuard's AI agents. You can use either or both. An external detector does not replace the AI provider that interprets chat requests.

## What you need

- This complete repository, including `app.py`, `detector.py`, `schema.py`, and the dependency files.
- Either Docker, or Python 3.12 (matching the Docker image; Python 3.10+ is supported by this template).
- A running ChainGuard app when you are ready to connect it. See the [main app guide](../ChainGuard/README.md).

An **API** lets programs exchange requests. An **endpoint** is its URL. The detector endpoint ends in `/detect`; `/health` checks that the server is alive, and `/docs` provides an interactive test page. A **schema** defines the fields a request or response must contain.

Commands use Windows PowerShell. On macOS/Linux, use `.venv/bin/python` instead of `.venv\Scripts\python`, and `curl` instead of `curl.exe`.

## 1. Start the detector

If you do not have the repository yet, run these commands from your projects folder:

```powershell
git clone https://github.com/Mossata/ChainGuard-detector-template.git
cd ChainGuard-detector-template
```

### With ChainGuard's Docker setup

If you followed ChainGuard's Docker guide, this service is already started. Keep the repositories beside one another:

```text
ProjectFiles/
  ChainGuard/
  ChainGuard-detector-template/
```

ChainGuard's root `.env` should contain `DETECTOR_PATH=../ChainGuard-detector-template`. Run from `ChainGuard/`:

```powershell
docker compose up -d --build
docker compose ps
```

ChainGuard builds the detector from this repository's Dockerfile and mounts its source at `/app`. You do not need another detector process on port 9000.

### Without Docker

Open a terminal in `ChainGuard-detector-template/`:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Keep the terminal running. The default address is `http://127.0.0.1:9000`. No activation script is required because the commands use the environment's Python directly.

### Standalone Docker alternative

To run only the detector, from this repository:

```powershell
docker build -t chainguard-detector .
docker run --rm --name chainguard-detector -p 127.0.0.1:9000:9000 chainguard-detector
```

Keep the terminal running. This image contains a copy of the source; rebuild it after changes. Do not run this alongside another service already using port 9000.

## 2. Check the interface

Open **http://127.0.0.1:9000/health**. Expect `{"status":"ok"}`. This does not execute the algorithm.

In a second terminal in the template folder, send the included example evidence:

```powershell
curl.exe -X POST http://127.0.0.1:9000/detect -H "Content-Type: application/json" --data-binary "@examples/context.json"
```

The unchanged template returns:

```json
{
  "label": "insufficient_evidence",
  "risk_type": "unknown",
  "confidence": 0.0,
  "evidence": []
}
```

Alternatively, open **http://127.0.0.1:9000/docs**, expand **POST /detect**, click **Try it out**, enter a request, and click **Execute**. Opening `/detect` directly in a browser sends GET and returns 405; it needs POST.

## 3. Implement your detector

Edit **`detect_custom()` in `detector.py`**. It receives an `AddressContext` object containing the address and available evidence. Call your Python package, local model, or other algorithm there and translate its result into `DetectionResult`:

```python
from schema import AddressContext, DetectionResult


def detect_custom(context: AddressContext) -> DetectionResult:
    # Replace this placeholder with your algorithm and map its output.
    return DetectionResult(
        label="insufficient_evidence",
        risk_type="unknown",
        confidence=0.0,
        evidence=[],
    )
```

Add required packages to `requirements.txt` and supply any model weights/configuration your algorithm needs. Map labels explicitly; convert percentage confidence to the 0–1 range only if it actually represents confidence. Missing or failed evidence is not proof of safety.

For an immediate demonstration, replace the `detect_custom()` function definition with this import, leaving the `detect()` dispatcher in place:

```python
from examples.heuristic import detect as detect_custom
```

Restart and resend `examples/context.json`. The example reports `scam` / `rug_pull` when the context explicitly identifies an unverified contract and a zero-liquidity pool with a recorded removal event. Otherwise it reports insufficient evidence. This is illustrative logic, not a validated model or proof of a rug pull's timing or size.

### Apply code and dependency changes

For ChainGuard-managed Docker, run from `ChainGuard/`:

```powershell
docker compose restart detector
```

Source is mounted, but automatic Python reload is off. If requirements changed, use `docker compose up -d --build detector` instead. When ChainGuard uses the local LLM shared-network override, include the same two `-f` options used to start it.

For native use, press Ctrl+C and start the server again; reinstall requirements when dependencies change. For standalone Docker, rebuild and rerun the image. To develop with a standalone source mount instead:

```powershell
docker run --rm --name chainguard-detector -p 127.0.0.1:9000:9000 --mount "type=bind,source=$($PWD.Path),target=/app" chainguard-detector
```

This PowerShell command mounts the current template folder. On macOS/Linux, replace the `--mount` argument with `-v "$PWD:/app"`. Restart the container after edits.

## 4. Connect to ChainGuard

Start ChainGuard and sign in as admin. Open **Settings > External Detector** and enter:

| Field | Value |
| --- | --- |
| Enabled | On |
| Name | Any descriptive name, such as `My template detector` |
| Endpoint | Choose the URL below for your setup |
| Mode | `template` |
| Required Input Type | `address_with_context` if you need ChainGuard's fetched evidence |
| LLM Based | Off for a normal algorithm; on only for an LLM detector supplying its own explanation |

| Where services run | Endpoint seen by the ChainGuard backend |
| --- | --- |
| ChainGuard's Compose stack, including its detector service | `http://detector:9000/detect` |
| Both natively on the same computer | `http://127.0.0.1:9000/detect` |
| Docker backend, detector on the host | `http://host.docker.internal:9000/detect` (detector must accept connections from Docker) |
| Remote detector | Your reachable HTTPS URL ending in `/detect` |

Inside a Docker container, `localhost` means that container, not your computer or another service. Native `app.py` binds to loopback by default; set `HOST=0.0.0.0` before startup if it must accept Docker/remote connections, and configure network access appropriately.

Click **Save Changes**, then **Confirm Change**. Saving registers the endpoint; it does not start or test it. Ask ChainGuard to assess a complete Ethereum address and inspect the result and service logs. The unchanged stub still reports insufficient evidence.

Choose `address` as the required input type only if your implementation performs its own lookups. Leave mode on `template`; ChainGuard's generic request/response mapping is not implemented. To return to the built-in AI Scam Checker, disable the external detector and save/confirm. Stopping the detector alone causes errors while it remains configured.

`detector_config_example.json` illustrates registration for **ChainGuard**; this wrapper does not read it. Prefer the web settings so ChainGuard saves to the correct location (its Docker data volume or native backend configuration file).

## Optional authentication and configuration

By default, detector requests require no key. To enable authentication for a native run, set a secret in the detector terminal **before startup**:

```powershell
$env:DETECTOR_API_KEY = "replace-with-your-own-secret"
.venv\Scripts\python app.py
```

Set the same key in ChainGuard's backend environment or under **Settings > API Wrappers > Detector API Key**. The backend sends `X-API-Key`. For a manual test, add `-H "X-API-Key:YOUR_SECRET"` to the curl command. In `/docs`, use **Authorize** to enter it.

With ChainGuard's Compose setup, root `.env` `DETECTOR_API_KEY` is passed to both services. Reapply `docker compose up -d` after changing it. Standalone Docker requires passing environment variables explicitly, for example with `--env-file` referencing a private file you create. Do not bake secrets into images or registration JSON.

| Detector environment variable | Default / purpose |
| --- | --- |
| `HOST` | `127.0.0.1` natively; the Docker image sets `0.0.0.0`. |
| `PORT` | `9000`. |
| `DETECTOR_API_KEY` | Empty: authentication disabled. Protects `/detect`; `/health` and `/docs` remain public. |
| `DETECTOR_MODE` | `custom`: calls `detect_custom()`. `llm` selects the forwarding adapter below. |
| `LLM_DETECTOR_ENDPOINT` | Required in `llm` mode: upstream URL accepting context and returning a detector result. |
| `LLM_DETECTOR_API_KEY` | Optional upstream `X-API-Key`; separate from the key protecting this service. |
| `LLM_DETECTOR_TIMEOUT` | Upstream request timeout in seconds; default `30`. |

Native runs do not automatically load `.env` files. On macOS/Linux, use `export NAME='value'` instead of `$env:NAME = "value"`. ChainGuard's Compose file passes only its listed environment entries; add detector environment entries or an override file for settings beyond its existing `HOST`, `PORT`, and `DETECTOR_API_KEY`.

## Other integration examples

### Your own LLM or Lambda endpoint

The optional adapter forwards context to a detector endpoint you operate. This is a detector-result API, **not** a raw OpenAI-compatible chat endpoint and not the local LLM hosting template.

For native use, configure before startup:

```powershell
$env:DETECTOR_MODE = "llm"
$env:LLM_DETECTOR_ENDPOINT = "https://your-service.example.com/detect"
$env:LLM_DETECTOR_TIMEOUT = "30"
# Set LLM_DETECTOR_API_KEY too if the upstream endpoint requires X-API-Key.
.venv\Scripts\python app.py
```

The upstream receives the same `AddressContext` JSON and must return a `DetectionResult`, including an explanation for ChainGuard's LLM-based handling. `examples/lambda_handler.py` illustrates API Gateway event handling; implement its `invoke_user_llm()` function and authenticate the deployed endpoint separately. Register **this wrapper's `/detect` URL** in ChainGuard and turn **LLM Based** on. Upstream failures do not fall back to the custom stub.

### Packages, CLI tools, and local models

Import a package or load a model once in `detector.py`, call it from `detect_custom()`, and translate its output. For a CLI, use `subprocess.run()` with an argument list, JSON input/output, `check=True`, an explicit timeout, and the default `shell=False`. Keep weights and deployment requirements documented in your fork.

### Honeypot and RugCheck adapters

To try one example, replace the `detect_custom()` definition with **one** import, preserving the dispatcher:

```python
from examples.honeypot import detect as detect_custom
```

Or:

```python
from examples.rugcheck import detect as detect_custom
```

Restart the service. These adapters call live third-party APIs and need internet access. Register as `template`, required input `address`, and LLM Based off.

- **Honeypot:** requires an Ethereum token contract, not a wallet, and sends chain ID 1. An explicit honeypot verdict maps to `scam` / `honeypot`; false or missing maps to insufficient evidence, since other scams are not ruled out.
- **RugCheck:** requires a Solana token mint and `chain: solana`. Danger findings map to `scam` / `token_risk` by the example's local policy, not a provider-confirmed scam verdict. This example does not add Solana fetching or resolution to ChainGuard.
- Both keep numeric confidence and evidence weights at `0.0` as placeholders for unavailable confidence, not calibrated estimates. Review `map_result()` before adopting either policy. HTTP failures and malformed responses are errors, not safe verdicts.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Port 9000 already used | Stop the other detector process or change your published/native port and ChainGuard endpoint together. |
| Health works, detection fails | Health only checks the process. Send the example POST and inspect the server log. |
| 401 on `/detect` | Match `DETECTOR_API_KEY` on caller and server; include `X-API-Key` in manual requests. |
| 422 | Request does not match `AddressContext`; send the context object directly, without a wrapper. |
| 500 | Algorithm exception, invalid result, or upstream error; inspect the detector terminal/container log. |
| Code edits have no effect | Restart the process; rebuild dependencies or standalone images when required. |
| ChainGuard cannot connect | Use a URL reachable from the backend, including the correct Docker service/host address. |
| Always insufficient evidence | Implement the placeholder, or check whether your algorithm has enough input evidence. |

For ChainGuard Docker logs, run `docker compose logs --tail 100 detector backend` from `ChainGuard/`, using any override files from your startup command.

## Testing and architecture

From this template folder:

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

Create the environment as in the native setup if needed. The current tests cover wrapper health/default detection, external API mappings, chain validation, and upstream failures using mocked requests. Use the example POST above to check the running wrapper and a ChainGuard scam request to check the full integration.

```text
ChainGuard -> POST /detect -> validate AddressContext
  -> detector.detect()
       custom mode -> detect_custom() -> your algorithm
       llm mode    -> your upstream detector endpoint
  -> validate DetectionResult -> return JSON
```

`schema.py` is the local wire contract; no ChainGuard Python package is required. Coordinate schema changes with the consuming app.

| Model | Fields |
| --- | --- |
| `AddressContext` | Required nonblank `address`; `chain` defaults to `ethereum`. Optional `queried_at`, `address_analysis`, `contract`, `tx_history`, `tokens`, `liquidity`, and `fetcher_provenance`. Missing evidence collections default to empty. |
| `DetectionResult` | `label`: `scam`, `not_scam`, or `insufficient_evidence`; nonblank `risk_type`; finite `confidence` from 0–1; `evidence`: objects with nonblank `description` and finite `weight` from 0–1; optional `explanation`. |

Invalid requests return 422. Execution failures or invalid results return a generic 500 with diagnostic details in the server log. Unset explanations are omitted from responses. The service has `/health`, `/detect`, and `/docs`; there are no `/analyse`, `/configuration`, or `/resolve-contract-address` routes.

Synchronous detection runs in FastAPI's worker thread pool. Make your implementation safe for concurrent calls. Python algorithm execution has no built-in hard timeout; bound expensive work in your adapter. ChainGuard's current detector HTTP client waits up to 60 seconds. For remote hosting, configure HTTPS and access controls at your deployment boundary.
