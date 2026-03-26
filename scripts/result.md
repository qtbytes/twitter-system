```sh
$ uv run benchmark-celebrity-fanout --followers 100000 --batch-size 10000 --drop-existing
Preparing database...
Clearing existing rows...
Creating celebrity and 100,000 followers...
Creating benchmark tweet...
Running fan-out benchmark...

========================================================================
Celebrity Fan-out Benchmark Result
========================================================================
followers:                  100,000
batch_size:                 10,000
fanout_strategy:            current fan-out job
user_create_seconds:        2.61
follow_create_seconds:      0.59
tweet_create_seconds:       0.0040
fanout_seconds:             4.79
delivered_rows:             100,001
throughput_rows_per_second: 20,873.47
========================================================================

Interpretation
------------------------------------------------------------------------
- Measured latency for this run: 4.79s to deliver one tweet to 100,001 timelines.
- Effective throughput: about 20,873.47 feed rows / second.
- If throughput stayed similar, 1,000,001 timeline deliveries (1 celebrity + 1e6 followers) would take about 47.91s.

Important caveat
------------------------------------------------------------------------
- This benchmark measures database-side fan-out latency in one process. It does not include queue backlog, multiple workers, network hops, replication lag, cache invalidation storms, or client-visible read delay.
- If you want a truer production-style number, run this benchmark against Postgres/MySQL instead of local SQLite, and compare one worker vs multiple workers.
$
```



```sh
$ uv run benchmark-celebrity-fanout --followers 1000000 --batch-size 10000 --drop-existing
Preparing database...
Clearing existing rows...
Creating celebrity and 1,000,000 followers...
Creating benchmark tweet...
Running fan-out benchmark...

========================================================================
Celebrity Fan-out Benchmark Result
========================================================================
followers:                  1,000,000
batch_size:                 10,000
fanout_strategy:            current fan-out job
user_create_seconds:        27.00
follow_create_seconds:      5.74
tweet_create_seconds:       0.0038
fanout_seconds:             11.86
delivered_rows:             1,000,001
throughput_rows_per_second: 84,347.49
========================================================================

Interpretation
------------------------------------------------------------------------
- Measured latency for this run: 11.86s to deliver one tweet to 1,000,001 timelines.
- Effective throughput: about 84,347.49 feed rows / second.
- If throughput stayed similar, 1,000,001 timeline deliveries (1 celebrity + 1e6 followers) would take about 11.86s.

Important caveat
------------------------------------------------------------------------
- This benchmark measures database-side fan-out latency in one process. It does not include queue backlog, multiple workers, network hops, replication lag, cache invalidation storms, or client-visible read delay.
- If you want a truer production-style number, run this benchmark against Postgres/MySQL instead of local SQLite, and compare one worker vs multiple workers.
$
```
