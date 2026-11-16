#!/usr/bin/env bash
# Run from a clean repository checkout with Docker, curl, git and Python 3.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
previous=56814adc71f47ca3d4c95a19175f13d2865e25fd
candidate=$(git rev-parse HEAD)
previous_id=""
candidate_id=""
cleanup() {
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

check_api() {
  local phase="$1" expected="$2" actual
  curl --retry 45 --retry-delay 1 --retry-connrefused --max-time 3 -fsS "$base/health" >/dev/null
  actual=$(curl -fsS "$base/openapi.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])')
  test "$actual" = "$expected"
  curl -fsS --max-time 60 -H 'Content-Type: application/json' \
    -d '{"question":"How many ECTS credits does the Master programme in Artificial Intelligence and Cybersecurity comprise?","department":"AIandCybersecurity"}' "$base/ask" |
    python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"] == "extractive" and r["sources"] and "120" in r["answer"], "curriculum smoke query failed"'
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
check_api baseline 2.0.0
docker stop "$previous_id" >/dev/null

candidate_id=$(start_image "$candidate_image" "$port")
# Read the candidate version from its own OpenAPI response, then validate the exercised route.
curl --retry 45 --retry-delay 1 --retry-connrefused --max-time 3 -fsS "$base/health" >/dev/null
candidate_version=$(curl -fsS "$base/openapi.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])')
test "$candidate_version" != 2.0.0
check_api candidate "$candidate_version"
for workers in 1 4; do
  docker restart "$candidate_id" >/dev/null
  curl --retry 45 --retry-delay 1 --retry-connrefused --max-time 3 -fsS "$base/health" >/dev/null
  python3 scripts/benchmark_offline.py "$port" "$workers"
done

docker stop "$candidate_id" >/dev/null
docker start "$previous_id" >/dev/null
test "$(docker inspect --format '{{.Image}}' "$previous_id")" = "$prior_image"
check_api rollback 2.0.0
