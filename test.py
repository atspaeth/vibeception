#!/usr/bin/env python3
import sys
import os
import json
import requests

if len(sys.argv) != 2:
    print("Usage: python script.py <prompt>", file=sys.stderr)
    sys.exit(1)

prompt = sys.argv[1]
api_key = os.environ.get('ANTHROPIC_API_KEY')

if not api_key:
    print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

headers = {
    'x-api-key': api_key,
    'anthropic-version': '2023-06-01',
    'content-type': 'application/json'
}

data = {
    'model': 'claude-sonnet-4-20250514',
    'max_tokens': 1024,
    'messages': [
        {
            'role': 'user',
            'content': prompt
        }
    ]
}

response = requests.post(
    'https://api.anthropic.com/v1/messages',
    headers=headers,
    json=data
)

result = response.json()
print(result['content'][0]['text'])
