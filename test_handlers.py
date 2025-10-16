#!/usr/bin/env python3
"""Test script to verify event handler registration"""

import os
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp

load_dotenv()

app = AsyncApp(token=os.getenv("SLACK_BOT_TOKEN"))

# Register handlers
from src import register_all_handlers
register_all_handlers(app)

# Check registered listeners
print("=" * 50)
print("REGISTERED EVENT LISTENERS")
print("=" * 50)

# Get all listener attributes
for attr_name in dir(app):
    if 'listener' in attr_name.lower():
        attr_value = getattr(app, attr_name)
        if isinstance(attr_value, dict):
            print(f"\n{attr_name}:")
            for key, value in attr_value.items():
                print(f"  {key}: {len(value) if isinstance(value, list) else value}")

print("\n" + "=" * 50)
print("Looking for app_mention and message handlers...")
print("=" * 50)

# Try to access internal listener registry
if hasattr(app, '_async_listener_runner'):
    runner = app._async_listener_runner
    if hasattr(runner, 'listener_executor'):
        executor = runner.listener_executor
        print(f"\nListener executor: {executor}")
        if hasattr(executor, 'listener_matchers'):
            print(f"Listener matchers: {executor.listener_matchers}")

print("\nDone!")
