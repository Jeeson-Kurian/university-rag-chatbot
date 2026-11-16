#!/usr/bin/env bash
# Run from a clean repository checkout with Docker, curl, git and Python 3.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
previous=56814adc71f47ca3d4c95a19175f13d2865e25fd
candidate=$(git rev-parse HEAD)
previous_id=""
candidate_id=""
restored_id=""
cleanup() {
  if [[ -n "$restored_id" ]]; then docker rm -f "$restored_id" >/dev/null; fi
  if [[ -n "$candidate_id" ]]; then docker rm -f "$candidate_id" >/dev/null; fi
  if [[ -n "$previous_id" ]]; then docker rm -f "$previous_id" >/dev/null; fi
}
trap cleanup EXIT

build_image() {
  git archive "$1" | docker build --quiet --label "org.opencontainers.image.revision=$1" -
}

start_image() {
  docker run -d --cpus 2 --memory 2g -e OPENAI_API_KEY= -p "127.0.0.1:$2:8000" "$1"
}

wait_for_health() {
  for ((attempt = 0; attempt < 45; attempt++)); do
    if curl --max-time 2 -fs "$base/health" >/dev/null; then return 0; fi
    sleep 1
  done
  echo "Service did not become ready at $base/health" >&2
  for id in "$previous_id" "$candidate_id" "$restored_id"; do
    if [[ -n "$id" ]]; then docker logs --tail 15 "$id" >&2; fi
  done
  return 1
}

check_api() {
  local phase="$1" expected="$2" mode="$3" actual
  wait_for_health
  actual=$(curl -fsS "$base/openapi.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])')
  test "$actual" = "$expected"
  curl -fsS --max-time 60 -H 'Content-Type: application/json' \
    -d '{"question":"How many ECTS credits does the Master programme in Artificial Intelligence and Cybersecurity comprise?","department":"AIandCybersecurity"}' "$base/ask" |
    python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"] == sys.argv[1] and r["answer"].strip() and r["sources"][0]["department"] == "AIandCybersecurity" and r["sources"][0]["excerpt"].strip(), "curriculum smoke query failed"' "$mode"
  echo "$phase: API version $actual served the curriculum smoke query"
}

echo "Host CPU: $(uname -m), $(getconf _NPROCESSORS_ONLN) online logical CPUs"
if command -v lscpu >/dev/null; then lscpu | grep -E 'Model name:|Architecture:' || true; fi
if [[ -r /proc/meminfo ]]; then head -1 /proc/meminfo; fi
echo "Service limit: 2 CPUs, 2 GiB RAM, one Uvicorn process. Load client shares the host."
echo "Previous revision: $previous. Candidate revision: $candidate."
prior_image=$(build_image "$previous")
candidate_image=$(build_image "$candidate")
previous_id=$(start_image "$prior_image" "")
port=$(docker port "$previous_id" 8000/tcp | head -1 | cut -d: -f2)
base="http://127.0.0.1:$port"
check_api baseline 2.0.0 preview
docker stop "$previous_id" >/dev/null

candidate_id=$(start_image "$candidate_image" "$port")
# Read the candidate version from its own OpenAPI response, then validate the exercised route.
wait_for_health
candidate_version=$(curl -fsS "$base/openapi.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])')
test "$candidate_version" != 2.0.0
check_api candidate "$candidate_version" extractive
for workers in 1 4; do
  docker restart "$candidate_id" >/dev/null
  wait_for_health
  python3 scripts/benchmark_offline.py "$port" "$workers"
done

docker stop "$candidate_id" >/dev/null
restored_id=$(start_image "$prior_image" "$port")
test "$(docker inspect --format '{{.Image}}' "$restored_id")" = "$prior_image"
check_api rollback 2.0.0 preview
