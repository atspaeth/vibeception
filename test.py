#!/usr/bin/env python3
import sys
import os
import json
import requests
import argparse
import re

parser = argparse.ArgumentParser(description='Chat with Claude')
parser.add_argument('--context', action='append', help='Context file to include')
parser.add_argument('--system', default='system.txt', help='System prompt file (default: system.txt)')
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

# Prepare messages array
messages = []

# Add system message if system file exists
if os.path.exists(args.system):
    try:
        with open(args.system, 'r') as f:
            system_content = f.read().strip()
            if system_content:
                messages.append({
                    'role': 'system',
                    'content': system_content
                })
    except Exception as e:
        print(f"Warning: Error reading system file '{args.system}': {e}", file=sys.stderr)

# Add user message
messages.append({
    'role': 'user',
    'content': full_prompt
})

data = {
    'model': 'claude-sonnet-4-20250514',
    'max_tokens': 4096,
    'messages': messages
}

response = requests.post(
    'https://api.anthropic.com/v1/messages',
    headers=headers,
    json=data
)

result = response.json()
output = result['content'][0]['text']

# Parse output for fenced code blocks with filenames
pattern = r'^```([^\n]+)\n(.*?)^```'
matches = re.findall(pattern, output, re.MULTILINE | re.DOTALL)

# Create a copy of the output to remove processed code blocks
remaining_output = output

for filename, code_content in matches:
    filename = filename.strip()
    if filename and not filename.startswith(' '):  # Skip language-only blocks
        # Check if this is a search/replace block
        search_replace_pattern = r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE'
        search_replace_match = re.search(search_replace_pattern, code_content, re.DOTALL)
        
        if search_replace_match:
            # Handle search/replace format
            search_text = search_replace_match.group(1)
            replace_text = search_replace_match.group(2)
            
            try:
                # Read the existing file
                if os.path.exists(filename):
                    with open(filename, 'r') as f:
                        file_content = f.read()
                    
                    # Perform the replacement
                    if search_text in file_content:
                        new_content = file_content.replace(search_text, replace_text)
                        
                        # Write the updated content back
                        with open(filename, 'w') as f:
                            f.write(new_content)
                        
                        print(f"Applied search/replace to {filename}")
                    else:
                        print(f"Warning: Search text not found in {filename}", file=sys.stderr)
                else:
                    print(f"Error: File '{filename}' does not exist for search/replace", file=sys.stderr)
                    
            except Exception as e:
                print(f"Error processing search/replace for '{filename}': {e}", file=sys.stderr)
        else:
            # Handle full file replacement (existing behavior)
            try:
                with open(filename, 'w') as f:
                    f.write(code_content)
            except Exception as e:
                print(f"Error writing to file '{filename}': {e}", file=sys.stderr)
        
        # Remove this code block from the output
        block_pattern = rf'^```{re.escape(filename)}\n.*?^```'
        remaining_output = re.sub(block_pattern, '', remaining_output, flags=re.MULTILINE | re.DOTALL, count=1)

# Print remaining output (everything except the processed code blocks)
remaining_output = remaining_output.strip()
if remaining_output:
    print(remaining_output)
