import re

with open('backend/scout_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the start of the block to replace
start_marker = '# KOREK KOMEN: cari elemen komen dalam post'
start_idx = content.find(start_marker)
if start_idx == -1:
    print('START MARKER NOT FOUND')
    exit(1)
print(f'START found at index {start_idx}')

# Find end: look for the line "                    except Exception as e:" (20 spaces) that comes after start
# This is the outer except for the container loop
end_marker = '                    except Exception as e:\n                        print(f"[WARN] Gagal proses komen post #{i}: {e}")'
end_idx = content.find(end_marker, start_idx)
if end_idx == -1:
    print('END MARKER NOT FOUND, trying alternative...')
    # Try finding just 'Gagal proses komen post' 
    alt_marker = 'Gagal proses komen post'
    alt_idx = content.find(alt_marker, start_idx)
    if alt_idx == -1:
        print('ALT MARKER NOT FOUND')
        exit(1)
        # Find the line start
        line_start = content.rfind('\n', 0, alt_idx) + 1
        # Find line end
        line_end = content.find('\n', alt_idx)
        print(f'Alt found: lines[{line_start}:{line_end}]')
        print(repr(content[line_start:line_end]))
        end_idx = line_end
    else:
        print(f'ALT found at {alt_idx}')
        # Find line boundaries
        line_start = content.rfind('\n', 0, alt_idx) + 1
        line_end = content.find('\n', alt_idx)
        end_idx = line_end
        print(f'Line: {repr(content[line_start:line_end])}')
else:
    print(f'END found at index {end_idx + len(end_marker)}')
    end_idx = end_idx + len(end_marker)

print(f'Block to replace: lines roughly {start_idx} to {end_idx}')
print(f'Old block length: {end_idx - start_idx}')
print(f'Old block first 100 chars: {repr(content[start_idx:start_idx+100])}')
print(f'Old block last 100 chars: {repr(content[end_idx-100:end_idx])}')
