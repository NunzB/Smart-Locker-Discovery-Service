def print_layout_matrix(boards, layout):
    
    is_dict = isinstance(layout, dict)
    
    if is_dict:
        columns = layout.get("columns", [])
    else:
        columns = getattr(layout, "columns", []) if layout is not None else []
        
    if not columns:
        print("Layout: Empty")
        return

    if is_dict:
        max_rows = max((len(col.get("rows", [])) for col in columns), default=0)
    else:
        max_rows = max((len(getattr(col, "rows", [])) for col in columns), default=0)
    
    print("Layout Matrix (X=open, c=closed):")
    
    # Header
    cell_width = 18
    if is_dict:
        header_cells = [f"Board {i+1} (Addr {b.get('address')})".center(cell_width) for i, b in enumerate(boards)]
    else:
        header_cells = [f"Board {i+1} (Addr {getattr(boards[i], 'address', '?')})".center(cell_width) for i in range(len(columns))]
    
    header_row = " | ".join(header_cells)
    
    print("\n" + header_row)
    print("-" * len(header_row))
    
    # Rows
    for r in range(max_rows):
        row_cells = []
        for col in columns:
            if is_dict:
                rows = col.get("rows", [])
            else:
                rows = getattr(col, "rows", [])
            
            if r < len(rows):
                if is_dict:
                    comps = rows[r].get("compartments", [])
                else:
                    comps = getattr(rows[r], "compartments", [])
            else:
                comps = []
                
            if comps:
                comps_str = []
                for comp in comps:
                    if is_dict:
                        status_char = "X" if comp.get("lockStatus") else "c"
                        lbl = comp.get("label", "?")
                    else:
                        status_char = "X" if getattr(comp, "lockStatus", False) else "c"
                        lbl = getattr(comp, "label", "?")
                    comps_str.append(f"{lbl}({status_char})")
                label_str = " ".join(comps_str)
                row_cells.append(label_str.center(cell_width))
            else:
                row_cells.append(" " * cell_width)
        print(" | ".join(row_cells))
    print()
