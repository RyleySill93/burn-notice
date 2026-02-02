#!/bin/sh

psql -d postgres -c "create role burn_notice login password 'dev1';"
psql -d postgres -c "ALTER USER burn_notice WITH SUPERUSER;"
# Create application db
createdb -O burn_notice -E UTF8 -T template1 burn_notice
# Create test db
createdb -O burn_notice -E UTF8 -T template1 burn_notice-test
