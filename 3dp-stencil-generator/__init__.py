# 3DP Stencil Generator for KiCad
# Original Author: Leo Kuroshita (Hugelton Instruments)
# License: MIT
# Repository: https://github.com/hugelton/3DP-Stencil-Generator

import pcbnew
import re
import datetime
import os


# === Global configuration ===
BUILD = "118"            # Build number
workDir = "stencil"      # Working folder name
front_copper_pads = True # Generate front copper pads
back_copper_pads = False # Generate back copper pads
min_mask_width = 0.20    # Minimum mask width (mm) between pads
min_pad_size = 0.40      # Minimum pad size (mm) after shrinking
pcbClearence = 0.15      # PCB clearance (mm) - moves outline outward from Edge.Cuts

import wx

class StencilParametersDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Stencil Generator Parameters")
        
        # Create the dialog layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Front copper pads checkbox
        self.front_copper_cb = wx.CheckBox(self, label="Generate front copper pads")
        self.front_copper_cb.SetValue(front_copper_pads)  # default value
        sizer.Add(self.front_copper_cb, 0, wx.ALL, 5)
        
        # Back copper pads checkbox
        self.back_copper_cb = wx.CheckBox(self, label="Generate back copper pads")
        self.back_copper_cb.SetValue(back_copper_pads)  # default value
        sizer.Add(self.back_copper_cb, 0, wx.ALL, 5)
        
        # Minimum mask width
        sizer.Add(wx.StaticText(self, label="Minimum mask width (mm):"), 0, wx.ALL, 5)
        self.mask_width_ctrl = wx.TextCtrl(self, value=str(min_mask_width))
        sizer.Add(self.mask_width_ctrl, 0, wx.ALL|wx.EXPAND, 5)
        
        # Minimum pad size
        sizer.Add(wx.StaticText(self, label="Minimum pad size (mm):"), 0, wx.ALL, 5)
        self.pad_size_ctrl = wx.TextCtrl(self, value=str(min_pad_size))
        sizer.Add(self.pad_size_ctrl, 0, wx.ALL|wx.EXPAND, 5)
        
        # PCB clearance
        sizer.Add(wx.StaticText(self, label="PCB clearance (mm):"), 0, wx.ALL, 5)
        self.clearance_ctrl = wx.TextCtrl(self, value=str(pcbClearence))
        sizer.Add(self.clearance_ctrl, 0, wx.ALL|wx.EXPAND, 5)
        
        # OK and Cancel buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK)
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALL|wx.CENTER, 5)
        
        self.SetSizer(sizer)
        self.Fit()
    
    def get_values(self):
        """Return the values from the dialog"""
        try:
            return {
                'front_copper_pads': self.front_copper_cb.GetValue(),
                'back_copper_pads': self.back_copper_cb.GetValue(),
                'min_mask_width': float(self.mask_width_ctrl.GetValue()),
                'min_pad_size': float(self.pad_size_ctrl.GetValue()),
                'pcb_clearance': float(self.clearance_ctrl.GetValue())
            }
        except ValueError:
            wx.MessageBox("Please enter valid numbers for all numeric fields!", "Error")
            return None



class StencilGenerator(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "3DP Stencil Generator"
        self.category = "Modify PCB"
        self.description = "Generate OpenSCAD file for 3D printable solder stencil with alignment holes"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(
            os.path.dirname(__file__), "./icon.png")
        
    def show_parameters_dialog(self):
        app = wx.App.Get()
        if not app:
            app = wx.App()
        
        dlg = StencilParametersDialog(None)
        
        if dlg.ShowModal() == wx.ID_OK:
            values = dlg.get_values()
            if values:
                # Update global variables with user input
                global front_copper_pads, back_copper_pads, min_mask_width, min_pad_size, pcbClearence
                front_copper_pads = values['front_copper_pads']
                back_copper_pads = values['back_copper_pads']
                min_mask_width = values['min_mask_width']
                min_pad_size = values['min_pad_size']
                pcbClearence = values['pcb_clearance']
                
                dlg.Destroy()
                return True  # User clicked OK
        
        dlg.Destroy()
        return False  # User cancelled

    def Run(self):
        try:
            board = pcbnew.GetBoard()
            project_file = board.GetFileName()
    
            if not project_file:
                raise RuntimeError("No board file loaded")
    
            project_dir = os.path.dirname(project_file)
            output_dir = os.path.join(project_dir, workDir)
            os.makedirs(output_dir, exist_ok=True)
    
            log_file = os.path.join(output_dir, "kicad_stencilgen_debug.log")
   
            def log(msg):
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now()} - {msg}\n")
    
            log(f"===== Plugin started - BUILD {BUILD} =====")
            log(f"Project directory: {project_dir}")

            # Show parameter dialog first
            log("Showing parameters dialog")
            if not self.show_parameters_dialog():
                log("Parameters dialog cancelled, exiting")
                return  # User cancelled, exit

    
            base_filename = re.sub(r'\.[^.]*$', '', os.path.basename(project_file))
            output_filename = os.path.join(output_dir, f"{base_filename}_stencil.scad")
    
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(self.generate_openscad(board))
                log(f"SCAD file written: {output_filename}")
    
            pcbnew.Refresh()
            print(f"OpenSCAD file generated: {output_filename}")
            log("Script completed successfully")
            
            # Open the stencil folder in file explorer
            import subprocess
            import platform
            system = platform.system()
            try:
                if system == 'Darwin':  # macOS
                    subprocess.run(['open', output_dir])
                elif system == 'Windows':
                    subprocess.run(['explorer', output_dir])
                elif system == 'Linux':
                    subprocess.run(['xdg-open', output_dir])
                log(f"Opened stencil folder: {output_dir}")
            except Exception as e:
                log(f"Could not open folder automatically: {e}")
    
        except Exception as e:
            msg = f"ERROR in Run(): {repr(e)}"
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now()} - {msg}\n")
            except:
                print("Error writing to log file.")
            print(msg)

    def generate_openscad(self, board):
        scad = "// KiCad Stencil Generator\n"
        scad += f"// Generated on {datetime.datetime.now()}\n\n"

        scad += "// Parameters (adjust as needed)\n"
        scad += "stencil_thickness = 0.2;  // mm (Thickness of the stencil)\n"
        scad += "frame_height = 2.0;       // mm (Height of the frame)\n"
        scad += "pcb_thickness = 1.6;      // mm (Thickness of the PCB)\n"
        scad += "alignment_pin_diameter = 3.0;  // mm (Diameter of alignment holes)\n"
        scad += "\n"
        scad += "// Feature toggle\n"
        scad += "enable_alignment_holes = true;\n"
        scad += "\n"
        scad += "$fs = 0.1;  // Set minimum facet size for curves\n"
        scad += "$fa = 5;    // Set minimum angle for facets\n\n"

        scad += self.generate_modules(board)

        scad += "union(){\n"
        scad += "stencil();\n"
        scad += "        if (enable_alignment_holes) alignment_holes();\n}"

        return scad

    def generate_modules(self, board):
        scad = "module frame() {\n"
        scad += self.generate_frame(board)
        scad += "}\n\n"

        scad += "module pcb_outline() {\n"
        scad += self.generate_pcb_outline(board)
        scad += "}\n\n"

        scad += "module pads() {\n"
        scad += self.generate_pads(board)
        scad += "}\n\n"

        scad += "module alignment_holes() {\n"
        scad += self.generate_alignment_holes(board)
        scad += "}\n\n"

        scad += "module stencil() {\n"
        scad += "    difference() {\n"
        scad += "        frame();\n"
        scad += "        translate([0, 0, frame_height - pcb_thickness]) {\n"
        scad += "            linear_extrude(height=pcb_thickness + 0.01) {\n"
        scad += "                pcb_outline();\n"
        scad += "            }\n"
        scad += "        }\n"
        scad += "        translate([0, 0, - stencil_thickness]) {\n"
        scad += "            linear_extrude(height=frame_height + stencil_thickness) {\n"
        scad += "                pads();\n"
        scad += "            }\n"
        scad += "        }\n"
        scad += "    }\n"
        scad += "}\n\n"

        return scad

    def calculate_pcb_bounds(self, board):
        """Calculate PCB bounds for frame generation"""
        # Try User.9 first (preferred method)
        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if pcb_rect:
            # User.9 rectangle found - use its bounds
            center_x = pcb_rect[0] + pcb_rect[2]/2
            center_y = pcb_rect[1] + pcb_rect[3]/2
            width = self.mm(pcb_rect[2])
            height = self.mm(pcb_rect[3])
            return {
                'center_x': center_x,
                'center_y': center_y,
                'width': width,
                'height': height
            }
        
        # Fallback: analyze Edge.Cuts to determine bounds
        # Get all Edge.Cuts elements to calculate bounding box
        min_x = float('inf')
        max_x = float('-inf')
        min_y = float('inf')
        max_y = float('-inf')
        
        found_edge_cuts = False
        
        for drawing in board.GetDrawings():
            if drawing.GetLayer() == pcbnew.Edge_Cuts and isinstance(drawing, pcbnew.PCB_SHAPE):
                found_edge_cuts = True
                shape_type = drawing.GetShape()
                
                if shape_type == pcbnew.SHAPE_T_SEGMENT:
                    start = drawing.GetStart()
                    end = drawing.GetEnd()
                    min_x = min(min_x, start.x, end.x)
                    max_x = max(max_x, start.x, end.x)
                    min_y = min(min_y, start.y, end.y)
                    max_y = max(max_y, start.y, end.y)
                    
                elif shape_type == pcbnew.SHAPE_T_CIRCLE:
                    center = drawing.GetCenter()
                    radius = drawing.GetRadius()
                    min_x = min(min_x, center.x - radius)
                    max_x = max(max_x, center.x + radius)
                    min_y = min(min_y, center.y - radius)
                    max_y = max(max_y, center.y + radius)
                    
                elif shape_type == pcbnew.SHAPE_T_RECT:
                    start = drawing.GetStart()
                    end = drawing.GetEnd()
                    min_x = min(min_x, start.x, end.x)
                    max_x = max(max_x, start.x, end.x)
                    min_y = min(min_y, start.y, end.y)
                    max_y = max(max_y, start.y, end.y)
                    
                elif shape_type == pcbnew.SHAPE_T_ARC:
                    # For arcs, include start, end, and center points as approximation
                    center = drawing.GetCenter()
                    start = drawing.GetStart()
                    end = drawing.GetEnd()
                    min_x = min(min_x, center.x, start.x, end.x)
                    max_x = max(max_x, center.x, start.x, end.x)
                    min_y = min(min_y, center.y, start.y, end.y)
                    max_y = max(max_y, center.y, start.y, end.y)
        
        if found_edge_cuts and min_x != float('inf'):
            # Calculate bounds from Edge.Cuts
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            width = self.mm(max_x - min_x)
            height = self.mm(max_y - min_y)
            return {
                'center_x': center_x,
                'center_y': center_y,
                'width': width,
                'height': height
            }
        
        # Ultimate fallback: use board bounding box
        bbox = board.GetBoundingBox()
        center_x = bbox.GetCenter().x
        center_y = bbox.GetCenter().y
        width = self.mm(bbox.GetWidth())
        height = self.mm(bbox.GetHeight())
        
        return {
            'center_x': center_x,
            'center_y': center_y,
            'width': width,
            'height': height
        }

    def generate_frame(self, board):
        # First, try to find existing rectangle on User.8 layer
        frame_rect = self.find_shape_on_layer(board, pcbnew.User_8)
        
        if frame_rect:
            # User.8 rectangle found - use existing logic
            scad = f"    linear_extrude(height=frame_height) {{\n"
            scad += f"        square([{self.mm(frame_rect[2])}, {self.mm(frame_rect[3])}], center=true);\n"
            scad += "    }\n"
            return scad
    
        # User.8 rectangle not found - auto-calculate frame
        pcb_bounds = self.calculate_pcb_bounds(board)
        
        # Add 5mm margin on all sides (10mm total to width and height)
        frame_margin = 5.0  # mm
        frame_width = pcb_bounds['width'] + (2 * frame_margin)
        frame_height = pcb_bounds['height'] + (2 * frame_margin)
        
        scad = f"    // Auto-calculated frame (PCB + {frame_margin}mm margin)\n"
        scad += f"    linear_extrude(height=frame_height) {{\n"
        scad += f"        square([{frame_width}, {frame_height}], center=true);\n"
        scad += "    }\n"
        
        return scad
    
    def connect_line_segments(self, segments):
        """Try to connect line segments into a closed polygon"""
        if not segments:
            return []
        
        # Start with the first segment
        polygon = list(segments[0])
        used_segments = {0}
        
        tolerance = 0.01  # mm tolerance for connecting points
        
        while len(used_segments) < len(segments):
            last_point = polygon[-1]
            found_connection = False
            
            # Look for a segment that connects to the last point
            for i, segment in enumerate(segments):
                if i in used_segments:
                    continue
                    
                start, end = segment
                
                # Check if segment start connects to last point
                if self.points_close(last_point, start, tolerance):
                    polygon.append(end)
                    used_segments.add(i)
                    found_connection = True
                    break
                # Check if segment end connects to last point
                elif self.points_close(last_point, end, tolerance):
                    polygon.append(start)
                    used_segments.add(i)
                    found_connection = True
                    break
            
            if not found_connection:
                # Can't connect more segments
                break
        
        # Check if we have a closed polygon (last point connects to first)
        if len(polygon) > 2 and self.points_close(polygon[-1], polygon[0], tolerance):
            polygon.pop()  # Remove duplicate closing point
            return polygon
        
        # If not closed or too few segments used, return empty
        if len(used_segments) < len(segments) * 0.8:  # At least 80% of segments should be used
            return []
        
        return polygon

    def points_close(self, p1, p2, tolerance):
        """Check if two points are within tolerance distance"""
        return abs(p1[0] - p2[0]) < tolerance and abs(p1[1] - p2[1]) < tolerance

    def mm(self, nm):
        return nm / 1e6

    def generate_pcb_outline_from_edge_cuts(self, board):
      """Generate PCB outline from Edge.Cuts layer as a single polygon or union of shapes"""
      
      log = getattr(self, 'log_function', lambda msg: print(f"DEBUG: {msg}"))
      
      log("=== Starting Edge.Cuts analysis ===")
      
      # Get PCB bounding box for centering
      pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
      if pcb_rect:
          center_x = pcb_rect[0] + pcb_rect[2]/2
          center_y = pcb_rect[1] + pcb_rect[3]/2
          log(f"Using User.9 center: ({self.mm(center_x)}, {self.mm(center_y)}) mm")
      else:
          bbox = board.GetBoundingBox()
          center_x = bbox.GetCenter().x
          center_y = bbox.GetCenter().y
          log(f"Using board bbox center: ({self.mm(center_x)}, {self.mm(center_y)}) mm")
      
      # Collect all Edge.Cuts elements
      shapes = []
      line_segments = []
      
      for drawing in board.GetDrawings():
          if drawing.GetLayer() == pcbnew.Edge_Cuts and isinstance(drawing, pcbnew.PCB_SHAPE):
              shape_type = drawing.GetShape()
              
              if shape_type == pcbnew.SHAPE_T_SEGMENT:
                  # Collect line segments to form polygon
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  x1, y1 = self.mm(start.x - center_x), self.mm(start.y - center_y)
                  x2, y2 = self.mm(end.x - center_x), self.mm(end.y - center_y)
                  line_segments.append([(x1, y1), (x2, y2)])
                  log(f"Line segment: ({x1}, {y1}) to ({x2}, {y2})")
                  
              elif shape_type == pcbnew.SHAPE_T_CIRCLE:
                  # Add circle as separate shape with clearance
                  center_circle = drawing.GetCenter()
                  radius = drawing.GetRadius()
                  cx, cy = self.mm(center_circle.x - center_x), self.mm(center_circle.y - center_y)
                  r = self.mm(radius) + pcbClearence
                  shapes.append(f"translate([{cx}, {cy}]) circle(r={r})")
                  log(f"Circle: center ({cx}, {cy}), radius {r} (with clearance)")
                  
              elif shape_type == pcbnew.SHAPE_T_RECT:
                  # Add rectangle as separate shape with clearance
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  x1, y1 = self.mm(start.x - center_x), self.mm(start.y - center_y)
                  x2, y2 = self.mm(end.x - center_x), self.mm(end.y - center_y)
                  w, h = abs(x2 - x1) + 2 * pcbClearence, abs(y2 - y1) + 2 * pcbClearence
                  cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                  shapes.append(f"translate([{cx}, {cy}]) square([{w}, {h}], center=true)")
                  log(f"Rectangle: center ({cx}, {cy}), size {w}x{h} (with clearance)")
                  
              elif shape_type == pcbnew.SHAPE_T_ARC:
                  # Convert arc to polygon approximation
                  center_arc = drawing.GetCenter()
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  
                  # Calculate arc parameters
                  cx, cy = self.mm(center_arc.x - center_x), self.mm(center_arc.y - center_y)
                  sx, sy = self.mm(start.x - center_x), self.mm(start.y - center_y)
                  ex, ey = self.mm(end.x - center_x), self.mm(end.y - center_y)
                  
                  # Calculate radius and angles
                  import math
                  radius = math.sqrt((sx - cx)**2 + (sy - cy)**2)
                  start_angle = math.atan2(sy - cy, sx - cx)
                  end_angle = math.atan2(ey - cy, ex - cx)
                  
                  # Generate arc points (approximate with line segments)
                  arc_points = []
                  num_segments = max(8, int(abs(end_angle - start_angle) * 180 / math.pi / 10))
                  
                  if end_angle < start_angle:
                      end_angle += 2 * math.pi
                      
                  for i in range(num_segments + 1):
                      angle = start_angle + (end_angle - start_angle) * i / num_segments
                      x = cx + radius * math.cos(angle)
                      y = cy + radius * math.sin(angle)
                      arc_points.append((x, y))
                  
                  # Add arc points to line segments
                  for i in range(len(arc_points) - 1):
                      line_segments.append([arc_points[i], arc_points[i + 1]])
                  
                  log(f"Arc: center ({cx}, {cy}), radius {radius}, {num_segments} segments")
      
      # Build the final SCAD code
      scad = ""
      
      # If we have line segments, try to form a closed polygon
      if line_segments:
          polygon_points = self.connect_line_segments(line_segments)
          if polygon_points:
              points_str = ",".join([f"[{x},{y}]" for x, y in polygon_points])
              # Apply clearance using offset() for closed polygons
              scad += f"    offset(r={pcbClearence}) polygon(points=[{points_str}]);\n"
              log(f"Created polygon with {len(polygon_points)} points and {pcbClearence}mm clearance")
          else:
              # If we can't form a closed polygon, create individual line shapes with clearance
              log("Could not form closed polygon, using individual line shapes with clearance")
              for segment in line_segments:
                  (x1, y1), (x2, y2) = segment
                  # Create a thin rectangle for each line segment with increased width for clearance
                  length = ((x2-x1)**2 + (y2-y1)**2)**0.5
                  if length > 0.001:  # Avoid zero-length segments
                      angle = math.atan2(y2-y1, x2-x1) * 180 / math.pi
                      cx, cy = (x1+x2)/2, (y1+y2)/2
                      line_width = 0.1 + 2 * pcbClearence
                      shapes.append(f"translate([{cx}, {cy}]) rotate([0, 0, {angle}]) square([{length}, {line_width}], center=true)")
      
      # Add other shapes to union if we have any
      if shapes:
          if scad:  # We already have a polygon
              scad = f"    union() {{\n        offset(r={pcbClearence}) polygon(points=[{points_str}]);\n"
              for shape in shapes:
                  scad += f"        {shape};\n"
              scad += "    }\n"
          else:  # Only shapes, no polygon
              if len(shapes) == 1:
                  scad = f"    {shapes[0]};\n"
              else:
                  scad = "    union() {\n"
                  for shape in shapes:
                      scad += f"        {shape};\n"
                  scad += "    }\n"
      
      # Fallback if no Edge.Cuts found
      if not scad:
          log("No Edge.Cuts shapes found, using board bounding box fallback with clearance")
          bbox = board.GetBoundingBox()
          w = self.mm(bbox.GetWidth()) + 2 * pcbClearence
          h = self.mm(bbox.GetHeight()) + 2 * pcbClearence
          scad = f"    square([{w}, {h}], center=true);\n"
          log(f"Fallback size: {w} x {h} mm (with clearance)")
      
      log("=== Edge.Cuts analysis complete ===")

      return scad


    def generate_pcb_outline(self, board):
        log = getattr(self, 'log_function', lambda msg: print(f"DEBUG: {msg}"))
        self.debug_all_layers(board)
        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if pcb_rect:
            log("Using User.9 rectangle for PCB outline")
            scad = f"    square([{self.mm(pcb_rect[2])}, {self.mm(pcb_rect[3])}], center=true);\n"
            return scad
        else:
            log("No User.9 rectangle found, falling back to Edge.Cuts")
            return self.generate_pcb_outline_from_edge_cuts(board)


    def get_pad_bounds(self, pad_info):
        """Get the bounding box of a pad considering its rotation"""
        import math
        
        angle_rad = math.radians(pad_info['angle'])
        half_w = pad_info['width'] / 2
        half_h = pad_info['height'] / 2
        
        # Calculate rotated corner positions
        corners = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h)
        ]
        
        rotated_corners = []
        for x, y in corners:
            rx = x * math.cos(angle_rad) - y * math.sin(angle_rad)
            ry = x * math.sin(angle_rad) + y * math.cos(angle_rad)
            rotated_corners.append((rx + pad_info['x'], ry + pad_info['y']))
        
        min_x = min(corner[0] for corner in rotated_corners)
        max_x = max(corner[0] for corner in rotated_corners)
        min_y = min(corner[1] for corner in rotated_corners)
        max_y = max(corner[1] for corner in rotated_corners)
        
        return {
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y,
            'width': max_x - min_x,
            'height': max_y - min_y
        }

    def find_close_pads(self, current_pad, all_pads, current_index, search_radius):
        """Find pads within search_radius of the current pad"""
        import math
        
        close_pads = []
        current_x = current_pad['x']
        current_y = current_pad['y']
        
        for i, pad in enumerate(all_pads):
            if i == current_index:
                continue
                
            dx = pad['x'] - current_x
            dy = pad['y'] - current_y
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance <= search_radius:
                close_pads.append(pad)
        
        return close_pads


    def project_pad_dimension(self, pad_info, direction_x, direction_y):
        """Project pad's half-dimension onto a given direction"""
        import math
        
        angle_rad = math.radians(pad_info['angle'])
        half_w = pad_info['width'] / 2
        half_h = pad_info['height'] / 2
        
        # Pad's local axes in global coordinates
        pad_x_axis = (math.cos(angle_rad), math.sin(angle_rad))
        pad_y_axis = (-math.sin(angle_rad), math.cos(angle_rad))
        
        # Project pad dimensions onto the given direction
        proj_x = abs(half_w * (pad_x_axis[0] * direction_x + pad_x_axis[1] * direction_y))
        proj_y = abs(half_h * (pad_y_axis[0] * direction_x + pad_y_axis[1] * direction_y))
        
        return proj_x + proj_y

    def find_pad_groups(self, all_pads):
        """Group pads that are close to each other and need uniform shrinking"""
        import math
        
        groups = []
        processed = set()
        
        for i, pad in enumerate(all_pads):
            if i in processed:
                continue
                
            # Start a new group with this pad
            current_group = [i]
            processed.add(i)
            
            # Find all pads connected to this group
            changed = True
            while changed:
                changed = False
                for j, other_pad in enumerate(all_pads):
                    if j in processed:
                        continue
                        
                    # Check if this pad is close to any pad in the current group
                    for group_idx in current_group:
                        group_pad = all_pads[group_idx]
                        dx = other_pad['x'] - group_pad['x']
                        dy = other_pad['y'] - group_pad['y']
                        distance = math.sqrt(dx*dx + dy*dy)
                        
                        # Consider pads close if they're within 2x the minimum mask width
                        max_dimension = max(group_pad['width'], group_pad['height'], 
                                          other_pad['width'], other_pad['height'])
                        threshold = max_dimension + min_mask_width * 2
                        
                        if distance < threshold:
                            current_group.append(j)
                            processed.add(j)
                            changed = True
                            break
                    
                    if changed:
                        break
            
            groups.append(current_group)
        
        return groups

    def calculate_group_shrink_factor(self, group_indices, all_pads):
        """Calculate separate shrink factors for width and height for a group of closely packed pads"""
        import math
        
        if len(group_indices) <= 1:
            return {'width': 1.0, 'height': 1.0}  # No shrinking needed for single pads
        
        group_pads = [all_pads[i] for i in group_indices]
        
        # Find the most constraining pad pairs for each direction
        min_width_shrink = 1.0
        min_height_shrink = 1.0
        
        for i, pad1 in enumerate(group_pads):
            for j, pad2 in enumerate(group_pads):
                if i >= j:
                    continue
                    
                dx = pad2['x'] - pad1['x']
                dy = pad2['y'] - pad1['y']
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance < 0.001:
                    continue
                
                # Check X-direction constraint (pads side-by-side)
                if abs(dx) > abs(dy) * 1.5:  # Primarily X-direction separation
                    pad1_half_width = pad1['width'] / 2
                    pad2_half_width = pad2['width'] / 2
                    current_gap = abs(dx) - pad1_half_width - pad2_half_width
                    
                    if current_gap < min_mask_width:
                        required_shrink = (abs(dx) - min_mask_width) / (pad1_half_width + pad2_half_width)
                        min_width_shrink = min(min_width_shrink, required_shrink)
                
                # Check Y-direction constraint (pads above/below each other)
                elif abs(dy) > abs(dx) * 1.5:  # Primarily Y-direction separation
                    pad1_half_height = pad1['height'] / 2
                    pad2_half_height = pad2['height'] / 2
                    current_gap = abs(dy) - pad1_half_height - pad2_half_height
                    
                    if current_gap < min_mask_width:
                        required_shrink = (abs(dy) - min_mask_width) / (pad1_half_height + pad2_half_height)
                        min_height_shrink = min(min_height_shrink, required_shrink)
                
                # Check diagonal constraints (pads close in both directions)
                else:
                    # Both X and Y constraints may apply
                    pad1_half_width = pad1['width'] / 2
                    pad2_half_width = pad2['width'] / 2
                    pad1_half_height = pad1['height'] / 2
                    pad2_half_height = pad2['height'] / 2
                    
                    current_gap_x = abs(dx) - pad1_half_width - pad2_half_width
                    current_gap_y = abs(dy) - pad1_half_height - pad2_half_height
                    
                    if current_gap_x < min_mask_width:
                        required_shrink_x = (abs(dx) - min_mask_width) / (pad1_half_width + pad2_half_width)
                        min_width_shrink = min(min_width_shrink, required_shrink_x)
                    
                    if current_gap_y < min_mask_width:
                        required_shrink_y = (abs(dy) - min_mask_width) / (pad1_half_height + pad2_half_height)
                        min_height_shrink = min(min_height_shrink, required_shrink_y)
        
        # Ensure minimum pad size (don't shrink below 0.1mm)
        for pad in group_pads:
            if pad['width'] * min_width_shrink < min_pad_size:
                min_width_shrink = max(min_width_shrink, min_pad_size / pad['width'])
            if pad['height'] * min_height_shrink < min_pad_size:
                min_height_shrink = max(min_height_shrink, min_pad_size / pad['height'])
        
        return {
            'width': max(min_pad_size, min_width_shrink),
            'height': max(min_pad_size, min_height_shrink)
        }


    def generate_pads(self, board):
        scad = ""
        
        # Try to get center from User.9 first
        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if pcb_rect:
            center_x = pcb_rect[0] + pcb_rect[2]/2
            center_y = pcb_rect[1] + pcb_rect[3]/2
        else:
            # Fallback to board bounding box center
            bbox = board.GetBoundingBox()
            center_x = bbox.GetCenter().x
            center_y = bbox.GetCenter().y

        # Collect all SMD pads with their information, filtered by layer
        pads_info = []
        for module in board.GetFootprints():
            for pad in module.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    # Check which copper layer(s) the pad is on
                    pad_layers = pad.GetLayerSet()
                    is_front_copper = pad_layers.Contains(pcbnew.F_Cu)
                    is_back_copper = pad_layers.Contains(pcbnew.B_Cu)
                    
                    # Filter based on global configuration variables
                    should_include = False
                    if front_copper_pads and is_front_copper:
                        should_include = True
                    if back_copper_pads and is_back_copper:
                        should_include = True
                    
                    # Only add pad if it matches the layer criteria
                    if should_include:
                        pos = pad.GetPosition()
                        size = pad.GetSize()
                        angle = pad.GetOrientation().AsDegrees()
                        pads_info.append({
                            'x': self.mm(pos.x - center_x),
                            'y': self.mm(pos.y - center_y),
                            'width': self.mm(size.x),
                            'height': self.mm(size.y),
                            'angle': angle,
                            'pad': pad
                        })

        if not pads_info:
            return "    // No SMD pads found matching layer criteria\n"

        # Group pads that are close to each other
        pad_groups = self.find_pad_groups(pads_info)
        
        # Calculate shrink factors for each group
        group_shrink_factors = {}
        for group_indices in pad_groups:
            shrink_factors = self.calculate_group_shrink_factor(group_indices, pads_info)
            for idx in group_indices:
                group_shrink_factors[idx] = shrink_factors

        # Generate pad cutouts with directional shrinking per group
        for i, pad_info in enumerate(pads_info):
            shrink_factors = group_shrink_factors.get(i, {'width': 1.0, 'height': 1.0})
            
            adjusted_width = pad_info['width'] * shrink_factors['width']
            adjusted_height = pad_info['height'] * shrink_factors['height']
            
            scad += f"    translate([{pad_info['x']}, {pad_info['y']}]) "
            scad += f"rotate([0, 0, {pad_info['angle']}]) "
            scad += f"square([{adjusted_width}, {adjusted_height}], center=true);\n"
        
        return scad

    def generate_alignment_holes(self, board):
        alignment_holes = self.find_circles_on_layer(board, pcbnew.User_7)
        if not alignment_holes:
            return "    // No alignment holes found on User.7 layer\n"

        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if not pcb_rect:
            return "    // No PCB outline found on User.9 layer\n"

        center_x = pcb_rect[0] + pcb_rect[2]/2
        center_y = pcb_rect[1] + pcb_rect[3]/2

        scad = ""
        for hole in alignment_holes:
            x = self.mm(hole[0] - center_x)
            y = self.mm(hole[1] - center_y)
            scad += f"    translate([{x}, {y}, -0.005]) "
            scad += f"cylinder(h=frame_height + 0.01, d=alignment_pin_diameter, center=false);\n"
        return scad

    def find_shape_on_layer(self, board, layer):
        for drawing in board.GetDrawings():
            if (isinstance(drawing, pcbnew.PCB_SHAPE) and
                drawing.GetShape() == pcbnew.SHAPE_T_RECT and
                    drawing.GetLayer() == layer):
                return (drawing.GetStart().x, drawing.GetStart().y,
                        drawing.GetEnd().x - drawing.GetStart().x,
                        drawing.GetEnd().y - drawing.GetStart().y)
        return None

    def find_circles_on_layer(self, board, layer):
        circles = []
        for drawing in board.GetDrawings():
            if (isinstance(drawing, pcbnew.PCB_SHAPE) and
                drawing.GetShape() == pcbnew.SHAPE_T_CIRCLE and
                    drawing.GetLayer() == layer):
                center = drawing.GetCenter()
                circles.append((center.x, center.y))
        return circles

    def mm(self, nm):
        return nm / 1e6

    def debug_all_layers(self, board):
        """Debug function to list all layers with drawings"""
        try:
            project_file = board.GetFileName()
            project_dir = os.path.dirname(project_file)
            output_dir = os.path.join(project_dir, workDir)
            log_file = os.path.join(output_dir, "all_layers_debug.log")
            
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"=== All Layers Analysis ===\n")
                
                layer_counts = {}
                for drawing in board.GetDrawings():
                    layer = drawing.GetLayer()
                    if layer not in layer_counts:
                        layer_counts[layer] = 0
                    layer_counts[layer] += 1
                
                f.write(f"Total drawings: {sum(layer_counts.values())}\n")
                for layer, count in sorted(layer_counts.items()):
                    f.write(f"Layer {layer}: {count} drawings\n")
                    
                f.write(f"\nEdge_Cuts constant value: {pcbnew.Edge_Cuts}\n")
        except Exception as e:
            print(f"Debug error: {e}")


StencilGenerator().register()
