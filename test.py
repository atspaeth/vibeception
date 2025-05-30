#!/usr/bin/env python3
import sys
import os
import json
import requests
import argparse

parser = argparse.ArgumentParser(description='Chat with Claude')
parser.add_argument('--context', action='append', help='Context file to include')
parser.add_argument('--system', default='system.txt', help='System prompt file (default: system.txt)')
parser.add_argument('--debug', action='store_true', help='Save API response to reply.json')
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

messages = [{
    'role': 'user',
    'content': full_prompt
}]

data = {
    'model': 'claude-sonnet-4-20250514',
    'max_tokens': 4096,
    'messages': messages
}

if os.path.exists(args.system):
    try:
        with open(args.system, 'r') as f:
            system_content = f.read().strip()
            if system_content:
                data['system'] = system_content
    except Exception as e:
        print(f"Warning: Error reading system file '{args.system}': {e}", file=sys.stderr)

response = requests.post(
    'https://api.anthropic.com/v1/messages',
    headers=headers,
    json=data
)

try:
    result = response.json()
    if args.debug:
        with open('reply.json', 'w') as f:
            json.dump(result, f, indent=2)
    output = result['content'][0]['text']
except KeyError as e:
    print(f"Error: Unable to extract response text. Key error: {e}", file=sys.stderr)
    sys.exit(1)
except (requests.exceptions.JSONDecodeError, json.JSONDecodeError) as e:
    print(f"Error: Unable to parse response as JSON: {e}", file=sys.stderr)
    print(f"Raw response: {response.text}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error: Unexpected error processing response: {e}", file=sys.stderr)
    sys.exit(1)

def parse_output(output):
    remaining_output = []
    edits = []
    
    lines = output.split('\n')
    
    # State tracking
    in_code_block = False
    code_filename = None
    code_lines = []
    fence_depth = 0
    potential_filename = None
    
    for i, line in enumerate(lines):
        if line.startswith('```') and not in_code_block:
            # Check if previous line is a potential filename
            if potential_filename and not potential_filename.startswith(' '):
                # Start of a code block with filename on previous line
                in_code_block = True
                code_filename = potential_filename
                fence_depth = 1
                # Remove the filename from remaining_output since we're using it
                if remaining_output and remaining_output[-1] == potential_filename:
                    remaining_output.pop()
                potential_filename = None
                continue
            else:
                # Start of a code block with filename after backticks (old format)
                filename = line[3:].strip()
                if filename and not filename.startswith(' '):
                    in_code_block = True
                    code_filename = filename
                    fence_depth = 1
                    continue
                
        elif line.startswith('```') and in_code_block:
            # End of a code block
            fence_depth -= 1
            if fence_depth == 0:
                # Process the collected code block
                code_content = '\n'.join(code_lines)
                if '<<<<<<< SEARCH' in code_content and '>>>>>>> REPLACE' in code_content:
                    edits.append((code_filename, code_content))
                code_lines = []
                in_code_block = False
                code_filename = None
                continue
            else:
                # This is a nested fence - treat as content
                code_lines.append(line)
                
        elif in_code_block:
            if line.startswith('```'):
                fence_depth += 1
            code_lines.append(line)
            
        else:
            # Check if this line could be a filename (next line might be ```)
            if (i + 1 < len(lines) and 
                lines[i + 1].startswith('```') and 
                line.strip() and 
                not line.startswith(' ') and
                ('.' in line or '/' in line)):  # Basic filename heuristic
                potential_filename = line.strip()
            
            remaining_output.append(line)
            
    return edits, '\n'.join(remaining_output)

edits, remaining_output = parse_output(output)

# Process the edits
for filename, code_content in edits:
    try:
        # Read the existing file
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                file_content = f.read()
            
            # Extract search and replace content
            parts = code_content.split('\n=======\n')
            if len(parts) == 2:
                search_text = parts[0].replace('<<<<<<< SEARCH\n', '', 1)
                replace_text = parts[1].replace('\n>>>>>>> REPLACE', '', 1)
                
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
            # Check if this is a file creation (blank search text)
            parts = code_content.split('\n=======\n')
            if len(parts) == 2:
                search_text = parts[0].replace('<<<<<<< SEARCH\n', '', 1)
                replace_text = parts[1].replace('\n>>>>>>> REPLACE', '', 1)
                
                if not search_text.strip():
                    # Create new file with replace content
                    with open(filename, 'w') as f:
                        f.write(replace_text)
                    print(f"Created new file {filename}")
                else:
                    print(f"Error: File '{filename}' does not exist for search/replace", file=sys.stderr)
            else:
                print(f"Error: File '{filename}' does not exist for search/replace", file=sys.stderr)
            
    except Exception as e:
        print(f"Error processing search/replace for '{filename}': {e}", file=sys.stderr)

# Print remaining output
if remaining_output.strip():
    print(remaining_output.strip())
