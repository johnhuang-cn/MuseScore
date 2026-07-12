#!/usr/bin/env python3
"""
OMR v5: Morphological approach for note head detection.
1. Detect & remove staff lines
2. Erode to isolate solid note heads
3. Find centroids of remaining components
4. Map to note names
"""
from PIL import Image, ImageDraw
import numpy as np
import sys

def load_gray(path):
    return np.array(Image.open(path).convert('L'))

def detect_staff(gray):
    """Detect 5 staff lines. Returns [bottom_y ... top_y] (descending y)."""
    h, w = gray.shape
    bin_ = (gray < 140).astype(float)
    x1, x2 = int(w*0.15), int(w*0.85)
    row_dark = np.array([np.mean(bin_[y, x1:x2]) for y in range(h)])
    thresh = max(np.mean(row_dark) * 3, 0.12)
    cands = np.where(row_dark > thresh)[0]
    if len(cands) == 0: return []
    groups, cur = [], [cands[0]]
    for i in range(1, len(cands)):
        if cands[i] - cands[i-1] <= 2: cur.append(cands[i])
        else: groups.append(int(np.mean(cur))); cur = [cands[i]]
    groups.append(int(np.mean(cur)))
    best, bscore = None, 1e9
    for i in range(len(groups)-4):
        g = groups[i:i+5]
        s = np.var([g[j+1]-g[j] for j in range(4)])
        if s < bscore: bscore, best = s, g
    if best and best[0] < best[-1]: best = list(reversed(best))
    return best

def remove_staff_lines(gray, staff_lines):
    """Remove staff lines, preserving note heads."""
    h, w = gray.shape
    cleaned = gray.copy()
    for line_y in staff_lines:
        for dy in range(-1, 2):
            y = line_y + dy
            if y < 0 or y >= h: continue
            # Scan for long horizontal dark runs (>8px) on this row
            x = 0
            while x < w:
                if cleaned[y, x] < 140:
                    # Find run length
                    run_start = x
                    while x < w and cleaned[y, x] < 140:
                        x += 1
                    run_len = x - run_start
                    if run_len > 8:  # Staff line run
                        # Check each pixel: keep if vertical neighbors are dark (note head)
                        for px in range(run_start, x):
                            above = y > 0 and cleaned[y-1, px] < 140
                            below = y < h-1 and cleaned[y+1, px] < 140
                            if not (above and below):
                                cleaned[y, px] = 255
                else:
                    x += 1
    return cleaned

def find_note_heads(cleaned_gray, staff_lines):
    """Find note head centroids using morphological erosion + connected components."""
    h, w = cleaned_gray.shape
    if len(staff_lines) < 5: return []
    
    bottom_y, top_y = max(staff_lines), min(staff_lines)
    ls = (bottom_y - top_y) / 4.0
    hs = ls / 2.0
    
    # Binary image
    binary = (cleaned_gray < 140).astype(np.uint8)
    
    # Erosion: use a small circular structuring element to isolate note heads
    # Note head is ~8px wide, ~5px tall at this resolution
    # Erosion with a 3x3 cross should preserve the core of note heads
    # but remove thin stems and isolated pixels
    
    # Apply erosion with cross-shaped element
    def erode(img, iterations=1):
        result = img.copy()
        for _ in range(iterations):
            new = np.zeros_like(result)
            new[1:, :] |= result[:-1, :]   # from above
            new[:-1, :] |= result[1:, :]   # from below
            new[:, 1:] |= result[:, :-1]   # from left
            new[:, :-1] |= result[:, 1:]   # from right
            result = result & new
        return result
    
    # Apply 1 iteration of erosion to remove thin stems
    eroded = erode(binary, iterations=1)
    
    # Also try: remove vertical stems by only keeping pixels that have
    # horizontal neighbors (wide features = note heads, not stems)
    horiz_mask = np.zeros_like(binary)
    for y in range(h):
        for x in range(2, w-2):
            if binary[y, x] and binary[y, x-1] and binary[y, x+1]:
                horiz_mask[y, x] = 1
    
    # Combine: note head must appear in both eroded and horizontal mask
    # (or just use horizontal mask for y-localization and eroded for validation)
    
    # Find connected components in the eroded image
    labels = np.zeros_like(eroded, dtype=int)
    label_count = 0
    min_component_area = 3  # At least 3 pixels after erosion
    
    for y in range(h):
        for x in range(w):
            if eroded[y, x] and labels[y, x] == 0:
                label_count += 1
                # BFS
                queue = [(y, x)]
                labels[y, x] = label_count
                component_pixels = []
                while queue:
                    cy, cx = queue.pop(0)
                    component_pixels.append((cy, cx))
                    for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                        ny, nx = cy+dy, cx+dx
                        if (0 <= ny < h and 0 <= nx < w and 
                            eroded[ny, nx] and labels[ny, nx] == 0):
                            labels[ny, nx] = label_count
                            queue.append((ny, nx))
    
    # Extract centroids and sizes of valid components
    notes = []
    for label in range(1, label_count + 1):
        ys, xs = np.where(labels == label)
        area = len(ys)
        if area < min_component_area:
            continue
        
        cy = np.mean(ys)
        cx = np.mean(xs)
        width = max(xs) - min(xs) + 1
        height = max(ys) - min(ys) + 1
        
        # Filter: note head components should be compact
        # Width: roughly 3-12px (after erosion, smaller than original)
        # Height: roughly 2-8px
        # Aspect ratio: 0.5-3.0
        aspect = width / max(height, 1)
        if width > 15 or height > 12:
            continue  # Too big (clef, text, etc.)
        if aspect < 0.3 or aspect > 4.0:
            continue  # Wrong shape
        
        # Check that this is actually a note head by looking at the
        # original (non-eroded) binary image in this region
        # A note head should be wider than tall in the original
        orig_region = binary[int(cy)-3:int(cy)+4, int(cx)-5:int(cx)+6]
        if orig_region.size > 0 and np.mean(orig_region) < 0.1:
            continue  # Too sparse in original = not a note head
        
        # Use the original (non-eroded) image to get better y-position
        # Find the y-position using the horizontal mask centroid
        region_y1 = max(0, int(cy) - int(hs))
        region_y2 = min(h, int(cy) + int(hs) + 1)
        region_x1 = max(0, int(cx) - int(ls//2))
        region_x2 = min(w, int(cx) + int(ls//2) + 1)
        
        local_horiz = horiz_mask[region_y1:region_y2, region_x1:region_x2]
        local_binary = binary[region_y1:region_y2, region_x1:region_x2]
        
        # Find the row with the widest horizontal run in the local region
        best_y_offset = cy - region_y1
        max_width = 0
        for row_idx in range(local_horiz.shape[0]):
            row = local_binary[row_idx]
            # Find longest dark run
            max_run = 0
            cur_run = 0
            for px in row:
                if px: cur_run += 1; max_run = max(max_run, cur_run)
                else: cur_run = 0
            if max_run > max_width:
                max_width = max_run
                best_y_offset = row_idx
        
        refined_y = region_y1 + best_y_offset
        
        notes.append({
            'x': float(cx),
            'y': float(refined_y),
            'area': area,
            'width': width,
            'height': height
        })
    
    # Sort by x
    notes.sort(key=lambda n: n['x'])
    
    # Remove duplicates that are too close
    filtered = []
    min_x_dist = ls * 0.5
    for n in notes:
        is_dup = False
        for f in filtered:
            if abs(n['x'] - f['x']) < min_x_dist:
                is_dup = True
                break
        if not is_dup:
            filtered.append(n)
    
    return filtered

def y_to_note(y, staff_lines):
    bottom_y = max(staff_lines)
    top_y = min(staff_lines)
    hs = (bottom_y - top_y) / 8.0
    pos = round((bottom_y - y) / hs)
    note_map = {
        -8: 'D3', -7: 'E3', -6: 'F3', -5: 'G3', -4: 'A3', -3: 'B3',
        -2: 'C4', -1: 'D4',
        0: 'E4', 1: 'F4', 2: 'G4', 3: 'A4', 4: 'B4',
        5: 'C5', 6: 'D5', 7: 'E5', 8: 'F5',
        9: 'G5', 10: 'A5', 11: 'B5', 12: 'C6',
        13: 'D6', 14: 'E6', 15: 'F6', 16: 'G6',
    }
    return note_map.get(pos, f'?{pos}'), pos

def to_custom(name):
    num = {'C':'1','D':'2','E':'3','F':'4','G':'5','A':'6','B':'7'}
    if len(name) < 2 or not name[0].isalpha(): return name
    letter = name[0]
    try: octave = int(name[1:])
    except: return name
    if octave < 4: return letter.upper()
    elif octave == 4: return num.get(letter, letter)
    elif octave == 5: return letter.lower()
    elif octave == 6: return letter.lower() + '2'
    else: return letter.lower() + str(octave - 4)

def save_debug(orig_path, gray, staff_lines, notes):
    img = Image.fromarray(gray).convert('RGB')
    draw = ImageDraw.Draw(img)
    h, w = gray.shape
    for y in staff_lines:
        draw.line([(0, y), (w, y)], fill=(0, 200, 0), width=1)
    for i, n in enumerate(notes):
        x, y = int(n['x']), int(n['y'])
        name, _ = y_to_note(n['y'], staff_lines)
        custom = to_custom(name)
        r = 6
        draw.ellipse([(x-r, y-r), (x+r, y+r)], outline=(255, 0, 0), width=2)
        draw.text((x-5, max(0, min(staff_lines)-16)), str(i+1), fill=(255, 0, 0))
        draw.text((x-5, max(staff_lines)+4), custom, fill=(255, 0, 0))
    debug_path = orig_path.rsplit('.', 1)[0] + '_debug3.png'
    img.save(debug_path)
    print(f"Debug: {debug_path}")

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print("Usage: python3 staff_reader.py <image>"); sys.exit(1)
    
    gray = load_gray(path)
    h, w = gray.shape
    print(f"Image: {w}x{h}")
    
    staff_lines = detect_staff(gray)
    if len(staff_lines) < 5:
        print("ERROR: no 5 staff lines"); sys.exit(1)
    
    bottom_y, top_y = max(staff_lines), min(staff_lines)
    ls = (bottom_y - top_y) / 4.0
    hs = ls / 2.0
    print(f"Staff: bottom={bottom_y} top={top_y} ls={ls:.1f}px hs={hs:.1f}px")
    
    # Remove staff lines
    cleaned = remove_staff_lines(gray, staff_lines)
    
    # Detect note heads
    notes = find_note_heads(cleaned, staff_lines)
    print(f"\nDetected {len(notes)} note heads")
    
    print(f"\n{'#':<4} {'X':>6} {'Y':>6} {'Note':>5} {'Pos':>4} {'Custom':>7}")
    print("-" * 40)
    results = []
    for i, n in enumerate(notes):
        name, pos = y_to_note(n['y'], staff_lines)
        custom = to_custom(name)
        print(f"{i+1:<4} {n['x']:>6.0f} {n['y']:>6.1f} {name:>5} {pos:>4} {custom:>7}")
        results.append(custom)
    
    print(f"\nResult: {' '.join(results)}")
    save_debug(path, gray, staff_lines, notes)

if __name__ == '__main__':
    main()
