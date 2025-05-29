#!/usr/bin/env python3
import sys
import os
import json
import requests
import argparse

parser = argparse.ArgumentParser(description='Chat with Claude')
parser.add_argument('--context', action='append', help='Context file to include')
parser.add_argument('prompt', help='The prompt to send')

args = parser.parse_args()

api_key = os.environ.get('ANTHROPIC_API_KEY')

if not api_key:
    print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

# Build the full prompt with context files
full_prompt = ""

if args.context:
    for context_file in args.context:
        try:
            with open(context_file, 'r') as f:
                content = f.read()
                full_prompt += f"```{context_file}\n{content}\n```\n\n"
        except FileNotFoundError:
            print(f"Error: Context file '{context_file}' not found", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading context file '{context_file}': {e}", file=sys.stderr)
            sys.exit(1)

full_prompt += args.prompt

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
            'content': full_prompt
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
