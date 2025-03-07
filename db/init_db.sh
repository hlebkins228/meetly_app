#!/bin/bash

sudo -u postgres psql -f DBcreate.sql
sudo -u postgres psql -d meetly_db -f DBsetup.sql
sudo -u postgres psql -d meetly_db -f DBconstrains.sql
