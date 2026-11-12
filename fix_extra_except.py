with open('backend/scout_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove lines 479-480 (1-indexed) = indices 478-479 (0-indexed)
# These are the extra "except Exception:" and "continue" at 28 spaces
# Verify what we're removing
print(f'Line 479 (idx 478): {repr(lines[478])}')
print(f'Line 480 (idx 479): {repr(lines[479])}')

# Remove indices 478 and 479
new_lines = lines[:478] + lines[480:]

with open('backend/scout_engine.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Removed extra except/continue lines')
