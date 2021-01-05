# haproxy-dynamic-weights

Inspired by https://github.com/reincubate/haproxy-dynamic-weight:
* using Redis in Pub/Sub mode instead of Memcached, which hopefully leads to faster update times, e.g. in case critical components of one node suddenly crash
* no need for all servers to report weight updates
* Python3.6+ (and at least for now even 2.7)

### Requirements:
## sub&#46;py:
* `yum install socat`
* `yum install python-redis` (or `pip install redis`)
* rename and configure `config.json.example`


## pub&#46;py:
* `yum install python-redis` (or `pip install redis`)
* rename and configure `config.json.example`