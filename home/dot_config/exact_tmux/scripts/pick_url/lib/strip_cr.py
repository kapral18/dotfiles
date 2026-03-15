#!/usr/bin/env python3
import sys

text = sys.stdin.read()
lines = text.split("\n")
sys.stdout.write("\n".join([ln.split("\r")[-1] for ln in lines]))
