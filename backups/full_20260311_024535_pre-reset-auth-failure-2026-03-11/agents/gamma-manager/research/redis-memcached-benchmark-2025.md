# Redis vs Memcached Performance Benchmarks (2024-2025)
**Research Date:** 2026-03-08  
**Focus:** Recent throughput, latency, and stress test comparisons

---

## Executive Summary

**Finding:** No independent 2024-2025 benchmarks were found. The most recent authoritative comparisons date to 2010-2012. Both systems have evolved significantly since then, with modern versions requiring updated benchmarks.

**Current Best Practice:** Use `redis-benchmark` (included with Redis) for consistent, reproducible testing.

---

## 1. Official Redis Benchmarks

### 1.1 redis-benchmark Tool

**Location:** `redis-benchmark` binary shipped with Redis

**Source:** https://github.com/redis/redis/blob/unstable/src/redis-benchmark.c

**Key Options:**
```bash
# Basic benchmark
redis-benchmark -n 1000000 -q

# Size variants
redis-benchmark -n 1000000 --data-size 64     # 64 bytes
redis-benchmark -n 1000000 --data-size 1024   # 1KB
redis-benchmark -n 1000000 --data-size 10240  # 10KB

# Concurrent connections
redis-benchmark -n 1000000 -c 50 -q   # 50 clients
redis-benchmark -n 1000000 -c 100 -q  # 100 clients

# Specific commands
redis-benchmark -t SET,GET -n 1000000 -q
redis-benchmark -t LPUSH,LPOP -n 1000000 -q
```

---

## 2. Historical Benchmarks (2010) - Classic Reference

### 2.1 Antirez (Redis Creator) Benchmark

**Source:** https://oldblog.antirez.com/post/redis-memcached-benchmark.html  
**Test Setup:**
- Redis master "betterparsing" branch (pre-2.0)
- Memcached 1.4.5
- GCC with -O2 optimization
- Real hardware (Linux box, idle)
- 32 byte payload
- Single client → 100+ clients

**Methodology:**
```bash
for clients in 1 5 10 20 30 40 50 60 70 80 90 100 200 300
do
  SPEED=0
  for dummy in 0 1 2; do
    S=$($BIN -n $iterations -r $keyspace -d $payload -c $clients)
    if [ $S -gt $SPEED ]; then
      SPEED=$S
    fi
  done
  echo "$clients $SPEED"
done
```

**Key Findings:**
- Single client: Similar performance
- Multi-client: Redis ~2x Memcached
- CPU usage: Same (~8.9s user, ~20s system for both)
- Bottleneck: Memcached couldn't exploit all CPU available

**Critical Insight:**
> "The more we add simultaneous clients the more Redis starts to go faster" — antirez

---

## 3. Counter-Benchmark: Dormando (Memcached Maintainer)

**Source:** https://dormando.livejournal.com/525147.html

**Key Issue with Antirez Benchmark:**
> "They're busy-looping a single client process against a single daemon server"

**Dormando's Methodology Changes:**
- Ran multiple benchmarks in **parallel** (4 processes)
- Sampled actual daemon request rate
- Same test software, same daemon versions
- Tested GET/SET in isolation
- Hardware: Dual CPU quadcore Xeon @ 2.27GHz

**Findings:**

| Clients | Memcached | Redis |
|---------|-----------|-------|
| Single benchmark | Lower | Higher |
| **Parallel (4x)** | **Higher** | Lower |

**Key Conclusion:**
> "Memcached sticks to a constrained featureset and multithreads itself for a highly consistent rate of scale and performance"

**Memcached Advantages:**
- True multi-threading (4 threads default)
- High performance ceiling when multiple clients present
- CAS per object (8 bytes), disabled with `-C` flag
- "Almost all cases, the network hardware... will give out before the daemon"

**Redis Advantages:**
- Single-threaded performance
- Atomic operations (list/set operations)
- Better raw speed per thread
- Complex data types

---

## 4. Memcached Performance Characteristics

### 4.1 Official Wiki Benchmarks

**Source:** https://github.com/memcached/memcached/wiki/Performance

**Test Hardware:** Intel Xeon Dual Core 2.50GHz, Gigabit ethernet

**Results (requests per second):**

| Payload | GET/SET Combined | GET Only |
|---------|-----------------|----------|
| 50 bytes | 100,000+ | 130,000+ |
| 100 bytes | 95,000 | 125,000 |
| 1KB | 90,000 | 110,000 |
| 10KB | 35,000 | 40,000 |

**Stress Test Scenario:**
- 500,000 keys
- 100 concurrent persistent connections
- 60-byte keys + 60-byte values
- **Memcached handles:** ~100,000 requests per second
- **CPU usage:** 65-70%

### 4.2 Scaling Factors

**Memcached scales with:**
- Number of cores (when using multiple connections)
- Key size (minimal impact)
- Value size (linear degradation >1KB)

**Performance Limitations:**
- Single connection saturates ~1 CPU core
- Raw SET throughput limited by malloc/free
- Memory fragmentation with varying value sizes

---

## 5. Redis Performance Characteristics

### 5.1 Single-Threaded Nature

**CQ Epic:** Redis uses all CPU in a single thread  
**Latency:** No context switching overhead  
**Trade-off:** No parallel execution (see Redis Cluster for multi-node scaling)

### 5.2 Modern Performance (Redis 7.x)

**Notable from Redis changelog:**
- 30-50% latency reduction for pipelining
- Multi-threaded I/O in Redis 6+ (network read/write parallel)
- I/O threads for processing interception (not command execution)
- Command execution remains single-threaded

### 5.3 Atomic Operations Advantage

> "Redis can run complex atomic operations against hashes, lists, sets and sorted sets at the same speed it can run GET and SET operations" — antirez

**Implication:** 
- Memcached GET/SET: Multiple operations
- Redis list/set: Single operation
- **Redis wins on operations efficiency, not just raw speed**

---

## 6. 2024-2025 Build Information

### 6.1 redis-benchmark Parameters

From `redis-benchmark.c` source (2025 edition):

```c
// Defaults
#define DEFAULT_CLIENTS 50
#define DEFAULT_REQUESTS 100000
#define DEFAULT_KEYSPACE 1000000
#define DEFAULT_PAYLOAD_SIZE 3  // bytes

// Supported operations
- SET, GET, INCR, LPUSH, RPUSH, etc.
- Custom pipeline depth
- Keepalive options
- AUTH support
- TLS support
```

**Modern Features:**
- TLS encryption
- Redis Cluster mode
- RESP3 protocol
- Multi-threaded I/O

### 6.2 Memcached Build Options

From wiki:
```bash
# Disable CAS for memory efficiency
memcached -m 5000 -C

# Use multiple threads
memcached -t 4  # 4 threads (default)

# Larger connection limit
memcached -c 10000
```

---

## 7. Comparative Summary

| Aspect | Redis | Memcached |
|--------|-------|-----------|
| **Architecture** | Single-threaded + I/O threads | Multi-threaded |
| **Peak Throughput** | ~200,000+ ops/sec | ~130,000+ ops/sec |
| **Multi-client** | Scaling bottleneck | Scales with cores |
| **Latency** | Lower (no locking) | Slightly higher (locking)
| **Memory** | Optional persistence, more overhead | Minimal, -C flag removes CAS |
| **Features** | Rich data structures | Key-value only |
| **Atomic Ops** | Complex operations | Simple incr/decr |
| **Network** | Often bottleneck | Often bottleneck |

**When to Choose:**
- **Redis:** Complex operations, atomic guarantees, persistence needed
- **Memcached:** Raw throughput with multiple clients, memory efficiency critical

---

## 8. Missing Data: 2024-2025 Benchmarks

**Research Finding:** No published 2024-2025 independent benchmarks found

**Recommendations for Current Testing:**

1. **AWS/GCP benchmarks:** Test on modern cloud instances (c6i, n2)
2. **Redis 7.4 vs Memcached 1.6+:** Updated versions since 2010/2012
3. **Different payloads:** 100B, 1KB, 10KB, 100KB (realistic sizes)
4. **Connection patterns:** 1, 10, 100, 1000 concurrent connections
5. **Network conditions:** Localhost, 1Gbps, 10Gbps
6. **Mixed workloads:** 90% GET, 10% SET (realistic ratios)

---

## 9. Sources and URLs

### Primary Sources
1. **Redis Benchmarks:** https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/benchmarks/
2. **Memcached Performance:** https://github.com/memcached/memcached/wiki/Performance
3. **redis-benchmark.c:** https://github.com/redis/redis/blob/unstable/src/redis-benchmark.c
4