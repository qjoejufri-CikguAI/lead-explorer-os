import re

with open('backend/scout_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the start of the block to replace
start_marker = '# KOREK KOMEN: cari elemen komen dalam post'
start_idx = content.find(start_marker)
if start_idx == -1:
    print('START MARKER NOT FOUND')
else:
    print(f'START found at index {start_idx}')

# Find a unique end marker - the line after the DOM extraction block
# The block ends with the except for the container loop, then there's a blank line
# and then code for saving JSON
end_marker = '                        except Exception as e:\n                            print(f"[WARN] Gagal proses komen post #{i}: {e}")'
end_idx = content.find(end_marker, start_idx)
if end_idx == -1:
    print('END MARKER NOT FOUND')
else:
    print(f'END found at index {end_idx + len(end_marker)}')
    # Show what we're replacing
    block = content[start_idx:end_idx + len(end_marker)]
    print(f'Block length: {len(block)}')
    print('First 300 chars:')
    print(repr(block[:300]))
    print('Last 200 chars:')
    print(repr(block[-200:]))
