# Course Compass offline serving benchmark

On 16 November 2026 a Docker rehearsal served all 212 requests without a transport, schema-mode or HTTP failure. At concurrency four, first-pass p95 was 8.86 ms. This is a short, single-host measurement of the offline v3 API. The workload is too small to estimate sustained capacity.

## Workload and environment

A client on the same Ubuntu GitHub Actions runner sent all 53 versioned curriculum questions to `POST /ask` over HTTP. The service ran one Uvicorn process with 2 CPUs and 2 GiB of container memory. The runner exposed four logical CPUs on AMD EPYC 9V45 hardware and about 15.6 GiB of RAM. Each concurrency level started with a fresh service process. A call to `/stats` loaded the corpus before timing. Each first pass was followed immediately by the same questions in the same order. The client recorded wall time through response decoding and used nearest-rank p95.

| Concurrent clients | Pass | Requests | p95 (ms) | Requests/s | Errors |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | first pass | 53 | 2.13 | 555.39 | 0 |
| 1 | repeat pass | 53 | 2.10 | 567.91 | 0 |
| 4 | first pass | 53 | 8.86 | 638.57 | 0 |
| 4 | repeat pass | 53 | 8.33 | 635.20 | 0 |

Each pass produced 45 extractive answers and 8 abstentions. The benchmark checks response modes. Answer quality has a [separate evaluation](../eval/RESULTS.md). Model API spend was $0 because the service ran without a provider key. Runner compute cost was unmeasured. Each pass took less than one second, so the throughput figures describe this burst only. A deployment serving remote users or invoking an LLM needs its own measurements.

## Rollback exercise

The rehearsal served the same programme question on a single loopback port before rollout, after the candidate started and after restoring the previous image by its Docker image ID. The previous API reported version 2.0.0 and returned a sourced preview. The candidate reported 3.0.0 and returned a sourced extractive answer. The restored API reported 2.0.0 and returned a sourced preview again. This exercise used sequential local container replacements with a short service interruption.

## Reproduce

Use a checkout with full Git history, Docker, Bash, curl and Python 3. From the repository root run `bash scripts/rehearse_offline_release.sh`. The script builds the previous and candidate revisions, records the machine details and cleans up its containers. The historical run used previous revision `56814adc` and candidate merge revision `80198e52`. Dependency ranges and the base image may resolve differently on a later run.

[GitHub Actions run and output artifact](https://github.com/Jeeson-Kurian/university-rag-chatbot/actions/runs/43970265039) · [Benchmark client](../scripts/benchmark_offline.py) · [Rollout and rollback script](../scripts/rehearse_offline_release.sh)
