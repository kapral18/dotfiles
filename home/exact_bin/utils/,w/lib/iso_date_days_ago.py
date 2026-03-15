#!/usr/bin/env python3
import datetime
import sys

days = int(sys.argv[1])
dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
print(dt.strftime("%Y-%m-%d"))
