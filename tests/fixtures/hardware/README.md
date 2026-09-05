# Synthetic hardware collector fixtures

Every log in this directory is a `SYNTHETIC` parser fixture. It is not a
NUCLEO-F401RE observation and must never be copied into `reports/` as hardware
evidence. The test suite derives temporary manifests from these bytes so that
the manifest hashes always bind to the exact fixture under test.
