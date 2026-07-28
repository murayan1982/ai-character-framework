\
# v5.4.0 REQ-5 Private Real-Provider Operator Acceptance

Status:

```text
REQ-4: ACCEPTED
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

## Purpose

REQ-5 is the operator-only checkpoint that proves the accepted REQ-4 runtime
against the actual OpenAI SDK and a real transcription request.

It must verify:

```text
private WAV outside repository
private credential outside repository
explicit real-execution confirmation
actual OpenAI SDK import
actual provider client creation
actual provider call
real transcript obtained
provider-neutral VoiceInputResult
public metadata redaction
private transcript/evidence outside repository
private staged WAV cleanup
repository clean before and after
```

The operator must not paste or commit the credential, private WAV path, raw
audio, complete transcript, provider request/response payload, exception
details, or private evidence path.

## Official provider shape

The accepted runtime uses:

```text
OpenAI(
    api_key=<explicit private credential>,
    timeout=<explicit seconds>,
    max_retries=<explicit count>,
)

client.audio.transcriptions.create(
    model=<explicit transcription model>,
    file=<audio.wav file object>,
    language=<optional ISO-639-1 language>,
)
```

The current official SDK transcription API accepts a file object and explicit
model, with optional language. The operator default model is
`gpt-4o-mini-transcribe`; the model remains overrideable.

## Private artifacts

The operator receives an original private WAV outside the repository. It copies
that WAV into a unique private evidence directory, executes against that staged
copy, and deletes only the staged copy after the call. The original WAV is not
deleted.

A successful run writes outside the repository:

```text
operator_evidence.json
private_transcript.txt
```

`operator_evidence.json` contains hashes, lengths, statuses, Framework public
metadata, SDK version, and cleanup markers. It does not contain the full
transcript, API key, audio bytes, or private absolute paths.

`private_transcript.txt` contains the real transcript and must remain private.

## Required confirmations

The real execution command requires these exact values:

```text
--confirm-real-provider-execution
I_ACCEPT_PRIVATE_REAL_PROVIDER_EXECUTION_AND_POSSIBLE_API_CHARGES

--confirm-private-data-outside-repo
I_WILL_KEEP_AUDIO_TRANSCRIPT_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY
```

The operator also refuses `OPENAI_LOG=debug`, because verbose provider logging
may contain request or response details.

## Source acceptance

Before any private call, run:

```text
python scripts/smoke_v540_openai_private_real_provider_operator_acceptance.py
python scripts/smoke_v540_openai_real_provider_runtime.py
```

These source checks do not import the actual OpenAI SDK, read credentials or
audio, create evidence, or execute a network request.

## Private operator acceptance

Install the optional SDK in the active private Python environment when needed:

```text
python -m pip install openai
python -c "import openai; print(openai.__version__)"
```

Set the API key in the current PowerShell process. Do not paste its value into
chat or commit it:

```text
$env:OPENAI_API_KEY = "<private value>"
```

Run the operator with absolute private paths outside the repository:

```text
python scripts/operator_v540_openai_private_real_provider_acceptance.py `
  --audio-path "<private absolute WAV path>" `
  --evidence-root "<private absolute evidence directory>" `
  --duration-ms <known duration> `
  --max-duration-ms 120000 `
  --max-audio-bytes 26214400 `
  --model "gpt-4o-mini-transcribe" `
  --language "ja" `
  --timeout-seconds 120 `
  --max-retries 0 `
  --confirm-real-provider-execution `
    "I_ACCEPT_PRIVATE_REAL_PROVIDER_EXECUTION_AND_POSSIBLE_API_CHARGES" `
  --confirm-private-data-outside-repo `
    "I_WILL_KEEP_AUDIO_TRANSCRIPT_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY"
```

The console prints only boolean/status markers and a random run ID. It does not
print private paths, transcript text, credential values, audio, or payloads.

Validate the resulting private `operator_evidence.json` locally:

```text
python scripts/verify_v540_openai_private_real_provider_evidence.py `
  --evidence-json "<private operator_evidence.json path>"
```

Only the validator's safe markers may be pasted for acceptance review.

## Stop rule

REQ-5 remains `IMPLEMENTED / NOT_ACCEPTED` until:

```text
source/operator smoke passes
REQ-1 through REQ-4 regression gates pass
actual SDK/client/provider execution succeeds
real transcript is obtained
private evidence validator passes
private staged WAV cleanup passes
repository remains clean
exact twelve-file diff check passes
explicit operator approval is given
```

Do not begin release readiness, DRC adoption, package creation, tagging, or
release before REQ-5 acceptance.
\

## Safe failed-run diagnostics

When a private provider call fails, the operator may print only these additional
fixed diagnostics:

```text
v540_req5_provider_runtime_status
v540_req5_provider_error_type
v540_req5_provider_http_status
```

These values are a Framework-owned status token, a fixed error category, and a
numeric HTTP status or `none`. The operator never prints the SDK exception
message, provider response body, request/response payload, request ID,
credential, private path, raw audio, or transcript.

After applying this repair, the source changes must be committed and the
worktree must be clean before another private operator attempt.

```text
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

## Accepted private real-provider checkpoint

A private operator run completed with the actual OpenAI SDK, an actual provider
client, real provider execution, a real transcript, and a provider-neutral
Framework result. The public-safe validator accepted the private evidence.

The API key, private WAV path, raw audio, provider payload, transcript text,
private evidence JSON, and private run details were not committed. Private
evidence remained outside the repository, private staged audio cleanup was
verified, the worktree remained clean before and after the run, the microphone
was not accessed, and DRC was not changed.

```text
v540_req5_private_evidence_status: accepted-by-validator
v540_req5_public_acceptance_sync_status: accepted
v540_req5_release_readiness_authorization: ready-for-next-small-commit
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```
