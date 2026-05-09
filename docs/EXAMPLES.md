# Hermes Continuation Examples

## Basic handoff

```bash
hermes-handoff create --repo . --goal "Ship handoff MVP" --next "Run pytest and inspect output"
```

## Development handoff with boundaries

```bash
hermes-handoff create   --repo .   --goal "Finish dashboard QA"   --completed "Implemented health card"   --verified "unit tests passed"   --not-run "browser smoke"   --blocker "LLM provider latency still unknown"   --do-not-touch "billing migrations"   --next "Run build and browser smoke"
```

## Fresh-session usage

Open the generated Markdown file and paste the `Resume Prompt` section into a new Hermes session.
