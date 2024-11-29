#!/bin/bash

# Create sftp users
./sftp-users.sh

# Start ssh daemon
/usr/sbin/sshd -D
