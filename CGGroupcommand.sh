#!/bin/bash
sudo cgcreate -a ubuntu -t ubuntu -g memory:ubuntu
sudo echo 900000000 > memory.limit_in_bytes
