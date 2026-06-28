import os
import re

def update_env_file_in_place(filepath: str, updates: dict):
    """
    Updates a .env file in-place without replacing the inode.
    This is critical for Docker file bind mounts, because python-dotenv's set_key
    creates a temp file and renames it, which breaks the Docker volume link.
    """
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            pass # Create if not exists

    with open(filepath, 'r') as f:
        lines = f.readlines()

    for key, value in updates.items():
        if not value:
            continue
            
        key_pattern = re.compile(rf"^{re.escape(key)}\s*=")
        found = False
        
        for i, line in enumerate(lines):
            if key_pattern.match(line):
                lines[i] = f"{key}={value}\n"
                found = True
                break
                
        if not found:
            # Ensure the last line has a newline before appending
            if lines and not lines[-1].endswith('\n'):
                lines[-1] += '\n'
            lines.append(f"{key}={value}\n")

    # Write back in-place (preserves inode for Docker bind mount)
    with open(filepath, 'w') as f:
        f.writelines(lines)

    # Also update os.environ
    for key, value in updates.items():
        if value:
            os.environ[key] = str(value)
